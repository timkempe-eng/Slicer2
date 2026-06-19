# Security

This documents SlicedBambu's hardening and the operational steps that require
your DigitalOcean / registrar access.

## Threat model

A free, no-login public service that runs a desktop slicer (OrcaSlicer) on
**untrusted uploaded files** and stores them in object storage. The main risks:
abuse/DoS of the expensive slice pipeline, enumeration/leak of other users'
files, code execution via a malicious model, and the usual web risks (XSS,
clickjacking, SSRF, transport security).

## What's enforced in the app / deploy (in this repo)

- **No job enumeration.** There is no "list all jobs" endpoint. A job id is an
  unguessable `uuid4`; that capability is required to read or download a job
  (`backend/app/main.py`).
- **Per-IP rate limiting** on `POST /api/slice` (Redis-backed, fail-open):
  defaults 6/min and 80/day, tunable via `SLICER2_SLICE_RATE_PER_*`
  (`backend/app/ratelimit.py`). Client IP is taken from Caddy's `X-Forwarded-For`.
- **Upload limits / validation.** 200 MiB cap (streamed), extension allow-list,
  and **filename sanitization** to a safe charset so names can't carry markup or
  path traversal into responses, object keys, or the CLI.
- **XSS hardening.** Untrusted text (slicer errors, filenames) is HTML-escaped
  before rendering (`static/app.js`), backed by a Content-Security-Policy.
- **SSRF surface disabled.** The LAN `/print` endpoint (opens connections to a
  caller-supplied host) is **off by default** (`SLICER2_ENABLE_PRINT=false`);
  it 404s on the hosted service.
- **Security headers** via Caddy (`deploy/Caddyfile`): HSTS (1y, preload),
  `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, a scoped CSP (self + Google AdSense + Stripe), and the
  `Server` token removed. TLS is automatic Let's Encrypt.
- **Container hardening** (`deploy/docker-compose.prod.yml`): `no-new-privileges`,
  `cap_drop: ALL`, and `pids_limit`/`mem_limit` on app and worker, so a slicer
  exploit or abusive request can't escalate or OOM the host. Redis and Postgres
  are not published to the internet; Spaces bucket ACL is `private`.
- **Reduced surface.** Interactive API docs / OpenAPI schema are off in prod
  (`SLICER2_ENABLE_DOCS=false`); `/api/health` returns no internal details.

## Operational steps that need YOUR access

These can't be done from the repo; do them in the DigitalOcean console / your
registrar.

1. **Lock down SSH.** SSH (22) is currently open to the world. Set
   `ssh_source_addresses = ["<your.ip>/32"]` in `infra/terraform/terraform.tfvars`
   and re-run the provision workflow (or edit the cloud firewall directly:
   Networking → Firewalls → `slicer2-fw` → SSH source = your IP). Consider
   disabling SSH password auth (key-only) on the droplet.
2. **Patching.** Enable automatic security updates on the droplet:
   `apt-get install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades`.
   Optionally install `fail2ban` for SSH brute-force protection.
3. **Finish the DNS cutover.** Remove GoDaddy's parking A-records on the apex so
   `slicedbambu.com` resolves only to the droplet (otherwise traffic leaks to the
   parking page — see chat).
4. **Secrets hygiene.** `.env` on the droplet holds DB/Spaces creds (mode 0600).
   Rotate the Spaces keys and DB password if they've ever been shared; never
   commit `.env` or `terraform.tfvars`.
5. **Backups / cost guard.** Managed Postgres has automated backups; keep the
   Spaces 1-day lifecycle rule (limits exposure and cost) and watch usage.

## Known limitations / future work

- No user accounts — job ids are bearer capabilities (fine for share-by-link,
  not for private multi-tenant). Add anonymous signed-session scoping or auth
  before treating jobs as private.
- The worker still runs the slicer as root *inside* its container; for stronger
  isolation, run it as a non-root user and/or add a seccomp profile.
- CSP allows `'unsafe-inline'` for scripts (required by AdSense); revisit if ads
  are removed.
