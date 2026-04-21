# Upstream ColdFront core migration copies

> **TL;DR for future maintainers and AI agents.** These five files do **not**
> exist anywhere in the upstream `ubccr/coldfront` git history at any tag
> (including `v1.1.7`, which is what we pin). They are *locally generated*
> migration files that paper over a packaging bug in upstream v1.1.7: its
> committed migrations are stale relative to the model state produced at
> import time by the third-party libraries v1.1.7 itself pins
> (`django-simple-history==3.8.0`, `Django==4.2.23`). `setup_environment.sh`
> copies these files into the freshly-cloned `coldfront/` tree so that
> `migrate` and `initial_setup` no longer warn. See "Why this drift exists"
> below for the full story.

## Why these files exist

ColdFront `v1.1.7` (commit `50c7577`) ships with model definitions in
`coldfront.core.{allocation,grant,publication,research_output,resource}` whose
state diverges from the migration files committed in the same release. As a
result, every invocation of `manage.py migrate` against a clean v1.1.7
checkout prints:

```
Your models in app(s): 'allocation', 'grant', 'publication', 'research_output',
'resource' have changes that are not yet reflected in a migration, and so
won't be applied.
Run 'manage.py makemigrations' to make new migrations, and then re-run
'manage.py migrate' to apply them.
```

The drift is benign (historical model `Meta.get_latest_by`/`Meta.ordering`,
`db_index=True` on `history_date`, validator metadata on a few `Grant` fields,
and a `Resource.linked_resources` field option), but the warning is noisy and
can mask real problems. Inside `setup_environment.sh` it would print **twice**
on every fresh setup — once for the explicit `migrate` step, and again from
inside `coldfront initial_setup`, which calls `migrate` itself.

`tests/setup/setup_environment.sh` drops these files into the cloned
ColdFront tree (under `coldfront/core/<app>/migrations/`) before running
`migrate`, which silences the warning and applies the small set of trailing
schema/metadata adjustments.

These migration files are **owned by upstream ColdFront**, not by this
plugin. We just keep verbatim copies here so the test setup can patch the
cloned tree without depending on `makemigrations` running successfully on
each developer's machine.

## Why this drift exists (root cause)

This is the part that confuses people the first time they look at it. The
filenames (`0006_alter_historicalallocation_options_and_more.py`, etc.) look
like they could have been copied from a later upstream commit. **They were
not.** They do not exist in any tag of `ubccr/coldfront`. The naming is just
Django's standard `makemigrations` autonaming: "the next number after the
highest committed migration in the app, suffixed with a summary of the
operations." If you run `makemigrations` again from scratch you'll get the
same filenames — that's how Django names auto-generated migrations.

The real reason `makemigrations` finds anything to do against an untouched
v1.1.7 source tree is that the *Django model state* doesn't only come from
the `.py` files you can see in `coldfront/core/<app>/models.py`. Two of those
apps' models are heavily generated **at import time** by third-party
libraries that v1.1.7 doesn't pin tightly enough:

- **`django-simple-history`** generates the `HistoricalAllocation`,
  `HistoricalGrant`, `HistoricalPublication`, `HistoricalResearchOutput`,
  `HistoricalResource`, etc. proxy models on the fly whenever ColdFront calls
  `history = HistoricalRecords()` inside a model. Their fields,
  `Meta.get_latest_by`, `Meta.ordering`, and `db_index=True` on `history_date`
  are all decided by the **running** version of `django-simple-history`, not
  by anything in ColdFront's source.
- **`Django` itself** changed how some validator and field metadata
  serializes between releases (this accounts for the `Grant.direct_funding`,
  `Grant.percent_credit`, `Grant.total_amount_awarded` and
  `Resource.linked_resources` items that show up in the dry-run output).

The migrations checked into v1.1.7 (last touched in
`0005_auto_20211117_1413.py` etc.) were generated against an **older**
`django-simple-history` release where:

