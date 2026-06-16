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

## Deploy

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in token, region, keys
terraform init
terraform plan          # review — this creates billable resources
terraform apply
terraform output app_url
```

The droplet's cloud-init clones the repo, writes `deploy/.env`, and runs
`deploy/docker-compose.prod.yml`. First boot takes a few minutes (it builds the
slicer image). SSH in with `ssh root@$(terraform output -raw app_ip)` and check
`docker compose -f /opt/slicer2/app/deploy/docker-compose.prod.yml logs -f`.

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
