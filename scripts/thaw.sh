#!/usr/bin/env bash
# Spin the Slicer2 infra back UP after a freeze (see scripts/freeze.sh).
#
# Runs `terraform apply` to recreate the droplet, managed Postgres, and Spaces
# files bucket. With --restore it also waits for the droplet to come up and
# loads the most recent DB dump from the state bucket back into Postgres.
#
# Usage:
#   ./scripts/thaw.sh             # recreate infra (asks to confirm)
#   ./scripts/thaw.sh --restore   # also restore the latest DB backup
#   ./scripts/thaw.sh -y          # don't prompt before applying
#
# Same env requirements as freeze.sh / a normal apply (see infra/README.md).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform"
SSH_USER="${SLICER2_SSH_USER:-root}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)

RESTORE=0
AUTO_APPROVE=0
for arg in "$@"; do
  case "$arg" in
    --restore) RESTORE=1 ;;
    -y|--auto-approve|--yes) AUTO_APPROVE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

cd "$TF_DIR"
[[ -d .terraform ]] || terraform init -input=false

echo "==> Applying — recreating droplet, Postgres, and files bucket…"
if [[ "$AUTO_APPROVE" -eq 1 ]]; then
  terraform apply -auto-approve
else
  terraform apply
fi

IP="$(terraform output -raw app_ip)"
echo
echo "==> Thawed. App will be reachable at: $(terraform output -raw app_url)"
echo "    First boot runs cloud-init (Docker install + image build) — give it a few minutes."

if [[ "$RESTORE" -eq 1 ]]; then
  echo "==> Restore requested — fetching latest DB backup…"
  DUMP="$(mktemp "${TMPDIR:-/tmp}/slicer2-db.XXXXXX.sql.gz")"
  KEY="$(python3 "$ROOT/infra/db_backup.py" download-latest "$DUMP")"
  echo "    Got $KEY"

  echo "==> Waiting for the droplet to accept SSH and have Docker ready…"
  deadline=$(( $(date +%s) + 600 ))  # up to 10 minutes for cloud-init
  until ssh "${SSH_OPTS[@]}" "$SSH_USER@$IP" 'command -v docker >/dev/null' 2>/dev/null; do
    if [[ "$(date +%s)" -ge "$deadline" ]]; then
      echo "!! Droplet not ready after 10 min. Restore later with:" >&2
      echo "   gunzip -c $DUMP | ssh $SSH_USER@$IP 'set -a; . /opt/slicer2/.env; docker run --rm -i --network host postgres:16 psql \"\$DATABASE_URL\"'" >&2
      exit 1
    fi
    sleep 15
  done

  echo "==> Restoring database (the dump is --clean, so it overwrites the fresh schema)…"
  gunzip -c "$DUMP" \
    | ssh "${SSH_OPTS[@]}" "$SSH_USER@$IP" \
        'set -a; . /opt/slicer2/.env; set +a; docker run --rm -i --network host postgres:16 psql --quiet "$DATABASE_URL"'
  rm -f "$DUMP"
  echo "==> Database restored from $KEY."
fi