- `history_date` did *not* have `db_index=True`,
- `Historical*` models did *not* declare
  `Meta.get_latest_by = ('history_date', 'history_id')` or
  `Meta.ordering = ('-history_date', '-history_id')`.

But v1.1.7's `coldfront/uv.lock` resolves:

```
django==4.2.23
django-simple-history>=3.8.0  →  3.8.0
```

So the tree you actually install at v1.1.7 is:

- v1.1.7's model code, plus
- v1.1.7's committed migrations (last frozen against older lib versions),
  plus
- *Newer* `django-simple-history` / `Django` whose runtime model state has
  drifted from those frozen migrations.

Django compares "current in-memory model state" against "migration history on
disk" and sees a delta in those 5 apps — hence the warning. **It is an
upstream-ColdFront packaging issue**: the maintainers shipped v1.1.7 without
re-running `makemigrations` after bumping the pinned dep ranges. Nothing
about your local checkout is wrong.

## What "the error" actually looks like

There is **no Python traceback and no `Error:` line**. That's why people
sometimes ask "what error?" — the symptoms are quieter than that:

| Command | Behaviour on drift |
|---|---|
| `migrate` | Prints the `Your models … have changes that are not yet reflected in a migration` warning at the top, then applies whatever it can. Exits 0. This is the "error" `setup_environment.sh` was hitting twice. |
| `makemigrations --dry-run <apps>` | Prints `Migrations for '<app>': coldfront/core/<app>/migrations/<NNNN>_…py` for each affected app and lists the operations it would write. Exits 0. **This is the "receipt" for the drift** — if it prints anything, you have drift. |
| `makemigrations --check --dry-run <apps>` | Same detection, but **exits non-zero** if any migrations would be created. This is the CI-style gate the `--check` safety net in `setup_environment.sh` uses. |

## Verifying the drift (and the fix) yourself

If you want to convince yourself the drift is real and lives upstream — not
in this repo or in your local environment — do this in a scratch directory
**outside** this project (no plugin, no `setup_environment.sh`):

```bash
rm -rf /tmp/cfcheck && \
git clone --depth 1 --branch v1.1.7 \
    https://github.com/ubccr/coldfront.git /tmp/cfcheck
cd /tmp/cfcheck
uv sync                       # uses upstream's own uv.lock
git status                    # working tree clean, on tag v1.1.7

# 1) Drift "receipt" — should print 5 proposed migrations:
uv run coldfront makemigrations --dry-run \
    allocation grant publication research_output resource

# 2) CI-style gate — should exit non-zero on drifted v1.1.7:
uv run coldfront makemigrations --check --dry-run \
    allocation grant publication research_output resource ; echo "exit=$?"

# 3) Migrate-time warning — should print
#    "Your models in app(s): 'allocation', … have changes that are not yet
#     reflected in a migration, and so won't be applied." near the top:
uv run coldfront migrate --no-input 2>&1 | head -30
```

You should observe, on a clean v1.1.7 with nothing of ours involved:

- step 1 prints exactly the 5 files this directory holds,
- step 2 prints `exit=1`,
- step 3 prints the warning, then applies the rest of the migrations.

That confirms the drift is in upstream v1.1.7 + its own pinned deps, not in
anything we do.

To verify the **fix**, do the same but copy the vendored files in first:

```bash
rm -rf /tmp/cfcheck && \
git clone --depth 1 --branch v1.1.7 \
    https://github.com/ubccr/coldfront.git /tmp/cfcheck
cd /tmp/cfcheck
uv sync

VENDORED=/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental-localhost/tests/setup/upstream_migration_copies
for app in allocation grant publication research_output resource; do
    cp "$VENDORED/$app"/*.py "coldfront/core/$app/migrations/"
done

# Now both should be quiet:
uv run coldfront makemigrations --check --dry-run \
    allocation grant publication research_output resource ; echo "exit=$?"
uv run coldfront migrate --no-input 2>&1 | head -30
```

