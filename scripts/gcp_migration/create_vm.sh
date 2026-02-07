#!/bin/bash
set -e

# Configuration
INSTANCE_NAME="airflow-vm-free-tier"
ZONE="us-west1-b" # Oregon (Free Tier eligible)
MACHINE_TYPE="e2-micro" # Free Tier eligible (2 vCPU, 1 GB RAM)
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_FAMILY="ubuntu-2204-lts"
DISK_SIZE="30GB" # Free Tier eligible (up to 30GB)

echo "Creating Free Tier VM instance $INSTANCE_NAME in $ZONE..."
gcloud compute instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --image-project=$IMAGE_PROJECT \
    --image-family=$IMAGE_FAMILY \
    --boot-disk-size=$DISK_SIZE \
    --boot-disk-type=pd-standard \
    --tags=airflow-server,http-server

echo "Creating firewall rule to allow port 8080 (Airflow)..."
# Check if rule exists first to avoid error
if ! gcloud compute firewall-rules describe allow-airflow-http &>/dev/null; then
    gcloud compute firewall-rules create allow-airflow-http \
        --allow tcp:8080 \
        --target-tags=airflow-server \
        --description="Allow Airflow access"
else
    echo "Firewall rule allow-airflow-http already exists."
fi

echo "VM Creation Complete!"
echo "Public IP:"
gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

echo ""
echo "Next Steps:"
echo "1. Upload your project files to the VM."
echo "2. SSH into the VM: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo "3. Run the installation script: bash scripts/gcp_migration/install_on_vm.sh"
