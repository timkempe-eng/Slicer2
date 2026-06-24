# --- Authentication ---------------------------------------------------------
variable "do_token" {
  type        = string
  description = "DigitalOcean API token (Personal Access Token with read/write)."
  sensitive   = true
}

variable "spaces_access_id" {
  type        = string
  description = "DigitalOcean Spaces access key ID (Spaces > Manage Keys)."
  default     = ""
}

variable "spaces_secret_key" {
  type        = string
  description = "DigitalOcean Spaces secret key."
  default     = ""
  sensitive   = true
}

# --- Project / placement ----------------------------------------------------
variable "basename" {
  type        = string
  description = "Prefix for all resource names."
  default     = "slicer2"
}

variable "region" {
  type        = string
  description = "DO region. Must support Droplets and Spaces (e.g. nyc3, sfo3, fra1, ams3, sgp1)."
  default     = "nyc3"
}

variable "ssh_key_ids" {
  type        = list(string)
  description = "SSH key fingerprints/IDs already in your DO account, for droplet root access."
  default     = []
}

variable "ssh_source_addresses" {
  type        = list(string)
  description = "CIDRs allowed to reach SSH (port 22). Lock this to your IP(s) — e.g. [\"203.0.113.4/32\"] — instead of the whole internet."
  default     = ["0.0.0.0/0", "::/0"]
}

# --- Compute ----------------------------------------------------------------
variable "droplet_size_slug" {
  type        = string
  description = "Droplet size. c-2 (2vCPU/4GB) is a good slicing starter; bump for concurrency."
  default     = "s-2vcpu-4gb"
}

variable "droplet_image" {
  type        = string
  description = "Base image. We install Docker via cloud-init on a stock Ubuntu LTS."
  default     = "ubuntu-24-04-x64"
}

# --- Application bootstrap --------------------------------------------------
variable "git_repo" {
  type        = string
  description = "Git URL the droplet clones to build/run the app."
  default     = "https://github.com/timkempe-eng/Slicer2.git"
}

variable "git_ref" {
  type        = string
  description = "Branch/tag/commit to deploy."
  default     = "main"
}

variable "domain" {
  type        = string
  description = "Optional domain for automatic HTTPS via Caddy. Empty = HTTP on the droplet IP."
  default     = ""
}

variable "stripe_secret_key" {
  type        = string
  description = "Stripe secret key (Phase 2). Leave empty until payments are wired."
  default     = ""
  sensitive   = true
}

variable "stripe_webhook_secret" {
  type        = string
  description = "Stripe webhook signing secret (Phase 2)."
  default     = ""
  sensitive   = true
}

# --- Object storage (Spaces) ------------------------------------------------
variable "bucket_name" {
  type        = string
  description = "Spaces bucket name. Must be globally unique. Empty = '<basename>-files'."
  default     = ""
}

variable "retention_days" {
  type        = number
  description = "Storage-layer expiry for uploads/outputs (PRD zero-retention). Min 1 day."
  default     = 1
}

# Postgres runs as a container on the app droplet — no managed DB variables needed.
