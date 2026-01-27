# Exporter & Importer Reference

This guide documents the management commands that export or import portal data for ColdFront core and the ORCD plugin. It summarizes directory layout, command options, validation/compatibility behaviors, and configuration comparison.

## Export Structure

Exports use a component-aware layout (v2+):

```
export_YYYYMMDD_HHMMSS/
├── manifest.json            # Root manifest (aggregates component manifests)
├── config/                  # Configuration settings
│   ├── manifest.json        # Config manifest
│   ├── plugin_config.json   # Plugin runtime settings
│   ├── coldfront_config.json # ColdFront-specific settings
│   ├── django_config.json   # Core Django settings
│   └── environment.json     # Environment metadata
├── coldfront_core/
│   ├── manifest.json        # Component manifest
│   └── *.json               # Core data files
└── orcd_plugin/
    ├── manifest.json        # Component manifest
    └── *.json               # Plugin data files
```

Legacy v1 exports are flat (single manifest plus JSON files in one directory). The importer auto-detects the format.

## Export Command (`export_portal_data`)

Run with the `coldfront` management CLI:

```bash
coldfront export_portal_data --output /path/to/backups/    # default: all components, timestamped dir
```

Key options:

| Option | Purpose |
| --- | --- |
| `--output, -o PATH` | Required. Destination directory (timestamped subdir by default). |
| `--component {coldfront_core, orcd_plugin, all}` | Limit export scope (default `all`). |
| `--models <m1,m2>` | Restrict models within the selected component (use with single component). |
| `--exclude <m1,m2>` | Exclude specific models (use with single component). |
| `--list-models` | List available model names and exit. |
| `--no-timestamp` | Write directly into the provided path (no timestamp subdir). |
| `--no-config` | Skip exporting configuration settings. |
| `--dry-run` | Show counts only; do not write files. |
| `--source-url <url>` | Persist portal URL in manifests. |
| `--source-name <name>` | Persist portal display name in manifests. |

Behavior notes:
- Components export independently via registered exporters (`coldfront_core` and `orcd_plugin`).
- Configuration settings are exported by default to the `config/` directory.
- Successful exports write component manifests and a root manifest in the top-level directory.
- Dry runs only log record counts per model.

### Export Examples

- Export all data to a timestamped folder:
  ```bash
  coldfront export_portal_data -o /backups/portal/
  ```
- Export only plugin data:
  ```bash
  coldfront export_portal_data -o /backups/portal/ --component orcd_plugin
  ```
- Preview without writing files:
  ```bash
  coldfront export_portal_data -o /backups/portal/ --dry-run
  ```
- Export without configuration:
  ```bash
  coldfront export_portal_data -o /backups/portal/ --no-config
  ```
- List available models:
  ```bash
  coldfront export_portal_data --list-models
  ```

## Import Command (`import_portal_data`)

Run with the `coldfront` management CLI:

```bash
coldfront import_portal_data /path/to/export_dir
```

Key options:

| Option | Purpose |
| --- | --- |
| `--component {coldfront_core, orcd_plugin, all}` | Limit import scope (default `all`). |
| `--dry-run` | Validate and simulate; no DB writes (transaction rolled back). |
| `--validate` | Validate manifests and compatibility only; do not import. |
| `--mode {create-only, update-only, create-or-update}` | Control how records apply (default `create-or-update`). |
| `--skip-conflicts` | Skip conflicting records instead of failing. |
| `--models <m1,m2>` | Restrict models within the component(s). |
| `--force` | Proceed despite compatibility warnings, config differences, or checksum failures. |
| `--no-verify-checksum` | Skip checksum verification. |
| `--ignore-config-diff` | Skip configuration comparison check. |
| `--config-diff-report PATH` | Write configuration diff report to JSON file. |

Behavior notes:
- The importer auto-detects v2 (component directories) vs v1 (flat) exports.
- For v2, it loads the root manifest, checks per-component compatibility, and imports core first, then plugin.
- Configuration comparison runs before data import (unless `--ignore-config-diff` is used).
- Compatibility errors abort; warnings require `--force` when not running with `--dry-run` or `--validate`.
- Checksum verification runs unless disabled; `--force` can override failures.
- Dry runs and `--validate` do not write data; dry runs still exercise import logic within a rolled-back transaction.

