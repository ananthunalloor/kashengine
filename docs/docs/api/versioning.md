---
title: Versioning
sidebar_label: Versioning
description: The version policy of the HTTP API, what counts as a breaking change, and the life cycle of a version.
---

# Versioning

## The version in the path

The **major version** is in the URL path: `/api/v1/`. A new major version gets a new path
(`/api/v2/`). The old version stays on while clients move.

`GET /api/` lists the versions, with their status and their links. It needs no sign-in.

## The contract version

Each answer has the header `API-Version`. It holds the full version of the contract, for example
`1.0.0`. The same value is in `info.version` of the OpenAPI file.

| Number | When it goes up |
| --- | --- |
| Major (`1`) | A change that can break a client. It needs a new path. |
| Minor (`1.1.0`) | A new endpoint, a new optional parameter, or a new response field. |
| Patch (`1.0.1`) | A fix to the text of the documentation, or a fix to a bug with no change to the contract. |

## What is a breaking change

These changes are **not allowed inside `v1`**. They need `v2`:

- remove or rename an endpoint, a parameter or a response field;
- change the type, the format or the meaning of a field;
- make an optional parameter required;
- make an allowed value of a parameter narrower;
- change an error `code` or the status of an error;
- remove a value from an enum that a client can read.

These changes are **allowed inside `v1`**:

- add an endpoint;
- add an optional parameter;
- add a field to a response object;
- add a new value to a response enum (for example a new `status`);
- add a new error `code` for a new case.

:::important
Write clients so that they **ignore unknown fields** and handle an **unknown enum value**.
The `data` object of a report can get new keys at any time. Only the keys that the guides name
are part of the contract.
:::

## Life cycle of a version

| Status | Meaning |
| --- | --- |
| `stable` | The version is supported. |
| `deprecated` | The version still works. A successor exists. Plan to move. |
| `retired` | The version stopped. |

Every answer of a deprecated version has these headers (RFC 8594):

| Header | Meaning |
| --- | --- |
| `Deprecation` | The date that the deprecation started. |
| `Sunset` | The date that the version stops, if it is set. |
| `Link` | A link to the successor, with `rel="successor-version"`. |

The policy of the project is to give at least 90 days between the start of a deprecation and
the sunset date. Each change goes in the [changelog](./changelog.md).

## How the version is made in the code

- Each major version has its own `NinjaAPI` object (`apps/api/v1/api.py`).
- The list of versions and their status is `apps/api/versions.py`.
- The OpenAPI file is `docs/openapi/v1.json`. The command
  `python manage.py export_openapi --output docs/openapi/v1.json` writes it. A test fails when the
  file is older than the code, so the file in the repository is always current.
- The script `docs/scripts/openapi_compat.py` compares two OpenAPI files and lists every
  breaking change. CI runs it against the file on the main branch. See
  [Development workflow](../development/workflow.md).
