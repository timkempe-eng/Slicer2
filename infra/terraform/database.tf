# Managed PostgreSQL: durable store for job records, Stripe payment history,
# and the clickwrap consent/liability log (PRD §6).
resource "digitalocean_database_cluster" "pg" {
  name       = "${local.name}-pg"
  engine     = "pg"
  version    = "16"
  size       = var.db_size_slug
  region     = var.region
  node_count = var.db_node_count
  tags       = [digitalocean_tag.this.id]
}

resource "digitalocean_database_db" "app" {
  cluster_id = digitalocean_database_cluster.pg.id
  name       = "slicer2"
}

resource "digitalocean_database_user" "app" {
  cluster_id = digitalocean_database_cluster.pg.id
  name       = "slicer2"
}

# Only allow the app droplet (by tag) to reach the database.
resource "digitalocean_database_firewall" "pg" {
  cluster_id = digitalocean_database_cluster.pg.id

  rule {
    type  = "tag"
    value = digitalocean_tag.this.name
  }
}
