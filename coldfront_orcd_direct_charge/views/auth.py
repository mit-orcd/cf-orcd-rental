# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Authentication views for the ORCD Rental Portal.

Provides optional username/password login when enabled via runtime config,
as an alternative to the default OIDC/Touchstone authentication.
"""

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.views import View


class PasswordLoginView(View):
    """Handle password login when enabled via runtime config.

    This view provides an alternative username/password login form that
    bypasses OIDC authentication. It is only accessible when:
    1. PASSWORD_LOGIN_ENABLE is True in settings (via plugin_config.yaml)
    2. The ?opt=password query parameter is present in the URL

    If either condition is not met, the view redirects to OIDC authentication.
    """

    def dispatch(self, request, *args, **kwargs):
        """Check if password login is enabled before processing the request."""
        # If password login disabled or no opt=password param, redirect to OIDC
        if not getattr(settings, "PASSWORD_LOGIN_ENABLE", False):
            return redirect("oidc_authentication_init")
        if request.GET.get("opt") != "password":
            return redirect("oidc_authentication_init")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        """Display the username/password login form."""
        form = AuthenticationForm()
        return render(request, "user/login_password.html", {"form": form})

    def post(self, request):
        """Process the login form submission."""
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get("next", "/")
            return redirect(next_url)
        return render(request, "user/login_password.html", {"form": form})
