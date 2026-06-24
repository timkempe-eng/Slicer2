# DigitalOcean-hosted DNS for the app domain.
#
# Terraform manages the domain and A records here so that every `terraform apply`
# (i.e. every thaw) automatically points slicedbambu.com at the new droplet IP.
# No manual DNS edits are needed after the one-time nameserver change below.
#
# ONE-TIME SETUP — change slicedbambu.com's nameservers at GoDaddy:
#   GoDaddy → My Products → slicedbambu.com → DNS → Nameservers → Change
#   → Enter my own nameservers:
#       ns1.digitalocean.com
#       ns2.digitalocean.com
#       ns3.digitalocean.com
# After that, every freeze/thaw cycle is fully automatic.

resource "digitalocean_domain" "app" {
  count = var.domain != "" ? 1 : 0
  name  = var.domain
}

resource "digitalocean_record" "apex_a" {
  count  = var.domain != "" ? 1 : 0
  domain = digitalocean_domain.app[0].id
  type   = "A"
  name   = "@"
  value  = digitalocean_droplet.app.ipv4_address
  ttl    = 300
}

resource "digitalocean_record" "www_a" {
  count  = var.domain != "" ? 1 : 0
  domain = digitalocean_domain.app[0].id
  type   = "A"
  name   = "www"
  value  = digitalocean_droplet.app.ipv4_address
  ttl    = 300
}
