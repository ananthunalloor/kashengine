---
title: Errors
sidebar_label: Errors
description: The error format and every error code of the HTTP API.
---

# Errors

The API reports every error as a **problem document** (RFC 9457). The content type is
`application/problem+json`.

```json
{
  "type": "/docs/api/errors/#validation_error",
  "title": "Unprocessable Content",
  "status": 422,
  "detail": "One or more parameters are not valid.",
  "instance": "/api/v1/reports",
  "code": "validation_error",
  "errors": [
    {"field": "limit", "message": "Must be at most 100.", "type": "less_than_equal"}
  ]
}
```

| Member | Meaning |
| --- | --- |
| `type` | A link to the explanation of the code on this page. |
| `title` | The fixed HTTP status text. |
| `status` | The HTTP status code. |
| `detail` | The text for this case. It is safe to show to a user. It never holds a path, a setting, a stack trace or a secret. |
| `instance` | The path of the request. |
| `code` | A stable code. **Branch on this value, not on `detail`.** |
| `errors` | The wrong parameters. Only for `validation_error`. |

Normal users never see internal errors or configuration problems. The server writes them to the
log.

## Codes

### unauthenticated {#unauthenticated}

Status `401`. The request has no token and no valid session. The answer has
`WWW-Authenticate: Bearer`. Send a token, or sign in.

### invalid_token {#invalid_token}

Status `401`. The `Authorization` header has the wrong form, or the token is unknown, revoked,
or has a wrong secret. The answer has `WWW-Authenticate`. Make a new token.

### token_expired {#token_expired}

Status `401`. The token passed its end date. Make a new token on the Account page.

### subscription_required {#subscription_required}

Status `403`. Subscriptions are required, and the user has no active trial or subscription. Ask
the admin of the site.

### feature_not_available {#feature_not_available}

Status `403`. The user does not have the feature of the endpoint. An admin can remove a feature
from a user. The `detail` names the feature.

### not_found {#not_found}

Status `404`. The item does not exist. For example, there is no report for the date, or no IPO
with the id.

### validation_error {#validation_error}

Status `422`. A parameter is not valid: a wrong type, a value out of range, or a `limit` that
is more than `API_PAGE_SIZE_MAX`. The `errors` list names each wrong parameter.

### rate_limited {#rate_limited}

Status `429`. The client sent too many requests, or too many failed token checks. Read
`Retry-After` (seconds) and wait. See [Rate limits](./rate-limits.md).

### server_error {#server_error}

Status `500`. An error in the server. The `detail` is general. The server logs the cause. Try
again later. If it continues, tell the admin.

### api_disabled {#api_disabled}

Status `503`. A superuser turned the API off. The answer has `Retry-After: 300`.

## How to handle errors in a client

1. If the status is `429` or `503`, wait for `Retry-After` seconds, then try again.
2. If the status is `401`, do not retry with the same token. Get a new token.
3. If the status is `403`, `404` or `422`, the request is wrong. A retry does not help.
4. If the status is `500`, try again with a growing delay (for example 1, 2, 4 seconds).
5. Log the `code` and the `instance`.
