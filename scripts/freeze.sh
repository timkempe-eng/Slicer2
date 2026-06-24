#!/usr/bin/env bash
# Spin the Slicer2 infra DOWN to ~$5/mo (state bucket only) when not working.
#
# DigitalOcean has no real "pause" — a powered-off droplet still bills. So we
# destroy the billable resources (droplet + files bucket) and recreate them with
# scripts/thaw.sh when we come back. The Terraform state bucket is unmanaged and
# survives. DB data is intentionally not preserved (solo dev, low-value data).
#
# Usage:
#   ./scripts/freeze.sh          # destroy (asks to confirm)
#   ./scripts/freeze.sh -y       # destroy without prompt
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

echo "==> Frozen. Bring it back with: ./scripts/thaw.sh"
