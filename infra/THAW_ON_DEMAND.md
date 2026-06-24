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
| 7 | `TF_VAR_ssh_key_ids` | Droplet gets an SSH key so it's reachable at all | ❌ **unset — see below** |
| 8 | Sizing vars (optional) | Reproduce the same droplet/DB size, not the code defaults | ⚠️ defaults apply unless set |
| 9 | SSH private key in session + outbound port 22 | DB **restore** runs through the droplet over SSH | ❌ **not available from web — see below** |

Items 1–6 mean **spin-up works today**. Items 7–9 are what's missing for a
fully reachable box and for DB restore.

---

## One-time setup you need to do

### A. Make the droplet reachable — set `TF_VAR_ssh_key_ids` (do this)

Right now this is unset, so `apply` would build a droplet with **no SSH key**.
Even ignoring restore, that means neither you nor Claude can SSH in to debug.

In the web session's environment-variables settings, add:

| Secret name | Value |
|---|---|
| `TF_VAR_ssh_key_ids` | `["<fingerprint-or-id>"]` — your SSH key(s) already uploaded to DO |

Find the fingerprint under DO → Settings → Security → SSH Keys, or via
`doctl compute ssh-key list`. The value is Terraform JSON list syntax, e.g.
`["aa:bb:cc:..."]` or `["12345678"]`.

### B. (Optional) Pin sizing so thaw reproduces your exact box

The code defaults (`variables.tf`) are `s-2vcpu-4gb` droplet + `db-s-1vcpu-1gb`
Postgres in `nyc3`. If you ran something different before (e.g. the `c-2`
CPU-Optimized droplet from `terraform.tfvars.example`), set these so each thaw
recreates the same shape:

| Secret name | Example |
|---|---|
| `TF_VAR_region` | `nyc3` |
| `TF_VAR_droplet_size_slug` | `c-2` |
| `TF_VAR_db_size_slug` | `db-s-1vcpu-1gb` |
| `TF_VAR_domain` | `slicer.example.com` (blank = HTTP on the IP) |

These are environment-applied, so add/change them before starting a session.

### C. (Only if you want Claude to restore the DB from the web) — likely not feasible

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

## Summary: what to do so "just say thaw" works

1. Add **`TF_VAR_ssh_key_ids`** to the session env (item A) — the one real gap
   for spin-up to produce a usable box.
2. Optionally pin sizing (item B).
3. Then say **"spin up Slicer"** and Claude runs `./scripts/thaw.sh -y`.
4. Restore the DB from your laptop if/when you need the old data (item C / the
   fallback).
