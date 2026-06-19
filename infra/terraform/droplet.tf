# The application droplet: runs the FastAPI app, the in-process slicer, and
# Redis via docker-compose. Provisioned from a stock Ubuntu image; cloud-init
# installs Docker and brings the stack up.
resource "digitalocean_droplet" "app" {
  name     = "${local.name}-app"
  image    = var.droplet_image
  region   = var.region
  size     = var.droplet_size_slug
  ssh_keys = var.ssh_key_ids
  tags     = [digitalocean_tag.this.id]

  monitoring = true

  user_data = templatefile("${path.module}/files/cloud-init.yaml", {
    git_repo              = var.git_repo
    git_ref               = var.git_ref
    domain                = var.domain
    database_url          = digitalocean_database_cluster.pg.private_uri
    spaces_region         = var.region
    spaces_bucket         = digitalocean_spaces_bucket.files.name
    spaces_access_id      = var.spaces_access_id
    spaces_secret_key     = var.spaces_secret_key
    stripe_secret_key     = var.stripe_secret_key
    stripe_webhook_secret = var.stripe_webhook_secret
  })
}

# Cloud firewall: SSH + HTTP/HTTPS only.
resource "digitalocean_firewall" "app" {
  name        = "${local.name}-fw"
  droplet_ids = [digitalocean_droplet.app.id]
  tags        = [digitalocean_tag.this.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = var.ssh_source_addresses
  }
  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }
  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
