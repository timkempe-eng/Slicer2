# Remote state on DigitalOcean Spaces (S3-compatible), so Terraform state
# survives this ephemeral environment instead of living in a throwaway container.
#
# Credentials are NOT stored here — the backend reads AWS_ACCESS_KEY_ID /
# AWS_SECRET_ACCESS_KEY from the environment (set these to your Spaces keys).
# The state bucket must exist first: run `infra/bootstrap_state.py` once.
#
# If you'd rather keep state locally (e.g. running apply from your own laptop),
# init with `terraform init -backend=false` and delete/ignore this file.
terraform {
  backend "s3" {
    bucket = "slicer2-tfstate"
    key    = "slicer2/terraform.tfstate"
    region = "us-east-1" # placeholder; Spaces ignores AWS regions

    endpoints = {
      s3 = "https://nyc3.digitaloceanspaces.com" # must match your state bucket's region
    }

    # Required so the AWS S3 backend tolerates a non-AWS endpoint (Spaces).
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = false
  }
}
