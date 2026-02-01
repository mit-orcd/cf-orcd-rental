# Test Environment Setup

This directory contains scripts for setting up a complete ColdFront environment with the plugin installed. The setup is CI-agnostic and works with GitHub Actions, GitLab CI, Woodpecker CI, or local development.

## Quick Start

```bash
./setup_environment.sh
```

This will:
1. Clone ColdFront v1.1.7 to the parent directory
2. Create a Python virtual environment
3. Install ColdFront and the plugin
4. Configure local settings
5. Apply database migrations
6. Initialize the database (initial_setup, manager groups, fixtures)
7. Start the development server

## Files

| File | Description |
|------|-------------|
| `setup_environment.sh` | Main setup script - clones ColdFront, installs packages, configures settings |
| `initialize_database.sh` | Database initialization - runs initial_setup, creates manager groups, loads fixtures |
| `local_settings.py.template` | ColdFront configuration template with plugin settings |
| `README.md` | This documentation |

## Generated Files

After running `setup_environment.sh`, the following files are created:

| File | Location | Description |
|------|----------|-------------|
| `activate_env.sh` | `$WORKSPACE/coldfront/` | Environment activation script that sets up venv, `DJANGO_SETTINGS_MODULE`, and `PYTHONPATH` |
| `local_settings.py` | `$WORKSPACE/coldfront/coldfront/config/` | ColdFront local settings with plugin enabled |

### Using activate_env.sh

The `activate_env.sh` script should be sourced before running any Python code that imports Django models:

```bash
source ../coldfront/activate_env.sh

# Now Django is properly configured
python -c "from django.contrib.auth.models import User; print(User.objects.count())"
```

This script sets:
- `DJANGO_SETTINGS_MODULE=coldfront.config.settings`
- `PYTHONPATH` to include the ColdFront directory
- Activates the Python virtual environment

### Database Initialization

The `initialize_database.sh` script (called automatically by `setup_environment.sh`) performs:

1. **ColdFront initial_setup**: Creates default ColdFront data (fields of science, resource types, etc.)
2. **Manager group creation**: Creates Rental Manager, Billing Manager, and Rate Manager groups with appropriate permissions
3. **Fixture loading**: Loads plugin fixtures (node types, node instances)
4. **Test superuser**: Creates a superuser for testing (username: `admin`, password: `testpass123`)

You can run it independently if needed:

```bash
export COLDFRONT_DIR=/path/to/coldfront
export PLUGIN_DIR=/path/to/plugin
./initialize_database.sh
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COLDFRONT_VERSION` | `1.1.7` | ColdFront version to clone |
| `WORKSPACE` | `../` | Parent directory for ColdFront clone |
| `USE_UV` | `true` | Use `uv` for faster installs (falls back to pip) |
| `RUNNER_TYPE` | `github` | Runner type: `github`, `self-hosted`, `local` |
| `SERVER_PORT` | `8000` | Port for development server |
| `SKIP_SERVER` | `false` | Skip starting the server |
| `SKIP_INIT` | `false` | Skip database initialization (initial_setup, manager groups, fixtures) |
| `SKIP_FIXTURES` | `false` | Deprecated - use `SKIP_INIT` instead |
| `TEST_SUPERUSER` | `admin` | Username for test superuser (used by initialize_database.sh) |
| `TEST_PASSWORD` | `testpass123` | Password for test superuser |

## Usage Examples

### Local Development

```bash
# Full setup with defaults
./setup_environment.sh

# Skip server (you'll start it manually)
SKIP_SERVER=true ./setup_environment.sh

# Use a different ColdFront version
COLDFRONT_VERSION=1.1.8 ./setup_environment.sh

# Use pip instead of uv
USE_UV=false ./setup_environment.sh
```

### CI/CD Integration

#### GitHub Actions

```yaml
- name: Setup Environment
  run: ./tests/setup/setup_environment.sh
  env:
    RUNNER_TYPE: github
```

#### GitLab CI

```yaml
setup:
  script:
    - ./tests/setup/setup_environment.sh
  variables:
    RUNNER_TYPE: gitlab
```

#### Woodpecker CI

```yaml
steps:
  - name: setup
    commands:
      - ./tests/setup/setup_environment.sh
    environment:
      RUNNER_TYPE: woodpecker
```

### Self-Hosted Runners

For self-hosted runners with pre-installed dependencies:

```bash
RUNNER_TYPE=self-hosted ./setup_environment.sh
```

## Directory Structure After Setup

```
your-workspace/
├── coldfront/                          # ColdFront installation
│   ├── .venv/                          # Python virtual environment
│   ├── coldfront/
│   │   └── config/
│   │       ├── local_settings.py       # Generated from template
│   │       └── urls.py                 # Modified to include plugin URLs
│   └── db.sqlite3                      # SQLite database
└── coldfront-orcd-direct-charge/       # This plugin
    └── tests/
        └── setup/                      # This directory
```

## Troubleshooting

### Server won't start

Check the server log:
```bash
cat /tmp/coldfront_server.log
```

### Port already in use

Kill existing processes on the port:
```bash
lsof -ti:8000 | xargs kill -9
```

### Missing dependencies

Ensure you have:
- `git`
- `python3` (3.9+)
- `curl`
- `uv` (optional, for faster installs)

### Migration errors

Try resetting the database:
```bash
rm ../coldfront/db.sqlite3
./setup_environment.sh
```

## Customization

### Custom Settings

Edit `local_settings.py.template` to change default settings. Key options:

```python
# Branding
CENTER_NAME = 'Your Center Name'

# Features
AUTO_PI_ENABLE = True              # Auto-set users as PIs
AUTO_DEFAULT_PROJECT_ENABLE = True  # Auto-create user projects

# Database (for production)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        # ...
    }
}
```

### Using External Database

For CI with PostgreSQL services:

```bash
export DATABASE_URL="postgres://user:pass@localhost:5432/coldfront"
./setup_environment.sh
```

(Requires adding DATABASE_URL support to local_settings.py.template)

