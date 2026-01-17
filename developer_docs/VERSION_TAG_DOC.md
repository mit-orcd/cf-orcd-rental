# VERSION_FOOTER.md Auto-Update

## Overview

A GitHub Action automatically updates `coldfront_orcd_direct_charge/VERSION_FOOTER.md` on every push to `main` or when version tags are created.

## How It Works

1. Developer pushes to `main` or creates a tag like `v0.2`
2. GitHub Action runs (`.github/workflows/update-version-footer.yml`)
3. Action captures:
   - **Tag/Branch**: Git tag if on a tag, otherwise branch name (e.g., `main`)
   - **Commit Hash**: Short 7-character hash (e.g., `573b72d`)
   - **Datetime**: Current time in EST format (`YYYY-MM-DD_HH:MM`)
4. Action updates `VERSION_FOOTER.md` and commits with `[skip ci]`

## VERSION_FOOTER.md Format

```
main
f94bb6b
2026-01-17_15:30
```

Three lines:
1. Tag or branch name
2. Short commit hash
3. EST datetime

## Usage in Plugin

The plugin reads this file at runtime to display version info in the footer:

```
Plugin main-f94bb6b 2026-01-17_15:30 EST
```

With a link to the GitHub commit page.

## Workflow File

Location: `.github/workflows/update-version-footer.yml`

Triggers:
- Push to `main` branch
- Push of version tags (`v*`)

The `[skip ci]` in the commit message prevents infinite loops.
