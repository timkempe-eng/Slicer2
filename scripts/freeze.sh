#!/usr/bin/env bash
# Spin the Slicer2 infra DOWN to ~$0/mo when you're not working on it.
#
# DigitalOcean has no real "pause" — a powered-off droplet still bills, and
# managed databases can't be paused at all. So the cheap path is to destroy the
# billable resources (droplet + managed Postgres + Spaces files bucket) and
# recreate them with scripts/thaw.sh when you come back. The Terraform *state*
# bucket is not managed by Terraform, so it (and any DB backups we park in it)
# survives the teardown.
#
# Before destroying we take a best-effort dump of the database THROUGH the
# droplet (the DB firewall only allows the droplet, so we can't reach it
# directly) and stash it in the state bucket. thaw.sh --restore brings it back.
#
# Usage:
#   ./scripts/freeze.sh                # back up DB, then destroy (asks to confirm)
#   ./scripts/freeze.sh --no-backup    # skip the DB dump
#   ./scripts/freeze.sh --force        # don't abort if the backup fails
#   ./scripts/freeze.sh -y             # don't prompt before destroying
#
# Requires the same env as a normal apply: TF_VAR_do_token,
# TF_VAR_spaces_access_id, TF_VAR_spaces_secret_key, AWS_ACCESS_KEY_ID,
# AWS_SECRET_ACCESS_KEY (see infra/README.md).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform"
SSH_USER="${SLICER2_SSH_USER:-root}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)

BACKUP=1
AUTO_APPROVE=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --no-backup) BACKUP=0 ;;
    --force) FORCE=1 ;;
    -y|--auto-approve|--yes) AUTO_APPROVE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

cd "$TF_DIR"
[[ -d .terraform ]] || terraform init -input=false

if [[ "$BACKUP" -eq 1 ]]; then
  IP="$(terraform output -raw app_ip 2>/dev/null || true)"
  if [[ -z "$IP" ]]; then
    echo "==> No droplet in state — nothing to back up, skipping."
  else
    echo "==> Backing up database via droplet $IP …"
    DUMP="$(mktemp "${TMPDIR:-/tmp}/slicer2-db.XXXXXX.sql.gz")"
    # Source DATABASE_URL on the droplet and run pg_dump inside a throwaway
    # postgres container sharing the host network (so it can reach the private
    # DB). --clean --if-exists makes the dump self-resetting so a later restore
    # is deterministic regardless of what the app recreated.
    if ssh "${SSH_OPTS[@]}" "$SSH_USER@$IP" \
         'set -a; . /opt/slicer2/.env; set +a; docker run --rm --network host postgres:16 pg_dump --no-owner --no-acl --clean --if-exists "$DATABASE_URL"' \
         | gzip > "$DUMP"; then
      KEY="$(python3 "$ROOT/infra/db_backup.py" upload "$DUMP")"
      echo "==> DB backed up to state bucket: $KEY ($(du -h "$DUMP" | cut -f1))"
      rm -f "$DUMP"
    else
      rm -f "$DUMP"
      echo "!! DB backup FAILED (droplet unreachable, no SSH key, or DB down)." >&2
      if [[ "$FORCE" -eq 1 ]]; then
        echo "!! --force given: continuing WITHOUT a backup; DB data will be lost." >&2
      else
        echo "   Re-run with --no-backup (accept data loss) or --force, or fix SSH." >&2
        exit 1
      fi
    fi
  fi
fi

echo "==> Destroying billable resources (droplet, Postgres, files bucket)…"
if [[ "$AUTO_APPROVE" -eq 1 ]]; then
  terraform destroy -auto-approve
else
  terraform destroy
fi

echo
echo "==> Frozen. Billable infra is gone; only the state bucket remains (~\$0)."
echo "    Bring it back with: ./scripts/thaw.sh   (add --restore for the DB)"
