# VERSION_FOOTER.md Documentation

## Overview

A GitHub Action automatically updates `coldfront_orcd_direct_charge/VERSION_FOOTER.md` on every push to `main` or when version tags are created. This document covers both the automatic update system and the manual process for creating tagged releases.

## VERSION_FOOTER.md Format

```
main
f94bb6b
2026-01-17_15:30
```

Three lines:
1. Tag or branch name (e.g., `v1.0` or `main`)
2. Short commit hash (7 characters)
3. EST datetime (`YYYY-MM-DD_HH:MM`)

## Automatic Updates (GitHub Action)

### How It Works

1. Developer pushes to `main` or creates a tag like `v0.2`
2. GitHub Action runs (`.github/workflows/update-version-footer.yml`)
3. Action captures:
   - **Tag/Branch**: Git tag if on a tag, otherwise branch name (e.g., `main`)
   - **Commit Hash**: Short 7-character hash (e.g., `573b72d`)
   - **Datetime**: Current time in EST format (`YYYY-MM-DD_HH:MM`)
4. Action updates `VERSION_FOOTER.md` and commits with `[skip ci]`

### Workflow File

Location: `.github/workflows/update-version-footer.yml`

Triggers:
- Push to `main` branch
- Push of version tags (`v*`)

The `[skip ci]` in the commit message prevents infinite loops.

## Creating a Tagged Release

### The Commit Hash Constraint

There is a fundamental constraint when creating tagged releases:

1. You want VERSION_FOOTER.md to contain both the **tag name** and the **commit SHA**
2. But modifying VERSION_FOOTER.md creates a **new commit** with a different SHA
3. **Tags are immutable** - once created and pushed, they cannot be modified
4. The GitHub Action **cannot push changes** when triggered by a tag push (runs on detached HEAD)

**Bottom line**: The commit hash in VERSION_FOOTER.md will be the **parent commit's hash**, not the tagged commit itself. This is unavoidable because the hash is computed from the file contents, including VERSION_FOOTER.md itself.

### Prerequisites

Before creating a tagged release:

- All development work for the release is complete
- All changes have been pushed to `main`
- The GitHub Action has run and updated VERSION_FOOTER.md
- You have pulled the latest changes locally

### Step-by-Step Procedure

#### Step 1: Ensure main is up-to-date

```bash
cd cf-orcd-rental
git checkout main
git pull origin main
```

Verify the GitHub Action has updated VERSION_FOOTER.md:

```bash
cat coldfront_orcd_direct_charge/VERSION_FOOTER.md
```

You should see something like:
```
main
dc42a0d
2026-01-20_20:58
```

#### Step 2: Edit VERSION_FOOTER.md

Edit the file to set the tag name:

```bash
# Get current datetime in EST format
DATETIME=$(TZ="America/New_York" date +"%Y-%m-%d_%H:%M")

# Get current commit hash (this will be the parent of the release commit)
COMMIT=$(git rev-parse --short HEAD)

# Create the new VERSION_FOOTER.md with the tag name
cat > coldfront_orcd_direct_charge/VERSION_FOOTER.md << EOF
v1.0
${COMMIT}
${DATETIME}
EOF
```

Or edit manually:
- **Line 1**: Change from `main` to your tag name (e.g., `v1.0`)
- **Line 2**: Keep the existing commit hash (it references the parent commit)
- **Line 3**: Update to current datetime (optional)

#### Step 3: Commit with [skip ci]

Commit the change with `[skip ci]` in the message to prevent the GitHub Action from overwriting your changes:

```bash
git add coldfront_orcd_direct_charge/VERSION_FOOTER.md
git commit -m "[skip ci] Prepare release v1.0"
```

**Important**: The `[skip ci]` marker is critical. Without it, the GitHub Action would run on this push and change the tag name back to `main`.

#### Step 4: Create the tag

Create an annotated tag pointing to the release commit:

```bash
git tag -a v1.0 -m "Release v1.0"
```

Or create a lightweight tag:

```bash
git tag v1.0
```

