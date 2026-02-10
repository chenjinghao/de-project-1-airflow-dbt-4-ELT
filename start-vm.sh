#!/bin/bash
# Startup script for Airflow project on VM with limited resources

echo "Starting Airflow on VM with limited resources..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker first."
    exit 1
fi

echo "Building and starting Airflow services..."
docker compose -f docker-compose.vm-minimal.yml up --build -d

echo "Waiting for services to start..."
sleep 30

echo "Checking running containers..."
docker ps

echo
echo "Airflow should be available at http://localhost:8080"
echo "Username: admin"
echo "Password: admin"
echo
echo "To view logs: docker compose -f docker-compose.vm-minimal.yml logs -f"
echo "To stop services: docker compose -f docker-compose.vm-minimal.yml down"
echo