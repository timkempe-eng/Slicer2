# Spaces (S3-compatible) object storage for uploaded models and sliced output.
# A lifecycle rule enforces the PRD's zero-retention policy at the storage layer
# (expiry is day-granular; the app should also delete promptly after download).
resource "digitalocean_spaces_bucket" "files" {
  name   = var.bucket_name != "" ? var.bucket_name : "${local.name}-files"
  region = var.region
  acl    = "private"

  # Files here are transient (1-day lifecycle below), so let `terraform destroy`
  # empty and remove the bucket instead of erroring on leftover objects. This is
  # what makes the freeze/thaw workflow (scripts/freeze.sh) tear down cleanly.
  force_destroy = true

  lifecycle_rule {
    enabled = true
    expiration {
      days = var.retention_days
    }
  }

  # Allow direct browser PUT/GET if we move to presigned uploads later.
  cors_rule {
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = [var.domain != "" ? "https://${var.domain}" : "*"]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}
