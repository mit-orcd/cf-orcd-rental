# Exporter & Importer Reference

This guide documents the management commands that export or import portal data for ColdFront core and the ORCD plugin. It summarizes directory layout, command options, and validation/compatibility behaviors.

## Export Structure

Exports use a component-aware layout (v2):

```
export_YYYYMMDD_HHMMSS/
├── manifest.json            # Root manifest (aggregates component manifests)
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
| `--dry-run` | Show counts only; do not write files. |
| `--source-url <url>` | Persist portal URL in manifests. |
| `--source-name <name>` | Persist portal display name in manifests. |

Behavior notes:
- Components export independently via registered exporters (`coldfront_core` and `orcd_plugin`).
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
| `--force` | Proceed despite compatibility warnings or checksum failures. |
| `--no-verify-checksum` | Skip checksum verification. |

Behavior notes:
- The importer auto-detects v2 (component directories) vs v1 (flat) exports.
- For v2, it loads the root manifest, checks per-component compatibility, and imports core first, then plugin.
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

## Manifests, Checksums, and Compatibility

- **Root manifest (v2)** aggregates component manifests and includes metadata (created timestamp, source portal name/URL, total records, checksum).
- **Component manifests** record per-model counts and are written under each component directory.
- **Checksum**: Verified by default (root checksum for v2, component checksum for v1). Use `--no-verify-checksum` to skip or `--force` to continue after a failure.
- **Compatibility checks** run per component; incompatible status stops the import. Warnings require `--force` to proceed.

## Common Scenarios

- **Backup everything (core + plugin):** run export with default options; store the timestamped directory.
- **Migrate plugin-only data:** export/import with `--component orcd_plugin`.
- **Audit what would happen:** use `--dry-run` on export or import.
- **Model-level control:** use `--models` (and optionally `--exclude` on export) when focusing on specific model types.
- **Legacy exports:** importer will detect v1 layout automatically and use plugin importers.
