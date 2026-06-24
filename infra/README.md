# Slicer2 infrastructure (DigitalOcean)

Terraform that provisions Slicer2 on DigitalOcean, modeled on DO's own
[marketplace blueprints](https://github.com/digitalocean/marketplace-blueprints)
(the Airflow blueprint uses the same Droplet + Managed Postgres + Spaces shape).

## What it creates

| Resource | Purpose | Default size | ~Cost/mo |
|---|---|---|---|
| Droplet (`app`) | FastAPI app + in-process slicer + Postgres + Redis (docker-compose) | `s-2vcpu-4gb` (2 vCPU / 4 GB) | ~$24 |
| Spaces bucket | uploads + sliced outputs (1-day expiry) | — | ~$5 |
| DO DNS | A records for the app domain, auto-updated on thaw | — | free |
| Cloud Firewall | SSH + HTTP/HTTPS only | — | free |
| Project + Tag | grouping | — | free |

**Running total ≈ $29/mo. Frozen (destroyed) ≈ $5/mo** (Spaces state bucket only).

Postgres runs as a container on the droplet alongside Redis — no managed
database needed. This saves $15/mo and eliminates the ~5 min DB provision
delay on every thaw. Trade-off: DB data is lost on freeze (accepted for this
intermittent solo project).

## Freeze / thaw — pause costs between work sessions

This is an intermittent, single-developer project, so there’s no reason to pay
~$29/mo while nobody’s touching it. DO can’t truly “pause” a droplet (a
powered-off droplet still bills), so the cheap path is to **destroy and
recreate**:

```bash
./scripts/freeze.sh -y    # terraform destroy → ~$5/mo
./scripts/thaw.sh  -y    # terraform apply  → site back in ~5 min
```

Or just tell Claude “freeze Slicer” / “spin up Slicer” and it runs these.
See `infra/THAW_ON_DEMAND.md` for the full runbook.

What survives a freeze: the Terraform **state bucket** (`slicer2-tfstate`),
which isn’t managed by Terraform. DB data is intentionally lost on freeze.

Notes:
- The Spaces *files* bucket has `force_destroy = true` so teardown doesn’t
  choke on leftover objects (1-day lifecycle, so they’re transient anyway).
- `freeze.sh --no-backup` skips the DB dump; `-y` skips the destroy prompt.
- `thaw.sh -y` skips the apply prompt.

## DNS — one-time setup at GoDaddy

Terraform manages `slicedbambu.com` DNS in DigitalOcean so the A records
auto-update to the new droplet IP on every thaw. One-time step at GoDaddy:

1. **GoDaddy → My Products → slicedbambu.com → DNS → Nameservers → Change**
2. Choose **“Enter my own nameservers”** and enter:
   ```
   ns1.digitalocean.com
   ns2.digitalocean.com
   ns3.digitalocean.com
   ```
3. Save. Propagation takes 15 min – a few hours.

After that, every thaw automatically points the domain at the new server.

## Deploy

```bash
cd infra/terraform
terraform init            # connects to the Spaces backend
terraform plan            # review — this creates billable resources
terraform apply
terraform output app_url
```

Requires env vars: `TF_VAR_do_token`, `TF_VAR_spaces_access_id`,
`TF_VAR_spaces_secret_key`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
See `infra/THAW_ON_DEMAND.md` for the full list.

First boot takes a few minutes (cloud-init installs Docker + builds images).
SSH in with `ssh root@$(terraform output -raw app_ip)` and check
`docker compose -f /opt/slicer2/app/deploy/docker-compose.prod.yml logs -f`.

## Before you `apply`

- This **creates real, billable resources** — review `terraform plan` first.
- Put **real A1 profiles** in `backend/profiles/a1/` or slicing will fail.
- `deploy/.env` holds secrets — it’s gitignored and written by cloud-init.
- To tear everything down: `terraform destroy` (or `./scripts/freeze.sh`).
