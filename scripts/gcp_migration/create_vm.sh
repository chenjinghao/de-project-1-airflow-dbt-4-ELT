#!/bin/bash
set -e

# Configuration
INSTANCE_NAME="airflow-vm-standard"
ZONE="us-west1-b" # Oregon (Free Tier eligible)
MACHINE_TYPE="e2-medium" # Standard (2 vCPU, 4 GB RAM)
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_FAMILY="ubuntu-2204-lts"
DISK_SIZE="30GB" # Free Tier eligible (up to 30GB)

echo "Creating Standard VM instance $INSTANCE_NAME in $ZONE..."
gcloud compute instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --image-project=$IMAGE_PROJECT \
    --image-family=$IMAGE_FAMILY \
    --boot-disk-size=$DISK_SIZE \
    --boot-disk-type=pd-standard \
    --tags=airflow-server,http-server

echo "Creating firewall rule to allow port 22 (SSH), 8080 (Airflow), 9001 (MinIO) and 5432 (Postgres)..."
# Check if rule exists first to avoid error
if ! gcloud compute firewall-rules describe allow-airflow-http &>/dev/null; then
    gcloud compute firewall-rules create allow-airflow-http \
        --allow tcp:22,tcp:8080,tcp:9001,tcp:5432 \
        --target-tags=airflow-server \
        --description="Allow SSH, Airflow, MinIO, and Postgres access"
else
    # Update existing rule to include 22, 5432, 9001
    echo "Updating existing firewall rule allow-airflow-http..."
    gcloud compute firewall-rules update allow-airflow-http \
        --allow tcp:22,tcp:8080,tcp:9001,tcp:5432
fi

echo "VM Creation Complete!"
echo "Public IP:"
gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

echo ""
echo "Next Steps:"
echo "1. Upload your project files to the VM."
echo "2. SSH into the VM: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo "3. Run the installation script: bash scripts/gcp_migration/install_on_vm.sh"
echo "4. IMPORTANT: Change your Postgres password in docker-compose.prod.yml before going live!"
