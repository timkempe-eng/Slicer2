# DigitalOcean-hosted DNS for the app domain.
#
# Having DNS here means every `terraform apply` (i.e. every thaw) automatically
# updates the A records to the new droplet IP, so slicedbambu.com just works
# after a freeze/thaw with no manual DNS edits.
#
# One-time prerequisite: point slicedbambu.com's nameservers at DigitalOcean at
# your registrar (GoDaddy → Manage DNS → Nameservers → Custom):
#   ns1.digitalocean.com
#   ns2.digitalocean.com
#   ns3.digitalocean.com
# After that, every thaw is fully automatic.

resource "digitalocean_domain" "app" {
  count = var.domain != "" ? 1 : 0
  name  = var.domain
}

# --- Web traffic -------------------------------------------------------

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

# --- Mailgun email (replicated from current GoDaddy records) -----------

resource "digitalocean_record" "mx_a" {
  count    = var.domain != "" ? 1 : 0
  domain   = digitalocean_domain.app[0].id
  type     = "MX"
  name     = "@"
  value    = "mxa.mailgun.org."
  priority = 60
  ttl      = 300
}

resource "digitalocean_record" "mx_b" {
  count    = var.domain != "" ? 1 : 0
  domain   = digitalocean_domain.app[0].id
  type     = "MX"
  name     = "@"
  value    = "mxb.mailgun.org."
  priority = 60
  ttl      = 300
}

resource "digitalocean_record" "spf" {
  count  = var.domain != "" ? 1 : 0
  domain = digitalocean_domain.app[0].id
  type   = "TXT"
  name   = "@"
  value  = "v=spf1 include:mailgun.org ~all"
  ttl    = 300
}

resource "digitalocean_record" "dkim" {
  count  = var.domain != "" ? 1 : 0
  domain = digitalocean_domain.app[0].id
  type   = "TXT"
  name   = "smtp._domainkey"
  value  = "k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDa64KUK+b+fWBmqVjslRZsGnlp6lMKEhWddF2jb2Ik1JsaucyNsylnVKXhDEzb1au4zK0vqLhVk5JF5+VZ8RxO82KmcYNRkUMmo6ihP5sCM67hE1CaakMtH8ykBpOhMthZSzhXrntZXP5/aMxSm2rS5JC1FZKUkaoLsy3cUFEBoQIDAQAB"
  ttl    = 300
}

# Mailgun click/open tracking subdomain.
# Note: email.slicedbambu.com currently has both this CNAME and several TXT
# verification tokens at GoDaddy. Standard DNS doesn't allow CNAME + TXT at
# the same name, so DO DNS enforces the RFC here. The CNAME is what Mailgun
# actually needs for tracking; those TXT tokens were one-time verifications
# that no longer affect ongoing mail delivery.
resource "digitalocean_record" "email_tracking" {
  count  = var.domain != "" ? 1 : 0
  domain = digitalocean_domain.app[0].id
  type   = "CNAME"
  name   = "email"
  value  = "mailgun.org."
  ttl    = 300
}
