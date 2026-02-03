# Secure Deployment Guide (VPN / Private IP)

This guide details how to deploy the **Stock Data Pipeline** in a secure Google Cloud environment using Private IP, ensuring that database traffic and Airflow infrastructure remain within a Virtual Private Cloud (VPC).

## Architecture Overview

In this setup:
- **Cloud SQL** (`stocks_db`) has only a **Private IP** address. It is not accessible from the public internet.
- **Cloud Composer** (Airflow) runs in a **Private IP** environment. Nodes have no public IP addresses.
- **Cloud NAT** is configured to allow Composer to access external APIs (Alpha Vantage) for data extraction.
- **Private Service Access (PSA)** bridges your VPC with Google's managed services (Cloud SQL).
- **VPN / Bastion Host** is required for developers to access the database or Airflow UI (depending on configuration).

## Prerequisites

1.  **Google Cloud Project**: A valid GCP project.
2.  **gcloud CLI**: Installed and authenticated.
3.  **Permissions**: Owner or Editor role (or specific Network/SQL/Composer Admin roles).

## Step-by-Step Setup

### 1. Network Configuration (VPC & NAT)

Create a custom VPC and subnet. Cloud NAT is **required** because Private IP Composer nodes cannot reach the internet (Alpha Vantage API) without it.

```bash
# Variables
export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"
export NETWORK_NAME="stock-pipeline-vpc"
export SUBNET_NAME="composer-subnet"

# 1. Create VPC
gcloud compute networks create $NETWORK_NAME \
    --subnet-mode=custom \
    --bgp-routing-mode=regional

# 2. Create Subnet (e.g., 10.0.0.0/20)
gcloud compute networks subnets create $SUBNET_NAME \
    --network=$NETWORK_NAME \
    --region=$REGION \
    --range=10.0.0.0/20 \
    --enable-private-ip-google-access

# 3. Create Cloud Router
gcloud compute routers create stock-router \
    --network=$NETWORK_NAME \
    --region=$REGION

# 4. Configure Cloud NAT
gcloud compute routers nats create stock-nat \
    --router=stock-router \
    --region=$REGION \
    --auto-allocate-nat-external-ips \
    --nat-all-subnet-ip-ranges
```

### 2. Private Service Access (PSA)

This allows your VPC to communicate with Cloud SQL and Composer's tenant project.

```bash
# 1. Reserve an IP range for Google Services (e.g., /16)
gcloud compute addresses create google-managed-services-$NETWORK_NAME \
    --global \
    --purpose=VPC_PEERING \
    --prefix-length=16 \
    --network=$NETWORK_NAME

# 2. Create the peering connection
gcloud services vpc-peerings connect \
    --service=servicenetworking.googleapis.com \
    --ranges=google-managed-services-$NETWORK_NAME \
    --network=$NETWORK_NAME
```

### 3. Cloud SQL (Private IP)

Create the PostgreSQL instance with **only** a Private IP.

```bash
gcloud sql instances create stock-postgres-instance \
    --database-version=POSTGRES_14 \
    --cpu=2 --memory=8GiB \
    --region=$REGION \
    --network=$NETWORK_NAME \
    --no-assign-ip \
    --enable-private-path
```

*Note: `--no-assign-ip` disables the public IP. `--network` associates it with your VPC.*

After creation, get the Private IP:
```bash
export DB_PRIVATE_IP=$(gcloud sql instances describe stock-postgres-instance --format="value(ipAddresses[0].ipAddress)")
echo "Database Private IP: $DB_PRIVATE_IP"
```

### 4. Cloud Composer (Private IP)

Create the Composer environment.

```bash
gcloud composer environments create stock-airflow-env \
    --location=$REGION \
    --image-version=composer-3-airflow-2 \
    --network=$NETWORK_NAME \
    --subnetwork=$SUBNET_NAME \
    --enable-private-environment
```

### 5. Configure Airflow Connection

Once Airflow is running, you must update the `postgres_stock` connection to use the **Private IP** of the Cloud SQL instance.

1.  Open the Airflow UI.
2.  Go to **Admin > Connections**.
3.  Find or create `postgres_stock`.
4.  Set **Host** to the `DB_PRIVATE_IP` (e.g., `10.x.x.x`).
5.  Set **Schema**, **Login**, **Password**, and **Port** (5432) as configured.
6.  Save.

Alternatively, via CLI (if you have access):
```bash
gcloud composer environments run stock-airflow-env \
    --location=$REGION \
    connections add -- \
    --conn-id postgres_stock \
    --conn-type postgres \
    --conn-host $DB_PRIVATE_IP \
    --conn-schema stocks_db \
    --conn-login <YOUR_DB_USER> \
    --conn-password <YOUR_DB_PASSWORD> \
    --conn-port 5432
```

## Accessing Resources (VPN Setup)

Since the database has no public IP, you cannot connect to it directly from your laptop. You have three main options:

### Option A: Cloud VPN / Interconnect
If your organization has an on-premise network, set up **Cloud VPN** (IPsec) or **Cloud Interconnect** to the GCP VPC. This allows direct access to `10.x.x.x` IPs.

### Option B: Bastion Host (Jump Box)
Create a small VM in the same VPC/Subnet with a public IP (or use IAP).
1.  Create VM:
    ```bash
    gcloud compute instances create bastion-host \
        --network=$NETWORK_NAME \
        --subnet=$SUBNET_NAME \
        --zone=${REGION}-a
    ```
2.  SSH into Bastion:
    ```bash
    gcloud compute ssh bastion-host --zone=${REGION}-a
    ```
3.  Connect to SQL from Bastion:
    ```bash
    psql -h $DB_PRIVATE_IP -U postgres -d stocks_db
    ```
4.  **Port Forwarding** (to access from local machine):
    ```bash
    gcloud compute ssh bastion-host \
        --zone=${REGION}-a \
        -- -L 5432:$DB_PRIVATE_IP:5432
    ```
    Now you can connect local tools (DBeaver, Datagrip) to `localhost:5432`.

### Option C: IAP (Identity-Aware Proxy) TCP Forwarding
This is the most secure "lightweight" VPN alternative for developers.
1.  Enable IAP API.
2.  Create a firewall rule to allow IAP IP range (`35.235.240.0/20`) to port 22 and 5432.
3.  Use `gcloud` to tunnel:
    ```bash
    gcloud compute start-iap-tunnel bastion-host 5432 \
        --local-host-port=localhost:5432 \
        --zone=${REGION}-a
    ```

## Summary
By following these steps, your **Stock Data Pipeline** is now fully "in VPN":
- **Extraction**: Traffic flows from Composer -> NAT -> Alpha Vantage (Secure).
- **Loading**: Traffic flows from Composer -> Private Service Access -> Cloud SQL (Internal only).
- **Access**: Developers connect via VPN/Bastion/IAP Tunnel.
