# Postgres now runs as a container on the app droplet (see docker-compose.prod.yml).
# The managed DigitalOcean database cluster has been removed to eliminate the
# $15/mo fixed cost that could not be paused, and that added ~5 min to every thaw.
#
# Trade-offs accepted:
#   - No automated managed-DB backups (user has opted out of DB restore anyway).
#   - DB data lives on the droplet's disk; it is lost on freeze (expected behaviour).
#   - No private-network firewall rule needed (DB is container-local only).
