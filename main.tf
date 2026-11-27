terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-north-1"
}

# 1. Security Group
resource "aws_security_group" "open_webui_sg" {
  name        = "open-webui-sg"
  description = "Allow SSH, HTTP, HTTPS"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["146.52.70.180/32"]
  }

  # HTTP (For Let's Encrypt/Caddy)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS (For the public web)
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 2. Find the latest Ubuntu 22.04 AMI automatically
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# 3. Elastic IP, allocated up front so we know its address before the
# instance boots (needed to build the nip.io hostname for TLS below).
resource "aws_eip" "open_webui_ip" {
  domain = "vpc"
}

locals {
  # e.g. 3.123.45.67 -> 3-123-45-67.nip.io, a real hostname that resolves
  # to this IP, so Let's Encrypt can issue a genuine cert with no domain
  # purchase or DNS setup needed.
  webui_domain = "${replace(aws_eip.open_webui_ip.public_ip, ".", "-")}.nip.io"
}

# 4. EC2 Instance with User Data (Bootstrapping)
resource "aws_instance" "open_webui" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "m7i-flex.large"
  key_name               = "chapters" # MUST MATCH the name of your .pem file in AWS
  vpc_security_group_ids = [aws_security_group.open_webui_sg.id]

  root_block_device {
    volume_size = 20 # 20GB is safer for Docker images
  }

  # This script runs automatically the first time the server boots
  user_data = <<-EOF
              #!/bin/bash
              # Install Docker
              curl -fsSL https://get.docker.com -o get-docker.sh
              sh get-docker.sh
              
              # Create Open WebUI directory
              mkdir -p /opt/open-webui
              cd /opt/open-webui

              # Docker Compose file, defined in docker-compose.yml alongside this config
              cat <<'EOT' > docker-compose.yml
              ${file("${path.module}/docker-compose.yml")}
              EOT

              # Generate the secret; docker compose substitutes it into
              # docker-compose.yml's $${WEBUI_SECRET_KEY} from this exported var
              export WEBUI_SECRET_KEY=$(openssl rand -hex 32)

              # Start Open WebUI
              docker compose up -d

              # Install Caddy for HTTPS
              apt install -y debian-keyring debian-archive-keyring apt-transport-https
              curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
              curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
              apt update
              apt install -y caddy

              # Configure Caddy to proxy to Open WebUI and fetch SSL
              cat <<EOT > /etc/caddy/Caddyfile
              ${local.webui_domain} {
                  reverse_proxy localhost:8080
              }
              EOT

              systemctl restart caddy
              EOF

  tags = {
    Name = "OpenWebUI-Terraform"
  }
}

# 5. Associate the pre-allocated Elastic IP with the instance
resource "aws_eip_association" "open_webui_eip_assoc" {
  instance_id   = aws_instance.open_webui.id
  allocation_id = aws_eip.open_webui_ip.id
}

output "instance_public_ip" {
  value = aws_eip.open_webui_ip.public_ip
}

output "webui_url" {
  value = "https://${local.webui_domain}"
}