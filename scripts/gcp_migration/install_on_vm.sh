#!/bin/bash
set -e

echo "Enabling Swap Memory (Recommended for stability)..."
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

echo "Starting Airflow & MinIO (Standard Production Config)..."
# Ensure we are in the directory with docker-compose.prod.yml
if [ -f "docker-compose.prod.yml" ]; then
    # Stop existing containers to avoid port conflicts
    echo "Stopping any existing containers..."
    sudo docker compose -f docker-compose.prod.yml down --remove-orphans || true

    # Forcefully stop any containers holding our ports (fixes "port already allocated" errors from previous runs)
    for port in 5432 8080 9000 9001; do
        pids=$(sudo docker ps -q --filter "publish=$port")
        if [ -n "$pids" ]; then
            echo "Force stopping container(s) on port $port: $pids"
            sudo docker stop $pids || true
            sudo docker rm $pids || true
        fi
    done

    sudo docker compose -f docker-compose.prod.yml up -d --build
    echo "Airflow started! Access it at http://<VM_IP>:8080"
    echo "MinIO Console started! Access it at http://<VM_IP>:9001 (User: minio, Pass: minio123)"
else
    echo "Error: docker-compose.prod.yml not found. Please run this script from the project root."
fi
