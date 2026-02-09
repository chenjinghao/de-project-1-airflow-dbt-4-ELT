# Terraform Configuration for Airflow on GCP

This directory contains Terraform configuration to provision infrastructure for running Airflow on Google Cloud Platform (GCP) using a Free Tier eligible VM.

## Prerequisites

1. **Terraform**: Install Terraform (version >= 1.0)
   ```bash
   # On macOS
   brew install terraform
   
   # On Ubuntu/Debian
   wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
   echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
   sudo apt update && sudo apt install terraform
   ```

2. **Google Cloud SDK**: Install and authenticate
   ```bash
   # Install gcloud CLI
   # https://cloud.google.com/sdk/docs/install
   
   # Authenticate
   gcloud auth application-default login
   
   # Set your project
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **GCP Project**: Have a GCP project with billing enabled

## Infrastructure Components

This Terraform configuration creates:

- **Compute Instance**: e2-micro VM (Free Tier eligible)
  - 2 vCPU, 1 GB RAM
  - 30GB Standard persistent disk
  - Ubuntu 22.04 LTS
  - Swap memory configuration for low-memory optimization
  - Docker and Docker Compose pre-installed

- **Firewall Rules**: Allow traffic on:
  - Port 8080 (Airflow web UI)
  - Port 5432 (PostgreSQL)
  - Port 9000 (MinIO API)
  - Port 9001 (MinIO Console)

## Quick Start

1. **Create your variables file**:
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit `terraform.tfvars`** with your GCP project ID:
   ```hcl
   project_id = "your-gcp-project-id"
   ```

3. **Initialize Terraform**:
   ```bash
   terraform init
   ```

4. **Review the plan**:
   ```bash
   terraform plan
   ```

5. **Apply the configuration**:
   ```bash
   terraform apply
   ```

6. **Get outputs** (VM IP, SSH command, URLs):
   ```bash
   terraform output
   ```

## Deployment Steps After Infrastructure Creation

After Terraform creates your infrastructure:

1. **SSH into the VM**:
   ```bash
   # Use the SSH command from terraform output
   gcloud compute ssh airflow-vm-free-tier --zone=us-west1-b
   ```

2. **Clone your project** (on the VM):
   ```bash
   cd ~
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```

3. **Create `.env` file** with your secrets:
   ```bash
   cat > .env << EOF
   POSTGRES_USER=airflow
   POSTGRES_PASSWORD=your-secure-password
   POSTGRES_DB=airflow
   MINIO_ROOT_USER=minio
   MINIO_ROOT_PASSWORD=your-minio-password
   EOF
   ```

4. **Start Airflow**:
   ```bash
   sudo docker compose -f docker-compose.prod.yml up -d --build
   ```

5. **Access Airflow**:
   - Navigate to the Airflow URL from `terraform output airflow_url`
   - Default credentials: admin / admin

## Configuration Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `project_id` | GCP Project ID | - | Yes |
| `region` | GCP Region | us-west1 | No |
| `zone` | GCP Zone | us-west1-b | No |
| `instance_name` | VM instance name | airflow-vm-free-tier | No |
| `machine_type` | VM machine type | e2-micro | No |
| `disk_size_gb` | Boot disk size | 30 | No |

## Outputs

After applying, Terraform provides:

- `instance_name`: Name of the VM
- `instance_zone`: Zone where VM is deployed
- `public_ip`: Public IP address
- `airflow_url`: Direct URL to Airflow UI
- `minio_console_url`: Direct URL to MinIO Console
- `postgres_connection`: PostgreSQL connection endpoint
- `ssh_command`: Command to SSH into the VM

## Destroying Infrastructure

To tear down all resources:

```bash
terraform destroy
```

## Cost Considerations

This configuration uses GCP Free Tier eligible resources:

- **e2-micro instance**: 1 instance free per month in us-west1, us-central1, or us-east1
- **30GB standard persistent disk**: Within free tier limits
- **Egress**: First 1 GB per month is free

**Important**: Monitor your GCP billing to ensure you stay within free tier limits.

## Comparison with Bash Scripts

This Terraform configuration replaces the bash scripts in `scripts/gcp_migration/`:

- `create_vm.sh` → Terraform manages VM creation
- `install_on_vm.sh` → Startup script in compute.tf

**Benefits of Terraform**:
- Infrastructure as Code (version controlled)
- Declarative configuration
- State management
- Easy to replicate environments
- Plan before apply
- Automatic dependency management

## Troubleshooting

**Issue**: `terraform init` fails
- **Solution**: Ensure you're in the `terraform/` directory

**Issue**: Permission denied errors
- **Solution**: Run `gcloud auth application-default login`

**Issue**: Quota exceeded
- **Solution**: Check your GCP quotas and request increases if needed

**Issue**: VM not accessible
- **Solution**: Check firewall rules and VM status in GCP Console

## Next Steps

After successful deployment:

1. Set up GitHub Actions for CI/CD (see `.github/workflows/`)
2. Configure monitoring and alerting
3. Set up automated backups for PostgreSQL data
4. Implement SSL/TLS for production use
5. Restrict firewall rules to specific IP ranges

## Support

For issues related to:
- Terraform: Check [Terraform documentation](https://www.terraform.io/docs)
- GCP: Check [GCP documentation](https://cloud.google.com/docs)
- This project: Open an issue in the repository
