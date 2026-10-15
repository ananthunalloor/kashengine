"""The API object of version 1.

Importing this module builds the router tree. `docs/openapi/v1.json` is made from it.
"""

from functools import wraps

from django.http import HttpRequest
from ninja import NinjaAPI

from .. import errors
from ..auth import identify
from ..versions import VERSIONS
from . import companies, delivery, ipos, markets, news, reports, service

DESCRIPTION = """\
Read-only access to the Kash Engine data: daily reports, scored news, IPOs, the market
prediction, companies and the delivery log.

## Authentication

Send a token in the `Authorization` header:

    Authorization: Bearer ke_<prefix>_<secret>

Make a token on the **Account** page of the web app. The secret is shown once. A signed-in
browser session also works (this is how the Swagger page calls the API).

## Access rules

The API follows the same rules as the web app. A user needs the feature of an endpoint, and
needs an active subscription if the site requires one.

## Errors

Errors use `application/problem+json` (RFC 9457). Branch on the `code` member.

## Limits

Each token has a request limit for each minute. The headers `RateLimit-Limit`,
`RateLimit-Remaining` and `RateLimit-Reset` show the state. A client over the limit gets `429`
and `Retry-After`.

## Versions

The version is in the path. Inside `v1` changes only add things. The `API-Version` header gives
the full version of the contract.
"""


def sign_in_required(view):
    """Protect the OpenAPI file: a signed-in user or a valid token only.

    Args:
        view: The view function that ninja made.

    Returns:
        The same view, or a problem answer when the caller is not known.
    """

    @wraps(view)
    def wrapped(request: HttpRequest, *args, **kwargs):
        """Call the view for a known caller. Answer with a problem for any other caller."""
        try:
            user = identify(request)
        except errors.ApiError as exc:
            return errors.problem(request, exc.code, exc.detail, headers=exc.headers)
        if user is None:
            return errors.problem(
                request,
                "unauthenticated",
                "Send a Bearer token in the Authorization header, or sign in.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return view(request, *args, **kwargs)

    return wrapped


api = NinjaAPI(
    title="Kash Engine API",
    version=VERSIONS["v1"].semver,
    description=DESCRIPTION,
    urls_namespace="api-v1",
    docs_url=None,
    openapi_url="/openapi.json",
    docs_decorator=sign_in_required,
)
errors.install(api)
for _router in (
    service.public,
    service.account,
    reports.router,
    news.router,
    ipos.router,
    markets.router,
    companies.router,
    delivery.router,
):
    api.add_router("", _router)
