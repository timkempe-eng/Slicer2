locals {
  name = var.basename
}

# A tag applied to everything so the resources group cleanly in the DO console
# and can be referenced by the database firewall.
resource "digitalocean_tag" "this" {
  name = local.name
}

# Groups all resources under one DO Project.
resource "digitalocean_project" "this" {
  name        = local.name
  description = "Slicer2 — cloud slicing & delivery service for Bambu Lab."
  purpose     = "Web Application"
  environment = "Production"
  resources = [
    digitalocean_droplet.app.urn,
    digitalocean_database_cluster.pg.urn,
    digitalocean_spaces_bucket.files.urn,
  ]
}
