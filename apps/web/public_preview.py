"""Public React presentation using Django's original authentication boundary."""

from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.defaults import permission_denied as django_permission_denied


def preview_response(request: HttpRequest, *, page: str, status: int = 200, **data) -> HttpResponse:
    """Render a public React entry without private session or market data.

    Args:
        request: The incoming browser request.
        page: The public screen identifier.
        status: The original HTTP response status.
        **data: Explicitly selected, non-secret presentation values.

    Returns:
        An uncached shell with safely JSON-encoded presentation data.
    """
    response = render(
        request,
        "web/public_preview.html",
        {
            "preview": {
                "page": page,
                "authenticated": request.user.is_authenticated,
                "csrf": get_token(request),
                **data,
            }
        },
        status=status,
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_not_required
@never_cache
def landing(request: HttpRequest) -> HttpResponse:
    """Serve the anonymous React landing preview.

    Args:
        request: The public browser request.

    Returns:
        The public React landing shell.
    """
    return preview_response(request, page="landing")


class PreviewLogin(LoginView):
    """Use Django's login validation, safe redirects, signals, and axes unchanged."""

    next_page = "/app/dashboard/"
    redirect_authenticated_user = True

    def render_to_response(self, context, **response_kwargs):
        """Expose validation state but never submitted credentials.

        Args:
            context: Django's validated login context and form.
            **response_kwargs: The original response status.

        Returns:
            The React login shell with CSRF and safe redirect state.
        """
        return preview_response(
            self.request,
            page="login",
            status=response_kwargs.get("status", 200),
            next=context.get("next", ""),
            invalid=bool(context["form"].errors),
        )


def permission_denied(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Keep preview permission failures in React without changing legacy responses.

    Args:
        request: The denied browser request.
        exception: The original Django permission failure.

    Returns:
        A React preview 403 or Django's original legacy 403.
    """
    if request.path.startswith("/app/"):
        return preview_response(request, page="access", status=403, feature="This page")
    return django_permission_denied(request, exception)
