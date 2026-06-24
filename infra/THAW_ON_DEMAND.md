# Spinning Slicer2 back up on demand

Runbook for the workflow: **you say “spin up Slicer” and Claude runs the thaw
from a Claude Code web session.**

See `scripts/freeze.sh` / `scripts/thaw.sh` for the mechanics and
`infra/README.md` for the cost rationale.

---

## The trigger

Just tell Claude **“spin Slicer back up”** / **“thaw Slicer”**.
Saying it is your authorization to create billable resources.

What Claude does:

```bash
# installs terraform if the session doesn’t have it (HTTPS download)
./scripts/thaw.sh -y    # terraform init + apply, then prints the app URL
```

First boot runs cloud-init (Docker install + image build) — give it ~5 min.

---

## Requirements & current status

| # | Requirement | Why | Status |
|---|---|---|---|
| 1 | `TF_VAR_do_token` | Create DO resources | ✅ set in session env |
| 2 | `TF_VAR_spaces_access_id` / `TF_VAR_spaces_secret_key` | Create files bucket | ✅ set |
| 3 | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Read TF state from Spaces backend | ✅ set |
| 4 | `terraform` binary | Run apply | ⚙️ auto-installed at thaw time |
| 5 | State bucket `slicer2-tfstate` exists | Holds TF state; survives a freeze | ✅ exists |
| 6 | SSH key, domain, sizing pinned | Thaw reproduces the same server | ✅ in `prod.auto.tfvars` |

All requirements are met. **Spin-up works on your word.**

---

## What’s pinned in prod.auto.tfvars

- SSH key `57206872` (“slicedbambu-deploy”, already in the DO account)
- domain `slicedbambu.com`
- `s-2vcpu-4gb` droplet in `nyc3`
- `git_ref = main` (droplet clones from main on boot)

No secrets are in this file — it’s safe to commit.

---

## One-time GoDaddy nameserver change (do this once)

So the domain auto-updates after every thaw:

1. **godaddy.com → My Products → slicedbambu.com → DNS → Nameservers → Change**
2. Choose **“Enter my own nameservers”**
3. Enter:
   ```
   ns1.digitalocean.com
   ns2.digitalocean.com
   ns3.digitalocean.com
   ```
4. Save. Propagates in 15 min – a few hours.

After this, every thaw automatically points `slicedbambu.com` at the new server.

---

## If the state bucket is missing

```bash
pip install boto3
python infra/bootstrap_state.py
```

Then retry the thaw.
