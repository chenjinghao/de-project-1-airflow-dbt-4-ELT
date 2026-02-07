#!/bin/bash
set -e

echo "Enabling Swap Memory (Critical for e2-micro)..."
# Create a 2GB swapfile
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    # Persist swap
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap enabled."
else
    echo "Swap already enabled."
fi

echo "Installing Docker..."
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Docker installed."

echo "Preparing directories..."
# Ensure permissions for mapped volumes
mkdir -p logs plugins include dags
# Usually mapped volumes are owned by root if created by docker, but we can pre-create them.
# The container runs as 'astro' (uid 50000).
sudo chown -R 50000:0 logs plugins include dags

echo "Starting Airflow & MinIO (Free Tier Optimized)..."
# Ensure we are in the directory with docker-compose.prod.yml
if [ -f "docker-compose.prod.yml" ]; then
    sudo docker compose -f docker-compose.prod.yml up -d --build
    echo "Airflow started! Access it at http://<VM_IP>:8080"
    echo "MinIO Console started! Access it at http://<VM_IP>:9001 (User: minio, Pass: minio123)"
else
    echo "Error: docker-compose.prod.yml not found. Please run this script from the project root."
fi