### Import Examples

- Validate only (no DB writes):
  ```bash
  coldfront import_portal_data /backups/portal/export_20260117/ --validate
  ```
- Simulate full import with conflict skipping:
  ```bash
  coldfront import_portal_data /backups/portal/export_20260117/ --dry-run --skip-conflicts
  ```
- Import only plugin data, create new records only:
  ```bash
  coldfront import_portal_data /backups/portal/export_20260117/ --component orcd_plugin --mode create-only
  ```
- Import only core data, forcing through warnings:
  ```bash
  coldfront import_portal_data /backups/portal/export_20260117/ --component coldfront_core --force
  ```
- Import without config comparison:
  ```bash
  coldfront import_portal_data /backups/portal/export_20260117/ --ignore-config-diff
  ```
- Save config diff report to file:
  ```bash
  coldfront import_portal_data /backups/portal/export_20260117/ --config-diff-report /tmp/config_diff.json
  ```

## Configuration Export and Comparison

The export/import system captures and compares configuration settings to help identify differences between portal instances.

### What Gets Exported

Configuration is exported to the `config/` directory with these files:

| File | Contents |
| --- | --- |
| `plugin_config.json` | ORCD plugin runtime settings (center_summary_enable, auto_pi_enable, etc.) |
| `coldfront_config.json` | ColdFront settings (CENTER_NAME, PROJECT_ENABLE_PROJECT_REVIEW, etc.) |
| `django_config.json` | Core Django settings (INSTALLED_APPS, AUTHENTICATION_BACKENDS, DEBUG, etc.) |
| `environment.json` | Runtime metadata (Python/Django/ColdFront versions, hostname, timestamp) |

### What Is NOT Exported (Security)

Sensitive settings are explicitly excluded:
- `SECRET_KEY`, `*PASSWORD*`, `*SECRET*`, `*TOKEN*`
- Database connection strings (only `DATABASE_ENGINE` is exported)
- API keys and OAuth secrets

### Configuration Comparison

When importing, the importer compares exported configuration against the current instance before importing data. Differences are classified by severity:

| Severity | Behavior | Examples |
| --- | --- | --- |
| **Critical** | Blocks import (use `--force` to override) | Missing INSTALLED_APPS, database engine mismatch |
| **Warning** | Displayed prominently | Feature toggles, CENTER_NAME, authentication backends |
| **Info** | Informational only | DEBUG mode, timezone, language code |

### Example Output

```
============================================================
Configuration Comparison
============================================================

DIFFERENCES FOUND (3 settings differ):

[WARNING] auto_pi_enable
  Exported: True
  Current:  False
  Impact: Users may or may not be auto-assigned PI status

[WARNING] CENTER_NAME
  Exported: "MIT ORCD Production"
  Current:  "MIT ORCD Staging"
  Impact: Portal branding/name will differ

[INFO] DEBUG
  Exported: False
  Current:  True

CRITICAL ISSUES: None
```

## Manifests, Checksums, and Compatibility

- **Root manifest (v2)** aggregates component manifests and includes metadata (created timestamp, source portal name/URL, total records, checksum).
- **Component manifests** record per-model counts and are written under each component directory.
- **Checksum**: Verified by default (root checksum for v2, component checksum for v1). Use `--no-verify-checksum` to skip or `--force` to continue after a failure.
- **Compatibility checks** run per component; incompatible status stops the import. Warnings require `--force` to proceed.

## Common Scenarios

- **Backup everything (core + plugin + config):** run export with default options; store the timestamped directory.
- **Migrate plugin-only data:** export/import with `--component orcd_plugin`.
- **Audit what would happen:** use `--dry-run` on export or import.
- **Model-level control:** use `--models` (and optionally `--exclude` on export) when focusing on specific model types.
- **Compare configurations only:** use `--validate` to see config differences without importing.
- **Skip config comparison:** use `--ignore-config-diff` when you know configs differ and don't need the check.
- **Legacy exports:** importer will detect v1 layout automatically and use plugin importers.
