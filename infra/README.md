# Slicer2 infrastructure (DigitalOcean)

Terraform that provisions Slicer2 on DigitalOcean, modeled on DO's own
[marketplace blueprints](https://github.com/digitalocean/marketplace-blueprints)
(the Airflow blueprint uses the same Droplet + Managed Postgres + Spaces shape).

## What it creates

| Resource | Purpose | Default size | ~Cost/mo |
|---|---|---|---|
| Droplet (`app`) | FastAPI app + in-process slicer + Redis (docker-compose) | `c-2` (2 vCPU / 4 GB, CPU-Optimized) | ~$42 |
| Managed PostgreSQL | jobs, payments, consent/liability log | `db-s-1vcpu-1gb` | ~$15 |
| Spaces bucket | uploads + sliced outputs (1-day expiry) | — | ~$5 |
| Cloud Firewall | SSH + HTTP/HTTPS only | — | free |
| Project + Tag | grouping | — | free |

**Starter total ≈ $60–65/mo.** You can run the MVP cheaper on a shared-CPU
`s-2vcpu-4gb` (~$24) droplet, but slicing will be slower and throttled — CPU is
the bottleneck, so CPU-Optimized is recommended once you have real traffic.

## Why this shape

- **Slicing is CPU-bound.** The slice worker wants dedicated vCPUs; an upload
  pipeline that's light on CPU but bursty on slicing is the whole reason for the
  job queue. For the MVP we run the slicer **in-process on one droplet**; scale
  out by moving the slicer to dedicated CPU-Optimized worker droplets behind
  Redis (see roadmap Phase 1/3).
- **Postgres is managed** so consent logs and payment history survive droplet
  rebuilds (important for the PRD's Safe-Harbor record-keeping).
- **Spaces** holds transient files with a **1-day lifecycle rule**, which
  enforces the zero-retention policy at the storage layer.

## Two valid deployment shapes

1. **This blueprint — Droplet + docker-compose** (what's scaffolded here).
   Simplest, mirrors the DO Airflow blueprint, one `terraform apply`. Best for
   MVP and bench testing.
2. **App Platform + worker droplets** (PRD's "cloud-native" target). App
   Platform hosts the API/frontend with managed TLS + autoscaling; CPU-Optimized
   droplets run slicer workers off Managed Redis. More moving parts; adopt when
   you outgrow a single box.

## Deploy — option A: run it yourself (local state)

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in token, region, keys
terraform init -backend=false                  # state stays on your machine
terraform plan          # review — this creates billable resources
terraform apply
terraform output app_url
```

## Deploy — option B: let Claude apply from the web session (remote state)

State must live somewhere durable (not the ephemeral session container), so we
keep it in a DigitalOcean Spaces bucket (`backend.tf`).

**1. You add these to the session's environment secrets** (web settings →
environment variables — *not* pasted into chat):

| Secret name | Value |
|---|---|
| `TF_VAR_do_token` | DO API token (read/write PAT) |
| `TF_VAR_spaces_access_id` | Spaces access key |
| `TF_VAR_spaces_secret_key` | Spaces secret key |
| `AWS_ACCESS_KEY_ID` | same Spaces access key (used by the state backend) |
| `AWS_SECRET_ACCESS_KEY` | same Spaces secret key (used by the state backend) |

> Env vars are applied when the session container starts, so you may need to
> start a fresh session (or let it re-provision) after adding them.

**2. Claude bootstraps state + applies** (with your confirmation on the plan):

```bash
pip install boto3 && python infra/bootstrap_state.py   # creates the state bucket once
cd infra/terraform
terraform init            # connects to the Spaces backend
terraform plan -out tf.plan
terraform apply tf.plan   # only after you OK the plan
```

If your region isn't `nyc3`, update the endpoint in `backend.tf` and
`SLICER2_STATE_REGION` to match where the state bucket lives.

The droplet's cloud-init clones the repo, writes `deploy/.env`, and runs
`deploy/docker-compose.prod.yml`. First boot takes a few minutes (it builds the
slicer image). SSH in with `ssh root@$(terraform output -raw app_ip)` and check
`docker compose -f /opt/slicer2/app/deploy/docker-compose.prod.yml logs -f`.

## Freeze / thaw — pause costs between work sessions

This is an intermittent, single-developer project, so there's no reason to pay
for the droplet (~$24–42/mo) and managed Postgres (~$15/mo) while nobody's
touching it. DO can't truly "pause" these (a powered-off droplet still bills;
managed DBs can't be paused), so the cheap path is to **destroy and recreate**:

```bash
./scripts/freeze.sh    # backs up the DB, then `terraform destroy` → ~$0/mo
./scripts/thaw.sh      # `terraform apply` to bring it all back (~5 min)
./scripts/thaw.sh --restore   # ...and reload the last DB backup
```

What survives a freeze: the Terraform **state bucket** (`slicer2-tfstate`),
which isn't managed by Terraform. `freeze.sh` parks a compressed `pg_dump` there
(under `db-backups/`) by running it *through* the droplet — the DB firewall only
admits the droplet, so it can't be dumped directly. `thaw.sh --restore` pulls
the newest dump back. Both scripts need the same env vars as a normal apply
(`TF_VAR_*` + `AWS_*`) and SSH access to the droplet (`ssh_key_ids`).

Notes:
- The Spaces *files* bucket has `force_destroy = true` so teardown doesn't choke
  on leftover objects (they're 1-day-lifecycle transient anyway).
- `freeze.sh --no-backup` skips the dump; `--force` proceeds even if it fails;
  `-y` skips the destroy confirmation. `thaw.sh -y` skips the apply prompt.
- The dump is taken `--clean --if-exists`, so a restore deterministically
  overwrites whatever schema the freshly-booted app recreated.

## Before you `apply`

- This **creates real, billable resources** — review `terraform plan` first.
- Put **real A1 profiles** in `backend/profiles/a1/` (see that folder's README)
  or slicing will fail on the live box just like in tests.
- Verify the **Bambu Studio AppImage URL** in `deploy/Dockerfile.app` points at
  a real release asset (the pinned one is a placeholder). OrcaSlicer is a drop-in
  alternative and bundles A1 profiles.
- `terraform.tfvars` and `deploy/.env` hold secrets — both are gitignored. Keep
  them that way.
- To tear everything down: `terraform destroy`.
