output "app_ip" {
  description = "Public IPv4 of the app droplet."
  value       = digitalocean_droplet.app.ipv4_address
}

output "app_url" {
  description = "Where the app will be reachable once cloud-init finishes."
  value       = var.domain != "" ? "https://${var.domain}" : "http://${digitalocean_droplet.app.ipv4_address}"
}

output "spaces_bucket" {
  description = "Spaces bucket name for uploads/outputs."
  value       = digitalocean_spaces_bucket.files.name
}

output "spaces_endpoint" {
  description = "Spaces S3 endpoint."
  value       = "https://${var.region}.digitaloceanspaces.com"
}
