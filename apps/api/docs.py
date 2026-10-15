"""The Swagger UI page of the API."""

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from apps.siteconfig import conf

from .versions import VERSIONS


def swagger(request: HttpRequest, version: str = "v1") -> HttpResponse:
    """Show the interactive API page.

    The page needs a web login (the login middleware sends an anonymous visitor to the sign-in
    page). It loads the OpenAPI file of the same version.

    Args:
        request: The request.
        version: The path name of the API version, for example `v1`.

    Returns:
        The HTML page.

    Raises:
        Http404: If an admin turned the page off or the version does not exist.
    """
    if not conf.API_DOCS_ENABLED or version not in VERSIONS:
        raise Http404
    context = {"version": VERSIONS[version].semver, "spec_url": f"/api/{version}/openapi.json"}
    return render(request, "api/swagger.html", context)