#### Step 5: Push branch and tag

Push both the branch and the tag to the remote:

```bash
git push origin main --tags
```

Or push separately:

```bash
git push origin main
git push origin v1.0
```

### Complete Example

Here's a complete walkthrough for releasing version `v1.0`:

```bash
# 1. Ensure you're on main and up-to-date
cd cf-orcd-rental
git checkout main
git pull origin main

# 2. Verify current VERSION_FOOTER.md
cat coldfront_orcd_direct_charge/VERSION_FOOTER.md
# Output should show: main, <hash>, <datetime>

# 3. Update VERSION_FOOTER.md for the release
DATETIME=$(TZ="America/New_York" date +"%Y-%m-%d_%H:%M")
COMMIT=$(git rev-parse --short HEAD)

cat > coldfront_orcd_direct_charge/VERSION_FOOTER.md << EOF
v1.0
${COMMIT}
${DATETIME}
EOF

# 4. Commit with [skip ci]
git add coldfront_orcd_direct_charge/VERSION_FOOTER.md
git commit -m "[skip ci] Prepare release v1.0"

# 5. Create the tag
git tag -a v1.0 -m "Release v1.0"

# 6. Push everything
git push origin main --tags

# 7. Verify on GitHub
echo "Tag created. Verify at: https://github.com/mit-orcd/cf-orcd-rental/releases/tag/v1.0"
```

## Important Notes

### Why the commit hash is one behind

The VERSION_FOOTER.md in the tagged commit contains the **parent commit's hash**, not its own. This is because:

1. Git computes the commit hash from all file contents
2. If VERSION_FOOTER.md contained its own hash, changing the hash would change the file, which would change the hash (infinite loop)
3. This is a fundamental Git limitation, not a bug

When users click the commit link in the footer, they'll see the parent commit. The actual tagged code is one commit ahead.

### The [skip ci] requirement

The GitHub Action at `.github/workflows/update-version-footer.yml` triggers on all branch pushes. Without `[skip ci]`:

1. You push the release commit
2. The action runs and overwrites VERSION_FOOTER.md with `main` instead of `v1.0`
3. The action commits this change
4. Your tag now points to a commit that says `main`, not `v1.0`

### Tag immutability

Once a tag is pushed to GitHub:

- It cannot be modified (without force-pushing, which breaks anyone who pulled it)
- The VERSION_FOOTER.md content is permanent
- If you made a mistake, you must delete and recreate the tag

### Order of operations

The order is critical:

1. Edit VERSION_FOOTER.md
2. Commit with `[skip ci]`
3. Create tag
4. Push

If you create the tag before committing, or push before tagging, you'll need to start over.

## Troubleshooting

### Problem: Pushed without [skip ci] and action overwrote VERSION_FOOTER.md

**Solution**: 
1. Delete the remote tag: `git push origin --delete v1.0`
2. Delete the local tag: `git tag -d v1.0`
3. Reset to before the action's commit: `git reset --hard HEAD~1`
4. Start the procedure again from Step 2

### Problem: Created tag before committing VERSION_FOOTER.md change

**Solution**:
1. Delete the tag: `git tag -d v1.0`
2. Continue from Step 3 (commit)

### Problem: VERSION_FOOTER.md shows wrong tag name after push

**Solution**: Check if the GitHub Action ran (look for a commit with message "Update VERSION_FOOTER.md"). If so:
1. Delete remote tag: `git push origin --delete v1.0`
2. Pull: `git pull origin main`
3. Start procedure from Step 2, ensuring `[skip ci]` is in the commit message

### Problem: Forgot to pull latest before starting

**Solution**:
1. `git fetch origin`
2. Check if there are upstream changes: `git log HEAD..origin/main`
3. If there are changes, reset and pull: `git reset --hard origin/main`
4. Start procedure from Step 1

## Usage in Plugin

The plugin reads this file at runtime to display version info in the footer:

```
Plugin main-f94bb6b 2026-01-17_15:30 EST
```

With a link to the GitHub commit page.
