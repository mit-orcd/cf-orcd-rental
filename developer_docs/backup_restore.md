# Backup & Restore Guide

This guide summarizes recommended practices for backing up and restoring ColdFront and the ORCD direct-charge plugin, with emphasis on database safety, live backups, and how backups interact with upgrades.

## What to Back Up
- **PostgreSQL database**: authoritative source of portal data.
- **Portal export artifacts**: use `coldfront export_portal_data` to snapshot core + plugin data (see `developer_docs/exporter_importer_reference.md`).
- **Configuration**: `local_settings.py`, environment files, systemd/nginx configs, `MEDIA_ROOT` if user uploads are used.
- **Code version**: commit hash/tag of the deployed release.

## Backup Approaches

### Database backups (primary)
- Use `pg_dump` from the DB host:
  ```bash
  pg_dump -Fc -Z6 -f /backups/portal/db_$(date +%Y%m%d_%H%M%S).dump $DB_NAME
  ```
  - `-Fc` custom format supports selective restores and faster pg_restore.
  - Run as a role with sufficient privileges; avoid superuser when possible.
  - For large databases, consider `--jobs` during restore, not during dump.
- Live backups: `pg_dump` is consistent on PostgreSQL and safe while the site is running. For heavy write load, pair with:
  - `--lock-wait-timeout` to avoid long locks.
  - WAL archiving or storage snapshots if you need point-in-time recovery.

### Portal export (secondary, human-readable snapshot)
- Run from the app virtualenv:
  ```bash
  coldfront export_portal_data -o /backups/portal/exports/ --source-url https://<portal> --source-name "ORCD Rental Portal"
  ```
  - Default exports both `coldfront_core` and `orcd_plugin` with manifests.
  - Use `--component orcd_plugin` for plugin-only snapshots.
  - Add `--dry-run` to report counts without writing files (useful in cron health checks).

### Files/configs
- Version and back up `local_settings.py`, env files, and any `MEDIA_ROOT` uploads.
- Capture deployment automation (Ansible/Terraform) if applicable.

## Scheduling & Retention
- **Daily**: `pg_dump -Fc` (keep 7–14 days).
- **Weekly**: full portal export (`export_portal_data`) (keep 4–8 weeks).
- **Pre-change**: on-demand DB dump + portal export before upgrades or data migrations.
- Rotate and prune with a retention policy; verify at least one recent restore works.

## Labeling Backups
- Use timestamp + software version (git tag/commit) in names and manifest notes:
  - `db_20260310_0130_main-d2c53c4.dump`
  - `export_20260310_0130_main-d2c53c4/` (default exporter timestamp directory is fine; add a README.txt noting commit/tag).
- Record:
  - Portal URL and environment (`prod`, `staging`).
  - ColdFront/plugin version or commit hash.
  - Schema/app notes if an upgrade is pending or has just been applied.

## Restore Procedures

### Database restore
1. Provision a PostgreSQL instance with matching major version.
2. Drop/recreate target DB if appropriate:
   ```bash
   dropdb $DB_NAME && createdb $DB_NAME
   ```
3. Restore:
   ```bash
   pg_restore -Fc -j4 -d $DB_NAME /backups/portal/db_YYYYMMDD_HHMMSS.dump
   ```
4. Apply any environment-specific settings (settings files, secrets) and restart services.
5. Verify login, key pages, and recent data.

### Portal export restore (optional/additive)
- Use when migrating between instances or selectively repopulating data:
  ```bash
  coldfront import_portal_data /path/to/export_dir --dry-run   # validate first
  coldfront import_portal_data /path/to/export_dir             # execute
  ```
- Use `--component` to limit scope (e.g., plugin only), `--mode create-only` to avoid updating existing rows, and `--skip-conflicts` to continue past conflicts.
- Respect compatibility and checksum warnings; `--force` overrides but should be avoided unless understood.

## Live Backup Considerations
- `pg_dump` provides a consistent snapshot without downtime; expect brief locks when metadata is read.
- For high-traffic windows, schedule during lower activity or use storage snapshots + WAL shipping.
- Ensure backups run on the DB host or with a secure network path; avoid copying secrets into logs.

## Upgrades and Backups
- **Before upgrading**: take a DB dump + portal export; label with current version/commit.
- **After upgrading**: run migrations, then consider a fresh DB dump to anchor the new version.
- **Schema changes**: if importer/exporter adds new models, ensure the export was produced from a version compatible with the target importer; check compatibility output before import.
- Keep at least one pre-upgrade backup until the upgraded system is validated.

## Verification and Drills
- Periodically restore to a staging environment to verify:
  - `pg_restore` completes without errors.
  - `coldfront import_portal_data --dry-run` reports expected counts.
  - Key user flows work (login, reservations, billing pages).
- Track restore steps and timings to improve runbooks.

## Security and Access
- Restrict backup storage and transport (encryption at rest and in transit).
- Avoid embedding secrets in backup filenames; keep secrets in a separate secure vault.
- Audit who can run backup/restore commands and who can read the artifacts.
