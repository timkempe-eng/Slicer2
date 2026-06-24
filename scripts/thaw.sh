#!/usr/bin/env bash
# Spin the Slicer2 infra back UP after a freeze (see scripts/freeze.sh).
#
# Runs `terraform apply` to recreate the droplet and Spaces files bucket.
# First boot runs cloud-init (Docker install + image build) — ~5 min.
#
# Usage:
#   ./scripts/thaw.sh      # recreate infra (asks to confirm)
#   ./scripts/thaw.sh -y   # don't prompt before applying
#
# Same env requirements as freeze.sh (see infra/README.md).
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

echo "==> Applying — recreating droplet and files bucket…"
if [[ "$AUTO_APPROVE" -eq 1 ]]; then
  terraform apply -auto-approve
else
  terraform apply
fi

echo
echo "==> Thawed. App will be reachable at: $(terraform output -raw app_url)"
echo "    First boot runs cloud-init (Docker install + image build) — give it ~5 min."
