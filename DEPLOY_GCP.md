# Deploy to Google Cloud VM — Step-by-Step Guide

This guide walks you through deploying the **Airflow + dbt ELT pipeline** (stock market data) to a Google Cloud Platform (GCP) Compute Engine VM.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Create a GCP VM Instance](#2-create-a-gcp-vm-instance)
3. [Configure Firewall Rules](#3-configure-firewall-rules)
4. [SSH into the VM](#4-ssh-into-the-vm)
5. [Install Docker on the VM](#5-install-docker-on-the-vm)
6. [Clone the Repository](#6-clone-the-repository)
7. [Create the Environment File](#7-create-the-environment-file)
8. [Build and Start All Services](#8-build-and-start-all-services)
9. [Create an Airflow Admin User](#9-create-an-airflow-admin-user)
10. [Configure Airflow Connections](#10-configure-airflow-connections)
11. [Create the Airflow Pool](#11-create-the-airflow-pool)
12. [Verify All Services](#12-verify-all-services)
13. [Maintenance and Operations](#13-maintenance-and-operations)
14. [Troubleshooting](#14-troubleshooting)
15. [Architecture Overview](#15-architecture-overview)

---

## 1. Prerequisites

Before you begin, make sure you have the following:

| Requirement | Details |
|---|---|
| **GCP Account** | A Google Cloud account with billing enabled. The free tier `e2-micro` instance is eligible for [GCP Free Tier](https://cloud.google.com/free). |
| **gcloud CLI** | Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) on your local machine. |
| **Alpha Vantage API Key** | Sign up at [alphavantage.co](https://www.alphavantage.co/support/#api-key) to get a free API key. |
| **Slack Webhook (Optional)** | Create a [Slack Incoming Webhook](https://api.slack.com/messaging/webhooks) if you want DAG success/failure notifications. |

### Authenticate with GCP

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

---

## 2. Create a GCP VM Instance

You can create the VM using the provided script or manually.

### Option A: Use the Provided Script

```bash
bash scripts/gcp_migration/create_vm.sh
```

This creates an `e2-micro` (Free Tier eligible) VM in `us-west1-b` with Ubuntu 22.04 LTS and a 30 GB disk.

### Option B: Create Manually

```bash
gcloud compute instances create airflow-vm-free-tier \
    --zone=us-west1-b \
    --machine-type=e2-micro \
    --image-project=ubuntu-os-cloud \
    --image-family=ubuntu-2204-lts \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --tags=airflow-server,http-server
```

### Option C: Use the GCP Console

1. Go to **Compute Engine** → **VM Instances** → **Create Instance**.
2. Set the following:
   - **Name**: `airflow-vm-free-tier`
   - **Region/Zone**: `us-west1-b` (Oregon — Free Tier eligible)
   - **Machine type**: `e2-micro` (2 vCPU, 1 GB RAM)
   - **Boot disk**: Ubuntu 22.04 LTS, 30 GB Standard persistent disk
   - **Networking tags**: `airflow-server`, `http-server`
3. Click **Create**.

> **Note**: For production workloads with heavier transformations, consider `e2-small` (2 GB RAM) or `e2-medium` (4 GB RAM). The `e2-micro` runs with aggressive memory limits and requires swap.

### Note Your VM's External IP

```bash
gcloud compute instances describe airflow-vm-free-tier \
    --zone=us-west1-b \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Save this IP — you will use it to access Airflow and MinIO.

---

## 3. Configure Firewall Rules

Open the ports needed by the services:

```bash
gcloud compute firewall-rules create allow-airflow-http \
    --allow tcp:8080,tcp:9000,tcp:9001 \
    --target-tags=airflow-server \
    --description="Allow Airflow UI (8080), MinIO API (9000), MinIO Console (9001)"
```

| Port | Service |
|------|---------|
| `8080` | Airflow Web UI |
| `9000` | MinIO S3 API |
| `9001` | MinIO Console |

> **Security Note**: For production, restrict the source IP ranges using `--source-ranges=YOUR_IP/32` instead of allowing all traffic. Never expose PostgreSQL (5432) to the public internet.

---

## 4. SSH into the VM

```bash
gcloud compute ssh airflow-vm-free-tier --zone=us-west1-b
```

All remaining steps are executed **inside the VM**.

---

## 5. Install Docker on the VM

### Option A: Use the Provided Script

```bash
# Once inside the VM, if you already have the repo cloned:
bash scripts/gcp_migration/install_on_vm.sh
```

### Option B: Install Manually Step-by-Step

#### 5.1 Enable Swap (Critical for `e2-micro`)

The `e2-micro` instance has only 1 GB RAM. Swap is essential:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Verify swap is active:

```bash
free -h
# You should see ~2 GB under Swap
```

#### 5.2 Install Docker Engine

```bash
# Update packages and install prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

#### 5.3 Allow Your User to Run Docker Without `sudo`

```bash
sudo usermod -aG docker $USER
newgrp docker
```

#### 5.4 Verify Docker Installation

```bash
docker --version
docker compose version
```

---

## 6. Clone the Repository

```bash
cd ~
git clone https://github.com/chenjinghao/de-project-1-airflow-dbt-4-ELT.git
cd de-project-1-airflow-dbt-4-ELT
```

### Prepare Directory Permissions

The Airflow container runs as user `astro` (UID 50000). Pre-create and set ownership:

```bash
mkdir -p logs plugins
sudo chown -R 50000:0 logs plugins include dags
```

---

## 7. Create the Environment File

The production Docker Compose file (`docker-compose.prod.yml`) reads credentials from a `.env` file. Create one:

```bash
cat > .env << 'EOF'
# PostgreSQL (used for both Airflow metadata DB and stocks_db)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=CHANGE_ME_TO_A_STRONG_PASSWORD
POSTGRES_DB=stocks_db

# MinIO (S3-compatible object storage)
MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=CHANGE_ME_TO_A_STRONG_PASSWORD
EOF
```

> **Important**: Replace `CHANGE_ME_TO_A_STRONG_PASSWORD` with actual strong passwords before going live.

---

## 8. Build and Start All Services

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This will start the following services:

| Service | Description | Port |
|---------|-------------|------|
| `postgres` | PostgreSQL 15 database (Airflow metadata + stocks data) | 5432 (internal) |
| `minio` | MinIO S3-compatible object storage | 9000, 9001 |
| `airflow-apiserver` | Airflow Web UI and REST API | 8080 |
| `airflow-scheduler` | Airflow task scheduler | — |
| `airflow-init` | One-time setup: database migration + admin user creation | — |

### Wait for Initialization

The first build takes 5–15 minutes (downloading images, installing Python packages). Monitor progress:

```bash
# Watch all container logs
docker compose -f docker-compose.prod.yml logs -f

# Or check just the init container
docker compose -f docker-compose.prod.yml logs -f airflow-init
```

Wait until the `airflow-init` container finishes (it creates the database and admin user, then exits).

Then check all containers are running:

```bash
docker compose -f docker-compose.prod.yml ps
```

Expected output — all services should show `running` (except `airflow-init` which exits after completion):

```
NAME                SERVICE              STATUS
postgres            postgres             running
minio               minio                running
airflow-apiserver   airflow-apiserver    running
airflow-scheduler   airflow-scheduler    running
airflow-init        airflow-init         exited (0)
```

---

## 9. Create an Airflow Admin User

The `airflow-init` service in `docker-compose.prod.yml` automatically creates an admin user:

- **Username**: `admin`
- **Password**: `admin`

> **Important**: Change this password immediately after your first login via **Security** → **List Users** → Edit the `admin` user.

If you need to create an additional user:

```bash
docker compose -f docker-compose.prod.yml exec airflow-apiserver \
    airflow users create \
    --role Admin \
    --username your_username \
    --email your_email@example.com \
    --firstname Your \
    --lastname Name \
    --password your_secure_password
```

---

## 10. Configure Airflow Connections

The DAG requires four Airflow connections to function. Open the Airflow UI at `http://<VM_EXTERNAL_IP>:8080` and go to **Admin** → **Connections**, then add the following:

### 10.1 Stock API Connection (`stock_api`)

| Field | Value |
|-------|-------|
| **Connection Id** | `stock_api` |
| **Connection Type** | `HTTP` |
| **Host** | `https://www.alphavantage.co/query` |
| **Password** | Your Alpha Vantage API key |

Or via CLI:

```bash
docker compose -f docker-compose.prod.yml exec airflow-apiserver \
    airflow connections add 'stock_api' \
    --conn-type 'http' \
    --conn-host 'https://www.alphavantage.co/query' \
    --conn-password 'YOUR_ALPHA_VANTAGE_API_KEY'
```

### 10.2 PostgreSQL Connection (`postgres_stock`)

| Field | Value |
|-------|-------|
| **Connection Id** | `postgres_stock` |
| **Connection Type** | `Postgres` |
| **Host** | `postgres` (Docker service name) |
| **Schema** | `stocks_db` |
| **Login** | `postgres` |
| **Password** | Same as `POSTGRES_PASSWORD` in your `.env` |
| **Port** | `5432` |

Or via CLI:

```bash
docker compose -f docker-compose.prod.yml exec airflow-apiserver \
    airflow connections add 'postgres_stock' \
    --conn-type 'postgres' \
    --conn-host 'postgres' \
    --conn-schema 'stocks_db' \
    --conn-login 'postgres' \
    --conn-password 'YOUR_POSTGRES_PASSWORD' \
    --conn-port '5432'
```

### 10.3 MinIO Connection (`minio`)

| Field | Value |
|-------|-------|
| **Connection Id** | `minio` |
| **Connection Type** | `Amazon Web Services` |
| **Login** | Same as `MINIO_ROOT_USER` in your `.env` |
| **Password** | Same as `MINIO_ROOT_PASSWORD` in your `.env` |
| **Extra** | `{"endpoint_url": "http://minio:9000"}` |

Or via CLI:

```bash
docker compose -f docker-compose.prod.yml exec airflow-apiserver \
    airflow connections add 'minio' \
    --conn-type 'aws' \
    --conn-login 'YOUR_MINIO_USER' \
    --conn-password 'YOUR_MINIO_PASSWORD' \
    --conn-extra '{"endpoint_url": "http://minio:9000"}'
```

### 10.4 Slack Connection (`slack`) — Optional

| Field | Value |
|-------|-------|
| **Connection Id** | `slack` |
| **Connection Type** | `Slack Incoming Webhook` |
| **Password** | Your Slack webhook URL |

Or via CLI:

```bash
docker compose -f docker-compose.prod.yml exec airflow-apiserver \
    airflow connections add 'slack' \
    --conn-type 'slackwebhook' \
    --conn-password 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
```

> **Note**: If you don't configure the Slack connection, the DAG will still run but success/failure notifications will fail silently.

---

## 11. Create the Airflow Pool

The DAG uses an `api_pool` to throttle API calls. Create it:

```bash
docker compose -f docker-compose.prod.yml exec airflow-apiserver \
    airflow pools set api_pool 1 "Pool to limit concurrent Alpha Vantage API calls"
```

---

## 12. Verify All Services

### 12.1 Airflow Web UI

Open `http://<VM_EXTERNAL_IP>:8080` in your browser.

- Log in with `admin` / `admin`.
- You should see the `most_active_dag` in the DAGs list.
- Toggle the DAG **ON** to enable scheduled runs (weekdays at 9 PM ET).
- Trigger a manual run to test: click the ▶️ play button → **Trigger DAG**.

### 12.2 MinIO Console

Open `http://<VM_EXTERNAL_IP>:9001` in your browser.

- Log in with the `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from your `.env` file.
- After the DAG runs, you should see a `bronze` bucket with dated folders containing JSON files.

### 12.3 Check PostgreSQL

```bash
docker compose -f docker-compose.prod.yml exec postgres \
    psql -U postgres -d stocks_db -c "SELECT COUNT(*) FROM raw_most_active_stocks;"
```

### 12.4 Check Container Health

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=50 airflow-scheduler
```

---

## 13. Maintenance and Operations

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f airflow-scheduler
```

### Restart Services

```bash
# Restart all
docker compose -f docker-compose.prod.yml restart

# Restart a specific service
docker compose -f docker-compose.prod.yml restart airflow-scheduler
```

### Stop All Services

```bash
docker compose -f docker-compose.prod.yml down
```

### Stop and Remove All Data (⚠️ Destructive)

```bash
docker compose -f docker-compose.prod.yml down -v
```

### Update After Code Changes

```bash
cd ~/de-project-1-airflow-dbt-4-ELT
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```

### Monitor Disk Usage

The `e2-micro` Free Tier instance has a 30 GB disk. Monitor usage:

```bash
df -h
docker system df
```

Clean up unused Docker resources:

```bash
docker system prune -f
```

---

## 14. Troubleshooting

### Container Keeps Restarting / OOM Killed

The `e2-micro` has only 1 GB RAM. If containers are being killed:

1. Verify swap is active:
   ```bash
   free -h
   ```

2. Check which container was OOM-killed:
   ```bash
   docker inspect <container_id> | grep -i oom
   ```

3. Consider upgrading to `e2-small` (2 GB RAM):
   ```bash
   # Stop the VM first, then resize
   gcloud compute instances stop airflow-vm-free-tier --zone=us-west1-b
   gcloud compute instances set-machine-type airflow-vm-free-tier \
       --zone=us-west1-b --machine-type=e2-small
   gcloud compute instances start airflow-vm-free-tier --zone=us-west1-b
   ```

### Airflow UI Not Accessible

1. Check the container is running:
   ```bash
   docker compose -f docker-compose.prod.yml ps airflow-apiserver
   ```

2. Check the health endpoint from inside the VM:
   ```bash
   curl http://localhost:8080/health
   ```

3. Verify the firewall rule exists:
   ```bash
   gcloud compute firewall-rules list --filter="name=allow-airflow-http"
   ```

### Build Fails Due to Timeout

The `e2-micro` has limited CPU and network bandwidth. If the build times out:

1. Retry the build — the `UV_HTTP_TIMEOUT=300` in the `Dockerfile` helps.
2. Build one service at a time:
   ```bash
   docker compose -f docker-compose.prod.yml build airflow-apiserver
   docker compose -f docker-compose.prod.yml up -d
   ```

### DAG Import Errors

```bash
docker compose -f docker-compose.prod.yml exec airflow-scheduler \
    airflow dags list-import-errors
```

### Database Connection Refused

Check that the PostgreSQL container is healthy:

```bash
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U postgres
```

### MinIO Bucket Not Created

The DAG automatically creates the `bronze` bucket on first run. To create it manually:

```bash
docker compose -f docker-compose.prod.yml exec minio \
    mc alias set local http://localhost:9000 YOUR_MINIO_USER YOUR_MINIO_PASSWORD
docker compose -f docker-compose.prod.yml exec minio \
    mc mb local/bronze
```

---

## 15. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Google Cloud VM (e2-micro)                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  PostgreSQL   │  │    MinIO     │  │   Airflow Containers   │ │
│  │    :5432      │  │  :9000/9001  │  │                        │ │
│  │              │  │              │  │  ┌──────────────────┐  │ │
│  │  stocks_db    │  │  bronze/     │  │  │  API Server      │  │ │
│  │  ├─ raw_*     │  │  └─ YYYY-MM- │  │  │  :8080           │  │ │
│  │  ├─ stg_*     │  │     DD/      │  │  └──────────────────┘  │ │
│  │  ├─ int_*     │  │     ├─ most_ │  │  ┌──────────────────┐  │ │
│  │  └─ mart_*    │  │     ├─ price │  │  │  Scheduler       │  │ │
│  │              │  │     ├─ news/ │  │  │  (cron schedule)  │  │ │
│  └──────────────┘  │     └─ biz/  │  │  └──────────────────┘  │ │
│                    └──────────────┘  └────────────────────────┘ │
│                                                                 │
│  Data Flow:                                                     │
│  Alpha Vantage API → MinIO (JSON) → PostgreSQL (raw)            │
│                       → dbt staging → dbt intermediate → mart   │
└─────────────────────────────────────────────────────────────────┘
```

### Services Summary

| Service | Image | Purpose | Memory Limit |
|---------|-------|---------|-------------|
| PostgreSQL | `postgres:15` | Data warehouse + Airflow metadata | 128 MB |
| MinIO | `minio/minio` | S3-compatible object storage (data lake) | 128 MB |
| Airflow API Server | Astro Runtime 3.1-12 | Web UI + REST API | 450 MB |
| Airflow Scheduler | Astro Runtime 3.1-12 | Task scheduling and execution | 256 MB |

### DAG Schedule

The `most_active_dag` runs at **9:00 PM ET, Monday–Friday** (after NYSE market close) and:

1. Checks if today is a NYSE trading holiday.
2. Extracts stock data from the Alpha Vantage API (most active, prices, news, business info).
3. Stores raw JSON files in MinIO (`bronze` bucket).
4. Loads data into PostgreSQL (`raw_most_active_stocks`, `biz_info_lookup` tables).
5. Runs dbt transformations (staging → intermediate → mart models).
6. Sends a Slack notification on success or failure.

### Required Airflow Connections

| Connection ID | Type | Purpose |
|---------------|------|---------|
| `stock_api` | HTTP | Alpha Vantage API endpoint and key |
| `postgres_stock` | Postgres | Database for stock data storage |
| `minio` | AWS | MinIO S3-compatible storage |
| `slack` | Slack Webhook | (Optional) DAG notifications |
