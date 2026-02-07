# Migration Guide: Cloud Composer to Compute Engine (Free Tier Optimized)

This guide details how to migrate your Airflow environment from Google Cloud Composer (High Cost) to a Google Cloud Free Tier VM (`e2-micro`).

**Expected Savings:** ~$450/month -> **$0/month** (or very close to zero).

**Trade-offs:**
- The server has limited memory (1GB RAM).
- We removed Metabase to save resources.
- It may be slower than Composer, but sufficient for daily personal DAGs.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated on your local machine.
- This repository cloned locally.

## Step 1: Create the Free Tier VM Infrastructure

We will create an `e2-micro` VM in `us-west1` (Oregon) with a 30GB standard disk, which qualifies for the Free Tier.

1. Open a terminal in the root of this project.
2. Run the creation script:
   ```bash
   ./scripts/gcp_migration/create_vm.sh
   ```
3. Note the **Public IP** output at the end of the script.

## Step 2: Deploy Code to the VM

1. SSH into the VM (and add key to known_hosts):
   ```bash
   gcloud compute ssh airflow-vm-free-tier --zone=us-west1-b
   ```
   (Type `exit` to disconnect).

2. Copy project files to the VM:
   ```bash
   # Compresses and copies the current directory to the VM
   gcloud compute scp --recurse . airflow-vm-free-tier:~/airflow_project --zone=us-west1-b
   ```

## Step 3: Install & Start Airflow

1. SSH into the VM again:
   ```bash
   gcloud compute ssh airflow-vm-free-tier --zone=us-west1-b
   ```

2. Go to the project directory:
   ```bash
   cd airflow_project
   ```

3. Run the installation script. This will:
   - **Create a 2GB Swap File** (Critical for preventing crashes on 1GB RAM).
   - Install Docker.
   - Start Airflow.
   ```bash
   sudo ./scripts/gcp_migration/install_on_vm.sh
   ```

4. Wait 5-10 minutes. The first start takes time on a micro instance.

## Step 4: Access & Verify

1. Open your browser: `http://<VM_PUBLIC_IP>:8080` (User: `admin`, Password: `admin`)
2. Verify your DAGs.

## Step 5: DECOMISSION OLD RESOURCES (Crucial!)

**DELETE** the old resources to stop the billing immediately.

1. **Delete Cloud Composer Environment** (Console > Composer).
2. **Delete Cloud SQL Instance** (Console > SQL).
3. **Delete Old Storage Buckets** (Console > Cloud Storage).

## Tips for Low Memory Environment
- If the server becomes unresponsive, restart it from the Google Cloud Console.
- To view logs: `sudo docker compose -f docker-compose.prod.yml logs -f --tail 50`
- To restart Airflow: `sudo docker compose -f docker-compose.prod.yml restart`
