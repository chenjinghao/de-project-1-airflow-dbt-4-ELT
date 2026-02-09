output "instance_name" {
  description = "Name of the created VM instance"
  value       = google_compute_instance.airflow_vm.name
}

output "instance_zone" {
  description = "Zone of the created VM instance"
  value       = google_compute_instance.airflow_vm.zone
}

output "public_ip" {
  description = "Public IP address of the VM instance"
  value       = google_compute_instance.airflow_vm.network_interface[0].access_config[0].nat_ip
}

output "airflow_url" {
  description = "URL to access Airflow web UI"
  value       = "http://${google_compute_instance.airflow_vm.network_interface[0].access_config[0].nat_ip}:${var.allow_airflow_port}"
}

output "minio_console_url" {
  description = "URL to access MinIO console"
  value       = "http://${google_compute_instance.airflow_vm.network_interface[0].access_config[0].nat_ip}:${var.allow_minio_console_port}"
}

output "postgres_connection" {
  description = "Postgres connection string"
  value       = "${google_compute_instance.airflow_vm.network_interface[0].access_config[0].nat_ip}:${var.allow_postgres_port}"
}

output "ssh_command" {
  description = "Command to SSH into the VM instance"
  value       = "gcloud compute ssh ${google_compute_instance.airflow_vm.name} --zone=${google_compute_instance.airflow_vm.zone}"
}
