# Deploy Airflow Project to Google Cloud VM

## Overview
Deploy the stock data pipeline (Airflow + PostgreSQL + MinIO) to a GCP VM (e2-medium), with PostgreSQL accessible externally for a Streamlit web app on a separate machine.

---

## Step 1: Prerequisites Check

```bash
gcloud --version
gcloud auth login
gcloud projects list
gcloud config set project YOUR_PROJECT_ID
gcloud config list
gcloud services enable compute.googleapis.com
```

You need:
- GCP project with billing enabled
- Alpha Vantage API key (free: https://www.alphavantage.co/support/#api-key)
- (Optional) Slack webhook URL for notifications

---

## Step 2: Create the VM

**Option A — Use the existing script** (from Git Bash or WSL on Windows):
```bash
bash scripts/gcp_migration/create_vm.sh
```

**Option B — Run commands manually** (if the script doesn't work on your shell):
```bash
gcloud compute instances create airflow-vm-standard \
    --zone=us-west1-b \
    --machine-type=e2-medium \
    --image-project=ubuntu-os-cloud \
    --image-family=ubuntu-2204-lts \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --tags=airflow-server,http-server

gcloud compute firewall-rules create allow-airflow-http \
    --allow tcp:22,tcp:8080,tcp:5432 \
    --target-tags=airflow-server \
    --description="Allow SSH, Airflow UI, and PostgreSQL access"
```

**Get your VM's external IP** (write it down — referred to as `<VM_EXTERNAL_IP>` below):
```bash
gcloud compute instances describe airflow-vm-standard \
    --zone=us-west1-b \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

---

## Step 3: SSH into the VM

```bash
gcloud compute ssh airflow-vm-standard --zone=us-west1-b
```

---

## Step 4: Clone the Repository

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/de-project-1-airflow.git ~/airflow_project
cd ~/airflow_project
```

If repo is private, use a Personal Access Token:
```bash
git clone https://TOKEN@github.com/YOUR_USERNAME/de-project-1-airflow.git ~/airflow_project
```

---

## Step 5: Create the `.env` File

Since PostgreSQL will be publicly accessible, **use strong passwords**.

Generate 3 strong passwords:
```bash
openssl rand -base64 24    # run 3 times
```

Create the file:
```bash
cat > .env << 'EOF'
AIRFLOW__CORE__TEST_CONNECTION=enabled

POSTGRES_USER=jinghao_chen
POSTGRES_PASSWORD=jingH2o880318
POSTGRES_DB=stocks_db
MINIO_ROOT_USER=jinghao_chen
MINIO_ROOT_PASSWORD=jingH2o880318
AIRFLOW_ADMIN_PASSWORD=jingH2o880318
EOF
```

> **Note:** `POSTGRES_DB` must be `stocks_db` — the DAG code and init script hardcode this name.

---

## Step 6: Run the Installation Script

```bash
cd ~/airflow_project
bash scripts/gcp_migration/install_on_vm.sh
```

This will:
1. Create 2GB swap space
2. Install Docker Engine + Docker Compose
3. Create required directories with correct permissions
4. Build and start all containers via `docker-compose.prod.yml`

Takes ~5-10 minutes.

---

## Step 7: Verify All Services

```bash
# Check containers are running
sudo docker compose -f docker-compose.prod.yml ps

# Expected:
#   postgres          - Up (healthy)
#   minio             - Up
#   airflow-apiserver - Up (healthy)
#   airflow-scheduler - Up
#   airflow-init      - Exited (0)  <-- expected, one-shot init

# Test PostgreSQL
sudo docker compose -f docker-compose.prod.yml exec postgres pg_isready -U airflow_prod_user -d stocks_db

# Test Airflow health
curl http://localhost:8080/health

# Check logs if anything is wrong
sudo docker compose -f docker-compose.prod.yml logs --tail=50 postgres
sudo docker compose -f docker-compose.prod.yml logs --tail=50 airflow-apiserver
sudo docker compose -f docker-compose.prod.yml logs --tail=50 airflow-scheduler
```

**From your browser:**
- Airflow UI: `http://<VM_EXTERNAL_IP>:8080` — login: `admin` / `admin`
- MinIO Console: `http://<VM_EXTERNAL_IP>:9001` — login: your MINIO_ROOT_USER / MINIO_ROOT_PASSWORD

---

## Step 8: Configure Airflow (in the Web UI)

### 8a. Change admin password
Security > List Users > click "admin" > change password

### 8b. Create `stock_api` connection
Admin > Connections > + Add:

| Field | Value |
|-------|-------|
| Connection Id | `stock_api` |
| Connection Type | HTTP |
| Host | `https://www.alphavantage.co/query` |
| Password | Your Alpha Vantage API key |

### 8c. Create `minio` connection
| Field | Value |
|-------|-------|
| Connection Id | `minio` |
| Connection Type | Generic |
| Login | Your MINIO_ROOT_USER |
| Password | Your MINIO_ROOT_PASSWORD |
| Extra | `{"endpoint_url": "http://minio:9000"}` |

### 8d. Verify auto-configured connections
These are set via environment variables in `docker-compose.prod.yml` and should already exist:
- `postgres_stock` — PostgreSQL connection
- `aws_default` — S3/MinIO connection

### 8e. Create `api_pool`
Admin > Pools > + Add:

| Field | Value |
|-------|-------|
| Pool | `api_pool` |
| Slots | `1` |
| Description | Alpha Vantage API rate limiting |

> **Critical:** Without this pool, DAG tasks will queue indefinitely.

### 8f. (Optional) Create `slack` connection
If you don't want Slack notifications, you can skip this — but the DAG callbacks will log errors. To disable them entirely, remove `on_success_callback` and `on_failure_callback` from `dags/most_active.py`.

---

## Step 9: Verify PostgreSQL External Access

**From your local machine (not the VM):**

```powershell
# Windows PowerShell
Test-NetConnection -ComputerName <VM_EXTERNAL_IP> -Port 5432
```

```bash
# Or with psql (if installed)
psql -h <VM_EXTERNAL_IP> -p 5432 -U airflow_prod_user -d stocks_db
```

**Why this works without extra config:**
- `postgres:15` Docker image defaults to `listen_addresses = '*'` and allows md5 password auth from any host
- `docker-compose.prod.yml` maps port `5432:5432`
- GCP firewall rule opens TCP 5432

---

## Step 10: Connect Streamlit to PostgreSQL

### Connection string:
```
postgresql://airflow_prod_user:<POSTGRES_PASSWORD>@<VM_EXTERNAL_IP>:5432/stocks_db
```

### Using `st.connection` (recommended):
```python
import streamlit as st

conn = st.connection(
    "postgresql",
    type="sql",
    url="postgresql://airflow_prod_user:<PASSWORD>@<VM_EXTERNAL_IP>:5432/stocks_db"
)
df = conn.query("SELECT * FROM raw_most_active_stocks LIMIT 10;")
st.dataframe(df)
```

### Using Streamlit secrets (`.streamlit/secrets.toml`):
```toml
[connections.postgresql]
dialect = "postgresql"
host = "<VM_EXTERNAL_IP>"
port = 5432
database = "stocks_db"
username = "airflow_prod_user"
password = "<POSTGRES_PASSWORD>"
```

### Available tables after the DAG runs:
- `raw_most_active_stocks` — raw stock data (JSONB)
- `biz_info_lookup` — company info
- dbt mart tables: `mart_price_news__analysis`, `mart_price_vol_chgn`, `mart_news__recent`

### Important:
- Use the **EXTERNAL** IP (not the internal `10.x.x.x`)
- If the VM restarts, the IP may change — consider reserving a static IP (see below)

---

## Step 11: (Recommended) Reserve a Static IP

Prevents the external IP from changing when the VM restarts:

```bash
gcloud compute addresses create airflow-static-ip --region=us-west1

gcloud compute instances delete-access-config airflow-vm-standard \
    --zone=us-west1-b --access-config-name="External NAT"

gcloud compute instances add-access-config airflow-vm-standard \
    --zone=us-west1-b \
    --address=$(gcloud compute addresses describe airflow-static-ip --region=us-west1 --format='get(address)')
```

---

## Step 12: (Optional) Set Up CI/CD with GitHub Actions

Your project includes `.github/workflows/deploy.yml` for auto-deployment on push to `main`.

### Required GitHub Secrets:
| Secret | Value |
|--------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_SA_KEY` | Service account JSON key |
| `ZONE` | `us-west1-b` |
| `INSTANCE_NAME` | `airflow-vm-standard` |
| `SSH_USERNAME` | Your VM username |
| `POSTGRES_USER` | `airflow_prod_user` |
| `POSTGRES_PASSWORD` | Your password |
| `POSTGRES_DB` | `stocks_db` |
| `MINIO_ROOT_USER` | `minio_admin` |
| `MINIO_ROOT_PASSWORD` | Your password |

---

## Bugs Found That Need Fixing

### Bug 1 (HIGH): Missing `MINIO_ROOT_PASSWORD` in CI/CD workflow
**File:** `.github/workflows/deploy.yml` (lines 36-41)

The `.env` generation is missing `MINIO_ROOT_PASSWORD`, which will cause MinIO to fail on every CI/CD deploy. Need to add:
```yaml
MINIO_ROOT_PASSWORD=${{ secrets.MINIO_ROOT_PASSWORD }}
```

### Bug 2 (MEDIUM): Hardcoded admin password
**File:** `docker-compose.prod.yml` (line ~126)

The `airflow-init` service uses `--password admin` instead of `--password ${AIRFLOW_ADMIN_PASSWORD}`. Should use the env variable so the `.env` value is respected.

### Bug 3 (MEDIUM): `api_pool` not auto-created
The DAG requires `api_pool` but nothing creates it automatically. Tasks will queue forever without it. Consider adding pool creation to the `airflow-init` service.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Containers killed (OOM) | Check `sudo dmesg \| grep oom`, verify swap: `free -h` |
| Port 5432 unreachable | Verify firewall: `gcloud compute firewall-rules describe allow-airflow-http` |
| DAG import errors | Check scheduler logs for missing connections/pools |
| Docker build timeout | Retry with `sudo docker compose -f docker-compose.prod.yml build --no-cache` |
| External IP changed | Reserve static IP (Step 11) |
| MinIO bucket missing | Create via MinIO Console at `http://<VM_EXTERNAL_IP>:9001` — bucket name: `bronze` |

### Useful commands on the VM:
```bash
sudo docker compose -f docker-compose.prod.yml ps          # status
sudo docker compose -f docker-compose.prod.yml logs -f      # live logs
sudo docker compose -f docker-compose.prod.yml restart      # restart all
sudo docker stats --no-stream                               # memory usage
```
