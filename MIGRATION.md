# Migration Guide: Cloud Composer to Compute Engine

This guide details how to migrate your Airflow environment from Google Cloud Composer (High Cost) to a single Compute Engine VM (Low Cost).

**Expected Savings:** ~$450/month -> ~$50/month.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated on your local machine.
- This repository cloned locally.

## Step 1: Create the VM Infrastructure

We will create a cost-effective `e2-standard-2` VM in the `us-west1` region (Oregon).

1. Open a terminal in the root of this project.
2. Run the creation script:
   ```bash
   ./scripts/gcp_migration/create_vm.sh
   ```
3. Note the **Public IP** output at the end of the script. You will need this to access Airflow.

## Step 2: Deploy Code to the VM

We need to copy your project files to the new VM.

1. SSH into the VM to verify it works (and add the key to your known_hosts):
   ```bash
   gcloud compute ssh airflow-vm --zone=us-west1-b
   ```
   (Type `exit` to disconnect after logging in successfully).

2. Copy the project files to the VM using `gcloud compute scp`. Run this from your local machine:
   ```bash
   # Compresses and copies the current directory to the VM
   gcloud compute scp --recurse . airflow-vm:~/airflow_project --zone=us-west1-b
   ```

## Step 3: Install & Start Airflow

1. SSH into the VM again:
   ```bash
   gcloud compute ssh airflow-vm --zone=us-west1-b
   ```

2. Go to the project directory:
   ```bash
   cd airflow_project
   ```

3. Run the installation script. This will install Docker and start Airflow:
   ```bash
   sudo ./scripts/gcp_migration/install_on_vm.sh
   ```

4. Wait for a few minutes for the images to build and containers to start.

## Step 4: Access & Verify

1. Open your browser and navigate to:
   - **Airflow UI**: `http://<VM_PUBLIC_IP>:8080` (User: `admin`, Password: `admin`)
   - **Metabase**: `http://<VM_PUBLIC_IP>:3000`

2. Check if your DAGs are visible and running.
3. **Important**: If your DAGs connect to external services (like Slack), verify you have set the connections in the Airflow UI (Admin -> Connections) or added them to `docker-compose.prod.yml`.

## Step 5: DECOMISSION OLD RESOURCES (Crucial!)

Once you have verified the new setup is working, **DELETE** the old resources to stop the billing.

1. **Delete Cloud Composer Environment**:
   - Go to [Console > Composer](https://console.cloud.google.com/composer/environments).
   - Select your environment.
   - Click **DELETE**.

2. **Delete Cloud SQL Instance**:
   - Go to [Console > SQL](https://console.cloud.google.com/sql/instances).
   - Select your old instance (`db-custom-4...`).
   - Click **DELETE**.

3. **Delete Old Storage Buckets**:
   - Composer creates a GCS bucket (e.g., `us-west1-...-bucket`).
   - Go to [Console > Cloud Storage](https://console.cloud.google.com/storage/browser).
   - Delete the bucket associated with the old Composer environment.

## Managing the New Setup

- **Restarting services**:
  ```bash
  cd ~/airflow_project
  sudo docker compose -f docker-compose.prod.yml restart
  ```
- **Viewing logs**:
  ```bash
  sudo docker compose -f docker-compose.prod.yml logs -f
  ```
- **Updating code**:
  1. Copy new files to VM (`gcloud compute scp`).
  2. SSH in and rebuild:
     ```bash
     sudo docker compose -f docker-compose.prod.yml up -d --build
     ```
