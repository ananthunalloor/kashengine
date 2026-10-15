"""The versions of the API and their life cycle.

The major version is in the URL path: `/api/v1/`. Inside one major version, changes only add
things (a new endpoint, a new optional parameter, a new response field). Any change that can
break a client gets a new major version. See `docs/docs/api/versioning.md`.

When a version is deprecated, every response of that version carries the `Deprecation` header
and, if a date is set, the `Sunset` header (RFC 8594), with a `Link` header to the successor.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Version:
    """The state of one major version of the API.

    Attributes:
        major: The path name, for example `v1`.
        semver: The full version of the contract. It is in the OpenAPI file and in the
            `API-Version` header. Raise the minor number when you add something.
        status: `stable`, `deprecated` or `retired`.
        deprecated_on: The day the deprecation started (`YYYY-MM-DD`), or an empty text.
        sunset_on: The day the version stops (`YYYY-MM-DD`), or an empty text.
        successor: The path name of the version that replaces this one, or an empty text.
    """

    major: str
    semver: str
    status: str = "stable"
    deprecated_on: str = ""
    sunset_on: str = ""
    successor: str = ""


VERSIONS: dict[str, Version] = {
    "v1": Version(major="v1", semver="1.0.0"),
}
CURRENT = "v1"
