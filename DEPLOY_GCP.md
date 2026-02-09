# Google Cloud Deployment Guide

This guide outlines how to deploy your Airflow project to a Google Cloud Compute Engine VM (Standard `e2-medium`) and set up continuous deployment with GitHub Actions.

## Prerequisites

1.  **Google Cloud Project**: You need an active GCP project with billing enabled.
2.  **gcloud CLI**: Install and initialize the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) on your local machine.
3.  **GitHub Repository**: Ensure your project is pushed to a GitHub repository.

## Step 1: Create the VM Instance

1.  Make sure you are authenticated with `gcloud`:
    ```bash
    gcloud auth login
    gcloud config set project YOUR_PROJECT_ID
    ```

2.  Run the creation script to provision an `e2-medium` instance (2 vCPU, 4GB RAM) with firewall rules for Airflow:
    ```bash
    bash scripts/gcp_migration/create_vm.sh
    ```
    *Note: The script outputs the Public IP of your new VM. Save this.*

## Step 2: Initial Setup on VM

1.  SSH into your new VM:
    ```bash
    gcloud compute ssh airflow-vm-standard --zone=us-west1-b
    ```

2.  Clone your repository onto the VM:
    ```bash
    git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git ~/airflow_project
    cd ~/airflow_project
    ```
    *Note: If your repo is private, use HTTPS with a Personal Access Token (PAT) or set up an SSH key on the VM and add it to your GitHub account.*

3.  Run the installation script to set up Docker, Swap Memory, and start Airflow:
    ```bash
    bash scripts/gcp_migration/install_on_vm.sh
    ```

4.  Verify deployment:
    -   Airflow UI: `http://<VM_PUBLIC_IP>:8080`
    -   MinIO Console: `http://<VM_PUBLIC_IP>:9001`

## Step 3: Configure GitHub Actions (CI/CD)

To enable automatic deployment whenever you push to the `main` branch, you need to set up a Service Account and GitHub Secrets.

### 1. Create a Service Account (GCP Console)
1.  Go to **IAM & Admin > Service Accounts**.
2.  Click **Create Service Account**. Name it `github-deployer`.
3.  Grant the role **Compute Instance Admin (v1)** (or `roles/compute.osLogin`).
4.  Create a JSON Key for this service account and download it.

### 2. Add Secrets to GitHub
Go to your GitHub repository -> **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.

Add the following secrets:

| Secret Name | Value |
| :--- | :--- |
| `GCP_PROJECT_ID` | Your Google Cloud Project ID |
| `GCP_SA_KEY` | The content of the JSON key file you downloaded |
| `GCP_VM_INSTANCE` | `airflow-vm-standard` |
| `GCP_VM_ZONE` | `us-west1-b` |
| `POSTGRES_USER` | Database user (e.g., `postgres`) |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_DB` | Database name (e.g., `postgres`) |
| `MINIO_ROOT_USER` | MinIO root user |
| `MINIO_ROOT_PASSWORD` | MinIO root password |

### 3. Workflow Behavior
The included workflow `.github/workflows/deploy.yml` will:
1.  Authenticate to Google Cloud using the Service Account.
2.  SSH into the VM.
3.  Pull the latest code from the `main` branch.
4.  Rebuild and restart the Docker containers.

## Maintenance
-   **Logs**: `docker compose -f docker-compose.prod.yml logs -f`
-   **Stop**: `docker compose -f docker-compose.prod.yml down`

## Troubleshooting

### Unable to connect via SSH
If you cannot SSH into the VM (`gcloud compute ssh ...` fails or times out):

1.  **Check Firewall Rules**: Ensure port 22 is open.
    ```bash
    gcloud compute firewall-rules list --filter="name=allow-airflow-http"
    ```
    You should see `tcp:22` in the `allow` column. If not, re-run `scripts/gcp_migration/create_vm.sh` to update the rule.

2.  **Use IAP Tunneling**: If you are on a restricted network or the VM lacks a public IP, try using Identity-Aware Proxy (IAP):
    ```bash
    gcloud compute ssh airflow-vm-standard --zone=us-west1-b --tunnel-through-iap
    ```

3.  **Check OS Login**: Ensure you have permissions to log in.
    ```bash
    gcloud compute os-login describe-profile
    ```

### Port Conflict (e.g., Bind for 0.0.0.0:9000 failed)
If deployment fails with "port is already allocated", another process or a previous Docker container might still be running.
Run the following to clean up before retrying:
```bash
docker compose -f docker-compose.prod.yml down --remove-orphans
bash scripts/gcp_migration/install_on_vm.sh
```
