@echo off
REM Startup script for Airflow project on VM with limited resources

echo Starting Airflow on VM with limited resources...

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

echo Building and starting Airflow services...
docker compose -f docker-compose.vm-minimal.yml up --build -d

echo Waiting for services to start...
timeout /t 30 /nobreak

echo Checking running containers...
docker ps

echo.
echo Airflow should be available at http://localhost:8080
echo Username: admin
echo Password: admin
echo.
echo To view logs: docker compose -f docker-compose.vm-minimal.yml logs -f
echo To stop services: docker compose -f docker-compose.vm-minimal.yml down
echo.
pause