After patching, expect `exit=0` and no "have changes that are not yet
reflected in a migration" warning anywhere in the migrate output. This is the
exact transformation `setup_environment.sh` performs on the cloned tree
before its own `migrate` step.

## Provenance

The 5 migration files in this directory were generated once by:

1. Cloning ColdFront `v1.1.7` (`https://github.com/ubccr/coldfront.git`,
   commit `50c7577`).
2. Creating a venv and installing ColdFront with the dependency versions
   pinned by upstream `uv.lock`, notably:
   - `Django==4.2.23`
   - `django-simple-history==3.8.0`
   - `django-model-utils==5.0.0`
3. Running:
   ```
   python manage.py makemigrations \
       allocation grant publication research_output resource
   ```
4. Copying the resulting files here and replacing the
   `# Generated by Django ... on <timestamp>` header with a stable
   `# Upstream-migration copy kept by ...` line so the files are
   diff-stable.

## Regenerating after bumping `COLDFRONT_VERSION`

When `tests/setup/setup_environment.sh` is updated to a new
`COLDFRONT_VERSION` (or upstream bumps `django-simple-history` / `Django` in
its `uv.lock`), regenerate this directory:

1. Run `setup_environment.sh` once with the new version to clone ColdFront
   and install dependencies, but stop before/ignore the migrate step. (If
   the script aborts because `migrate` complains about drift, that's fine —
   the clone and `uv sync` have already happened by then.)
2. From inside the cloned `coldfront/` directory, with its `.venv` active,
   first probe whether drift still exists:
   ```
   uv run coldfront makemigrations --check --dry-run \
       allocation grant publication research_output resource ; echo "exit=$?"
   ```
   - `exit=0` and no output → upstream fixed the drift in this release;
     **empty this directory** (and let the copy step in
     `setup_environment.sh` become a no-op or be removed).
   - `exit=1` with a list of proposed migrations → continue.
3. Generate the new files:
   ```
   uv run coldfront makemigrations \
       allocation grant publication research_output resource
   ```
4. For each newly produced file under
   `coldfront/coldfront/core/<app>/migrations/`:
   - Copy it into this directory under `upstream_migration_copies/<app>/`.
   - Replace the `# Generated by Django ... on <timestamp>` header line with:
     ```
     # Upstream-migration copy kept by cf-orcd-rental-localhost/tests/setup. See ../README.md.
     ```
     so the file is diff-stable across regenerations.
   - Delete any files here that are no longer needed (e.g. an app that used
     to drift but no longer does).
5. Update the **Provenance** section above with the new `COLDFRONT_VERSION`,
   commit hash, and the resolved versions of `Django`,
   `django-simple-history`, and `django-model-utils`.
6. Re-run `setup_environment.sh` against a clean tree
   (`rm -fr ../coldfront`) and confirm that:
   - `migrate` reports no "changes that are not yet reflected in a
     migration" warning, and
   - the `makemigrations --check --dry-run` safety net at the end of the
     migrate block exits 0 (no `log_warn` line about new model drift).
7. Run the full test suite (`tests/run_all_tests.sh`) to confirm the
   regenerated migrations don't break anything.

## Layout

```
upstream_migration_copies/
├── README.md
├── allocation/
│   └── 0006_alter_historicalallocation_options_and_more.py
├── grant/
│   └── 0003_alter_historicalgrant_options_and_more.py
├── publication/
│   └── 0005_alter_historicalpublication_options_and_more.py
├── research_output/
│   └── 0002_alter_historicalresearchoutput_options_and_more.py
└── resource/
    └── 0003_alter_historicalresource_options_and_more.py
```

Each migration declares `dependencies = [(<app>, '<existing v1.1.7
migration>')]` so it chains cleanly onto the migrations that already ship
with ColdFront v1.1.7.
