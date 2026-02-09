variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-west1"
}

variable "zone" {
  description = "GCP Zone for the VM instance"
  type        = string
  default     = "us-west1-b"
}

variable "instance_name" {
  description = "Name of the VM instance"
  type        = string
  default     = "airflow-vm-free-tier"
}

variable "machine_type" {
  description = "Machine type for the VM (e2-micro is free tier eligible)"
  type        = string
  default     = "e2-micro"
}

variable "disk_size_gb" {
  description = "Boot disk size in GB (up to 30GB is free tier eligible)"
  type        = number
  default     = 30
}

variable "image_project" {
  description = "Project containing the OS image"
  type        = string
  default     = "ubuntu-os-cloud"
}

variable "image_family" {
  description = "OS image family"
  type        = string
  default     = "ubuntu-2204-lts"
}

variable "allow_airflow_port" {
  description = "Port for Airflow web UI"
  type        = number
  default     = 8080
}

variable "allow_postgres_port" {
  description = "Port for Postgres database"
  type        = number
  default     = 5432
}

variable "allow_minio_port" {
  description = "Port for MinIO API"
  type        = number
  default     = 9000
}

variable "allow_minio_console_port" {
  description = "Port for MinIO Console"
  type        = number
  default     = 9001
}

variable "environment" {
  description = "Environment label for the infrastructure (e.g., development, staging, production)"
  type        = string
  default     = "development"
}

variable "allowed_source_ranges" {
  description = "CIDR blocks allowed to access the services. Default allows all IPs - RESTRICT THIS IN PRODUCTION!"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
