# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Template tag for plugin version information.

Reads VERSION_FOOTER.md to provide version details for the footer.
"""

import os
from django import template

register = template.Library()

GITHUB_REPO = "https://github.com/mit-orcd/cf-orcd-rental"


@register.simple_tag
def get_plugin_version():
    """Read VERSION_FOOTER.md and return version info dict.

    Returns:
        dict: Version information with keys:
            - tag: Git tag or branch name (e.g., "v0.2" or "main")
            - commit: Short commit hash (e.g., "573b72d")
            - datetime: Build datetime in EST (e.g., "2026-01-17_15:30")
            - github_url: URL to the commit on GitHub
    """
    version_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "VERSION_FOOTER.md"
    )
    try:
        with open(version_file, "r") as f:
            lines = f.read().strip().split("\n")
        tag = lines[0].strip() if len(lines) > 0 else "unknown"
        commit = lines[1].strip() if len(lines) > 1 else "unknown"
        datetime = lines[2].strip() if len(lines) > 2 else "unknown"
        return {
            "tag": tag,
            "commit": commit,
            "datetime": datetime,
            "github_url": f"{GITHUB_REPO}/tree/{commit}",
        }
    except Exception:
        return {
            "tag": "unknown",
            "commit": "unknown",
            "datetime": "unknown",
            "github_url": GITHUB_REPO,
        }
