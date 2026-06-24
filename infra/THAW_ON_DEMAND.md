# Spinning Slicer2 back up on demand

Runbook for the workflow: **you say "spin up Slicer" and Claude runs the thaw
from a Claude Code web session.** This documents everything that has to be in
place for that to work, what's already satisfied, and what's still missing.

See `scripts/freeze.sh` / `scripts/thaw.sh` for the mechanics and the
"Freeze / thaw" section of `infra/README.md` for the cost rationale.

---

## The trigger

Just tell Claude something like **"spin Slicer back up"** / **"thaw Slicer"**.
Saying it is your authorization to create billable resources — Claude will run
`apply` non-interactively (`-y`) rather than asking again.

What Claude does on that trigger:

```bash
# install terraform + python deps if the session doesn't have them (HTTPS only)
./scripts/thaw.sh -y        # terraform init + apply, then prints the app URL
```

Add restore only if the DB-restore prerequisites below are met:

```bash
./scripts/thaw.sh -y --restore
```

First boot then runs cloud-init (Docker install + image build) for a few
minutes before the site answers.

---

## Requirements & current status

| # | Requirement | Why it's needed | Status (2026-06-24) |
|---|---|---|---|
| 1 | `TF_VAR_do_token` | Create DO resources | ✅ set in session env |
| 2 | `TF_VAR_spaces_access_id` / `TF_VAR_spaces_secret_key` | Create the files bucket | ✅ set |
| 3 | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (= the Spaces keys) | Read TF state from the Spaces backend; up/download DB dumps | ✅ set |
| 4 | `terraform` binary | Run apply | ⚙️ auto-installed at thaw time |
| 5 | `boto3` | DB dump download (restore only) | ⚙️ auto-installed at thaw time |
| 6 | State bucket `slicer2-tfstate` exists | Holds TF state + DB backups; survives a freeze | ✅ assumed (created by `bootstrap_state.py`) |
| 7 | SSH key + domain + sizing pinned | Thaw reproduces the *same* server, not a rebuilt one | ✅ committed in `infra/terraform/prod.auto.tfvars` |
| 8 | SSH private key in session + outbound port 22 | DB **restore** runs through the droplet over SSH | ❌ not available from web — restore is a laptop step / skipped |

Items 1–7 mean **spin-up works and faithfully reproduces the live setup**
(verified with a no-cost `terraform plan` on 2026-06-24: `0 to add, 0 to
destroy`). Item 8 only affects DB restore, which we've decided to skip.

---

## Setup — already done

The SSH key, domain, and sizing are now pinned in
`infra/terraform/prod.auto.tfvars` (committed, no secrets), captured from the
live server:

- SSH key `57206872` ("slicedbambu-deploy", already in the DO account)
- domain `slicedbambu.com`
- `s-2vcpu-4gb` droplet + `db-s-1vcpu-1gb` Postgres in `nyc3`

Because Terraform auto-loads that file, every thaw recreates the same box with
the same domain and key — no per-session setup needed. To change sizing, the
domain, or the key later, edit that file and commit.

> Note on the SSH key: it already exists and is attached to the droplet, so the
> server stays reachable. To actually *log in* yourself you'd need the matching
> private key file for "slicedbambu-deploy". If you don't have it, you don't
> need it for freeze/thaw — and we can swap in a fresh key anytime.

### DB restore from the web — not feasible (and we're skipping it)

DB restore runs `pg_dump`/`psql` **through the droplet over SSH** (the DB
firewall only admits the droplet). For Claude to do that from a web session it
would need *all* of:

1. `TF_VAR_ssh_key_ids` set (item A), so the droplet has a key.
2. The matching **private key** available in the session, e.g. a
   `SLICER2_SSH_PRIVATE_KEY` secret that a setup step writes to
   `~/.ssh/id_ed25519` (chmod 600).
3. **Outbound TCP/22** from the session to the droplet.

Item 3 is the blocker: the web sandbox routes egress through an **HTTPS-only
proxy**, so raw SSH to a droplet IP generally won't connect. Treat **DB restore
as a laptop step**, not something Claude does from the web — see the fallback
below. For an intermittent solo project with 1-day-transient files, starting
with a fresh DB each thaw is usually fine anyway.

---

## DB restore fallback (run from your laptop)

After a thaw, from a machine with `ssh` to the droplet:

```bash
cd infra/terraform
IP=$(terraform output -raw app_ip)
# pull the newest dump out of the state bucket
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
  python3 ../db_backup.py download-latest /tmp/slicer2.sql.gz
# load it through the droplet (the dump is --clean, so it overwrites cleanly)
gunzip -c /tmp/slicer2.sql.gz | ssh root@$IP \
  'set -a; . /opt/slicer2/.env; docker run --rm -i --network host postgres:16 psql "$DATABASE_URL"'
```

Or simply run the whole thing locally where SSH works:
`./scripts/thaw.sh -y --restore`.

---

## If the state bucket is missing

If `terraform init` can't find `slicer2-tfstate` (e.g. it was deleted), recreate
it once before thawing:

```bash
pip install boto3
python infra/bootstrap_state.py
```

Note: a missing/empty state bucket also means there's no prior DB backup to
restore.

---

## Summary: how "just say thaw" works now

Nothing left to set up. Just say **"freeze Slicer"** / **"spin up Slicer"** and
Claude runs the teardown / `./scripts/thaw.sh -y`. Config is pinned, secrets are
in the session env, and a no-cost dry run has confirmed thaw reproduces the
existing server without rebuilding it. The database starts fresh on each thaw
(we've opted out of restore).
