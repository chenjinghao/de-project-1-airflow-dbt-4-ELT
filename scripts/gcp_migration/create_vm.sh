#!/bin/bash
set -e

# Configuration
INSTANCE_NAME="project-de-stock"
ZONE="us-west1-b" # Oregon (Free Tier eligible)
MACHINE_TYPE="e2-medium" # Standard (2 vCPU, 4 GB RAM)
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_FAMILY="ubuntu-2204-lts"
DISK_SIZE="30GB" # Free Tier eligible (up to 30GB)

if gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE &>/dev/null; then
    echo "Instance $INSTANCE_NAME already exists. Skipping creation."
else
    echo "Creating Standard VM instance $INSTANCE_NAME in $ZONE..."
    gcloud compute instances create $INSTANCE_NAME \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --image-project=$IMAGE_PROJECT \
        --image-family=$IMAGE_FAMILY \
        --boot-disk-size=$DISK_SIZE \
        --boot-disk-type=pd-standard \
        --tags=project-de-stock,http-server
fi

# Ensure tags are applied (in case VM existed but lacked tags)
echo "Ensuring VM tags are set..."
gcloud compute instances add-tags $INSTANCE_NAME --zone=$ZONE --tags=project-de-stock,http-server --quiet || true

echo "Creating firewall rule to allow port 22 (SSH), 8080 (Airflow) and 5432 (Postgres)..."
# Check if rule exists first to avoid error
if ! gcloud compute firewall-rules describe allow-airflow-http &>/dev/null; then
    gcloud compute firewall-rules create allow-airflow-http \
        --allow tcp:22,tcp:8080,tcp:5432 \
        --target-tags=project-de-stock \
        --source-ranges=0.0.0.0/0 \
        --description="Allow SSH, Airflow and Postgres access"
else
    # Update existing rule to include 5432 and 22
    echo "Updating existing firewall rule allow-airflow-http..."
    gcloud compute firewall-rules update allow-airflow-http \
        --allow tcp:22,tcp:8080,tcp:5432 \
        --target-tags=project-de-stock \
        --source-ranges=0.0.0.0/0
fi

echo "VM Creation Complete!"
echo "Public IP:"
gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

echo ""
echo "Next Steps:"
echo "1. Upload your project files to the VM."
echo "2. SSH into the VM: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo "   (If connection fails, try: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --tunnel-through-iap)"
echo "3. Run the installation script: bash scripts/gcp_migration/install_on_vm.sh"
echo "4. IMPORTANT: Change your Postgres password in docker-compose.prod.yml before going live!"
