# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Hatchling build hook to generate VERSION_FOOTER.md at install time.

This ensures that when installing from any git branch or tag, the correct
version information is captured (branch/tag name, commit hash, datetime).
"""

import subprocess
from datetime import datetime
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Build hook that generates VERSION_FOOTER.md with git metadata."""

    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        """Generate VERSION_FOOTER.md with current git info.

        Args:
            version: The version being built
            build_data: Build configuration data
        """
        tag = self._get_tag_or_branch()
        commit = self._get_commit_hash()
        datetime_str = datetime.now().strftime("%Y-%m-%d_%H:%M")

        # Write VERSION_FOOTER.md
        version_file = "coldfront_orcd_direct_charge/VERSION_FOOTER.md"
        with open(version_file, "w") as f:
            f.write(f"{tag}\n{commit}\n{datetime_str}\n")

        self.app.display_info(
            f"Generated {version_file}: {tag}-{commit} {datetime_str}"
        )

    def _get_tag_or_branch(self):
        """Get the current git tag (if on a tag) or branch name.

        Returns:
            str: Tag name, branch name, or 'unknown' if git info unavailable
        """
        # First try to get an exact tag match
        try:
            tag = subprocess.check_output(
                ["git", "describe", "--tags", "--exact-match"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            return tag
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Fall back to branch name
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            # Handle detached HEAD (common in CI/pip install from git)
            if branch == "HEAD":
                # Try to get the branch from GITHUB_REF or similar
                return self._get_ref_from_env()
            return branch
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    def _get_ref_from_env(self):
        """Try to get branch/tag info from environment variables.

        When pip installing from git, the HEAD is often detached.
        We can try to get the ref from environment or git commands.

        Returns:
            str: Reference name or 'detached'
        """
        import os

        # Check for GitHub Actions environment
        github_ref = os.environ.get("GITHUB_REF", "")
        if github_ref:
            # refs/heads/branch-name or refs/tags/v1.0.0
            if github_ref.startswith("refs/heads/"):
                return github_ref[11:]  # Remove 'refs/heads/'
            elif github_ref.startswith("refs/tags/"):
                return github_ref[10:]  # Remove 'refs/tags/'

        # Try to get the ref from git (works when installing from git+url@ref)
        try:
            # This might give us the original ref used
            result = subprocess.check_output(
                ["git", "describe", "--tags", "--always"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            return result
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return "detached"

    def _get_commit_hash(self):
        """Get the short commit hash.

        Returns:
            str: Short commit hash or 'unknown' if unavailable
        """
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            return commit
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"
