#!/bin/bash
set -e

# Configuration
INSTANCE_NAME="airflow-vm"
ZONE="us-west1-b" # Default to Oregon as per user's previous setup
MACHINE_TYPE="e2-standard-2"
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_FAMILY="ubuntu-2204-lts"

echo "Creating VM instance $INSTANCE_NAME in $ZONE..."
gcloud compute instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --image-project=$IMAGE_PROJECT \
    --image-family=$IMAGE_FAMILY \
    --tags=airflow-server,http-server

echo "Creating firewall rule to allow port 8080 (Airflow) and 3000 (Metabase)..."
# Check if rule exists first to avoid error
if ! gcloud compute firewall-rules describe allow-airflow-metabase &>/dev/null; then
    gcloud compute firewall-rules create allow-airflow-metabase \
        --allow tcp:8080,tcp:3000 \
        --target-tags=airflow-server \
        --description="Allow Airflow and Metabase access"
else
    echo "Firewall rule allow-airflow-metabase already exists."
fi

echo "VM Creation Complete!"
echo "Public IP:"
gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

echo ""
echo "Next Steps:"
echo "1. Upload your project files to the VM."
echo "2. SSH into the VM: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo "3. Run the installation script: bash scripts/gcp_migration/install_on_vm.sh"
