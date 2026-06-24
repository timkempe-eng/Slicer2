#!/usr/bin/env bash
# Spin the Slicer2 infra DOWN to ~$5/mo (state bucket only) when not working.
#
# DigitalOcean has no real "pause" — a powered-off droplet still bills, and
# there is no pause for databases. The only cheap path is to destroy the
# billable resources (droplet + Spaces files bucket) and recreate them with
# scripts/thaw.sh when you come back. The Terraform *state* bucket is not
# managed by Terraform, so it survives the teardown.
#
# DB data is intentionally lost on freeze (Postgres runs on the droplet disk).
#
# Usage:
#   ./scripts/freeze.sh          # destroy (asks to confirm)
#   ./scripts/freeze.sh -y       # don't prompt before destroying
#
# Requires: TF_VAR_do_token, TF_VAR_spaces_access_id, TF_VAR_spaces_secret_key,
#           AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (see infra/README.md).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform"

AUTO_APPROVE=0
for arg in "$@"; do
  case "$arg" in
    -y|--auto-approve|--yes) AUTO_APPROVE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

cd "$TF_DIR"
[[ -d .terraform ]] || terraform init -input=false

echo "==> Destroying billable resources (droplet + files bucket)…"
if [[ "$AUTO_APPROVE" -eq 1 ]]; then
  terraform destroy -auto-approve
else
  terraform destroy
fi

echo
echo "==> Frozen. Billable infra is gone; only the state bucket remains (~\$5/mo)."
echo "    Bring it back with: ./scripts/thaw.sh"
