# Migration Guide: Cloud Composer to Compute Engine (Free Tier Optimized)

This guide details how to migrate your Airflow environment from Google Cloud Composer (High Cost) to a Google Cloud Free Tier VM (`e2-micro`).

**Expected Savings:** ~$450/month -> **$0/month** (or very close to zero).

**Trade-offs:**
- The server has limited memory (1GB RAM).
- We removed Metabase to save resources.
- We added MinIO (local S3-compatible storage) to replace Google Cloud Storage for data processing.

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
   *(Alternatively, clone from your GitHub repository directly on the VM).*

## Step 3: Install & Start Airflow + MinIO

1. SSH into the VM again:
   ```bash
   gcloud compute ssh airflow-vm-free-tier --zone=us-west1-b
   ```

2. Go to the project directory:
   ```bash
   cd airflow_project
   ```

3. **Update Dockerfile (If needed):**
   If you are using Airflow 3 features, edit the `Dockerfile` to use the correct image (e.g., `astrocrpublic.azurecr.io/runtime:3.1-12`).
   ```bash
   nano Dockerfile
   ```

4. **Run the installation script.** This will:
   - **Create a 2GB Swap File** (Critical for preventing crashes on 1GB RAM).
   - Install Docker.
   - Start Airflow and MinIO.
   ```bash
   chmod +x scripts/gcp_migration/install_on_vm.sh
   sudo ./scripts/gcp_migration/install_on_vm.sh
   ```

5. Wait 5-10 minutes. The first start takes time on a micro instance.

## Step 4: Access & Verify

1. **Airflow UI**: `http://<VM_PUBLIC_IP>:8080` (User: `admin`, Password: `admin`)
2. **MinIO Console**: `http://<VM_PUBLIC_IP>:9001` (User: `minio`, Password: `minio123`)

**Note:** You might need to open port 9001 in the firewall if you want to access the MinIO UI from your browser (currently only 8080 is opened by the script).
To open MinIO port:
```bash
gcloud compute firewall-rules create allow-minio --allow tcp:9001 --target-tags=airflow-server
```

## Step 5: DECOMISSION OLD RESOURCES (Crucial!)

**DELETE** the old resources to stop the billing immediately.

1. **Delete Cloud Composer Environment** (Console > Composer).
2. **Delete Cloud SQL Instance** (Console > SQL).
3. **Delete Old Storage Buckets** (Console > Cloud Storage).

## Tips for Low Memory Environment
- If the server becomes unresponsive, restart it from the Google Cloud Console.
- To view logs: `sudo docker compose -f docker-compose.prod.yml logs -f --tail 50`
- To restart Airflow: `sudo docker compose -f docker-compose.prod.yml restart`
