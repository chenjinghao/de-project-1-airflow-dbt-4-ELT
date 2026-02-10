resource "google_compute_instance" "airflow_vm" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone

  tags = ["airflow-server", "http-server"]

  boot_disk {
    initialize_params {
      image = "${var.image_project}/${var.image_family}"
      size  = var.disk_size_gb
      type  = "pd-standard"
    }
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  # Startup script to prepare the VM
  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -e
    
    # Enabling Swap Memory (Critical for e2-micro)
    if [ ! -f /swapfile ]; then
      fallocate -l 2G /swapfile
      chmod 600 /swapfile
      mkswap /swapfile
      swapon /swapfile
      echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    
    # Install Docker if not already installed
    if ! command -v docker &> /dev/null; then
      # Add Docker's official GPG key
      apt-get update
      apt-get install -y ca-certificates curl gnupg
      install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      chmod a+r /etc/apt/keyrings/docker.gpg
      
      # Add the repository to Apt sources
      echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
      apt-get update
      
      apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    fi
    
    # Prepare directories with proper permissions
    # UID 50000 is the default Airflow container user (astro)
    # GID 0 is the root group which allows proper access
    mkdir -p /opt/airflow/{logs,plugins,include,dags}
    chown -R 50000:0 /opt/airflow/{logs,plugins,include,dags}
  EOF

  labels = {
    environment = var.environment
    application = "airflow"
  }

  # Allow the instance to be stopped/restarted when updating
  allow_stopping_for_update = true
}
