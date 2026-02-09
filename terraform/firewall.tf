resource "google_compute_firewall" "allow_airflow_http" {
  name    = "allow-airflow-http"
  network = "default"

  allow {
    protocol = "tcp"
    ports = [
      tostring(var.allow_airflow_port),
      tostring(var.allow_postgres_port),
      tostring(var.allow_minio_port),
      tostring(var.allow_minio_console_port)
    ]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["airflow-server"]

  description = "Allow Airflow, Postgres, and MinIO access"
}
