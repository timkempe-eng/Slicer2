# Non-secret deployment config for Slicer2.
#
# Terraform auto-loads any *.auto.tfvars file, so these values apply to EVERY
# `apply` — which is what makes freeze/thaw reproduce the *same* infrastructure
# no matter which machine or session runs it. Without this, a thaw from a
# session that's missing (e.g.) the domain or SSH key would destroy and rebuild
# the droplet with different settings.
#
# Secrets are NOT here — tokens and Spaces/Stripe keys still come from TF_VAR_*
# environment variables. Everything below is safe to commit (no credentials).

region            = "nyc3"
droplet_size_slug = "s-2vcpu-4gb"

# Domain that points at the droplet for automatic HTTPS.
domain = "slicedbambu.com"

# SSH key already in the DigitalOcean account (name: "slicedbambu-deploy").
# The droplet is created with this key so it stays reachable across rebuilds.
ssh_key_ids = ["57206872"]

git_repo = "https://github.com/timkempe-eng/Slicer2.git"
git_ref  = "main"
