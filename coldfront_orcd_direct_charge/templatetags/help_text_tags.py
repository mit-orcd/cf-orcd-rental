# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Template tags for loading and rendering help text from markdown files.

This module provides a modular help text system that loads markdown content
from the help_and_notices_text/ directory and renders it as HTML for display in templates.

Usage:
    {% load help_text_tags %}
    {% load_help_text "maintenance_window" %}
"""

from pathlib import Path

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def load_help_text(feature_name):
    """Load and render help text markdown for a feature.

    Loads the markdown file from the help_and_notices_text directory and converts it to HTML.
    If the markdown library is not installed, returns the raw markdown text.
    If the file doesn't exist, returns an empty string.

    Args:
        feature_name: Name of the help text file (without .md extension)

    Returns:
        str: Rendered HTML from the markdown file, or raw text as fallback,
             or empty string if file not found
    """
    help_dir = Path(__file__).parent.parent / "help_and_notices_text"
    help_file = help_dir / f"{feature_name}.md"

    if not help_file.exists():
        return ""

    content = help_file.read_text()

    try:
        import markdown

        html = markdown.markdown(content, extensions=["tables", "fenced_code"])
        return mark_safe(html)
    except ImportError:
        # If markdown not installed, return raw text wrapped in pre tag
        return mark_safe(f"<pre>{content}</pre>")
