#!/bin/bash
set -e

echo "Installing Docker..."
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
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

echo "Starting Airflow..."
# Ensure we are in the directory with docker-compose.prod.yml
if [ -f "docker-compose.prod.yml" ]; then
    sudo docker compose -f docker-compose.prod.yml up -d --build
    echo "Airflow started! Access it at http://<VM_IP>:8080"
    echo "Metabase started! Access it at http://<VM_IP>:3000"
else
    echo "Error: docker-compose.prod.yml not found. Please run this script from the project root."
fi
