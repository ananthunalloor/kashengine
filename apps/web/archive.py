"""Hostname isolation and superuser-only access for archived Django pages."""

from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.signals import user_login_failed
from django.contrib.auth.views import LoginView, redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.http.request import split_domain_port
from django.shortcuts import render


class ArchiveAuthenticationForm(AuthenticationForm):
    """Do not establish archive sessions for ordinary members or staff."""

    def confirm_login_allowed(self, user) -> None:
        """Require an active superuser after the normal password check.

        Args:
            user: The user authenticated by Django's authentication backends.

        Raises:
            ValidationError: If the account cannot access the archived UI.
        """
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            # Authentication succeeded, so Django has not emitted the failure signal axes needs.
            user_login_failed.send(
                sender=__name__, credentials={"username": user.get_username()}, request=self.request
            )
            raise self.get_invalid_login_error()


class ArchiveLogin(LoginView):
    """Public credential entry; successful login is restricted to superusers."""

    template_name = "registration/login.html"
    authentication_form = ArchiveAuthenticationForm
    next_page = "/dashboard/"
    redirect_authenticated_user = False


def archive_not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """Return an archived missing-page screen without exposing URL details.

    Args:
        request: The superuser's archived browser request.
        exception: The original resolver or missing-resource exception.

    Returns:
        An archived HTTP 404 page.
    """
    return render(request, "web/archive_status.html", {"missing": True}, status=404)


class ArchiveMiddleware:
    """Select the archive URLconf by validated Host, then authorize every resolved view."""

    def __init__(self, get_response):
        """Store the next middleware or view handler.

        Args:
            get_response: The next callable in Django's middleware chain.
        """
        self.get_response = get_response

    def __call__(self, request):
        """Select host-specific routes and mark archive responses private and unindexed.

        Args:
            request: The request before URL resolution and authentication.

        Returns:
            The selected view's response with archive cache and indexing headers.
        """
        domain, _port = split_domain_port(request.get_host())
        request.is_archive = domain == settings.OLD_SITE_ADDRESS.lower().rstrip(".")
        if request.is_archive:
            request.urlconf = "config.legacy_urls"
        response = self.get_response(request)
        if request.is_archive:
            response["Cache-Control"] = "private, no-store"
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Require an active superuser for every archived page and action except login.

        Args:
            request: The request after authentication middleware.
            view_func: The resolved archived view.
            view_args: Positional URL arguments.
            view_kwargs: Named URL arguments.

        Returns:
            A login redirect or 403 for denied access, otherwise no response.
        """
        if not request.is_archive:
            return None
        if request.path == "/login/":
            return None
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="/login/")
        if not user.is_active or not user.is_superuser:
            return render(request, "web/archive_status.html", status=403)
        return None
