---
title: Authentication
sidebar_label: Authentication
description: How to authenticate to the HTTP API with a bearer token or a web session.
---

# Authentication

The API knows the caller in one of two ways:

1. A **bearer token**. Use it in programs and scripts.
2. A **web session**. The Swagger UI uses it. You are signed in to the web app, and the browser
   sends the session cookie.

If a request has an `Authorization` header, the API uses the token and does not look at the
session.

## Bearer tokens

Send the token in the `Authorization` header:

```http
Authorization: Bearer ke_1a2b3c4d_<secret>
```

A token has three parts: `ke`, an eight-character public **prefix**, and a 48-character
**secret**. The prefix is not secret. It tells your tokens apart in the list on the Account
page.

### Make a token

1. Sign in to the web app and open **Account**. Verify your email address first. The page shows
   **Send verification email** until you do. Staff and superusers do not need to verify.
2. In **API access**, enter a name for the token and select **Make token**.
3. Copy the token from the box. The page does not show it again.

A token has the access of the user who made it. It never has more. These rules apply:

| Rule | Value |
| --- | --- |
| Most active tokens for one user | 5 (`API_TOKEN_MAX_PER_USER`). Revoke one to make a new one. |
| Life of a new token | 90 days (`API_TOKEN_EXPIRY_DAYS`). The value 0 means no end date. |
| Name | Up to 60 characters. |

### Revoke a token

On the Account page, select **Revoke** next to the token. The token stops working at once. A
superuser can also revoke the tokens of a user on **Ops > Users**.

A token also stops working when:

- it reaches its end date (the error code is `token_expired`);
- the user changes the password (all tokens of the user stop);
- an admin turns the user off.

### How the server keeps tokens

The server never saves the secret. It saves a SHA-256 hash of the full token and the prefix. A
database leak does not give working tokens. The server compares hashes in constant time. It
removes tokens from the logs and from the audit log.

:::warning
Treat a token like a password. Do not put it in a URL, in source code, or in a chat message.
If a token leaks, revoke it.
:::

## Web session

A request from a browser that is signed in to the web app has the session cookie. The API
accepts it for `GET` requests. The Swagger UI works this way. The session has the same access
rules and the same rate limit as a token (the limit counts for the user).

## What the API does when authentication fails

| Case | Status | Code |
| --- | --- | --- |
| No `Authorization` header and no valid session | `401` | `unauthenticated` |
| Wrong form, unknown token, revoked token, or wrong secret | `401` | `invalid_token` |
| The token passed its end date | `401` | `token_expired` |
| The client address made too many failed checks in one minute | `429` | `rate_limited` |

For an unknown token, a wrong secret and a revoked token, the answer text is the same. A client
cannot find out which tokens exist.

Each failed check counts for the client address. After 10 failed checks in one minute
(`API_AUTH_FAIL_LIMIT_PER_MINUTE`), the address gets `429` for the rest of the minute.

## Access after authentication

After the caller is known, the API checks the rules of the web app:

| Check | Error when it fails |
| --- | --- |
| The user has an active trial or subscription (only when subscriptions are required). | `403` `subscription_required` |
| The user has the feature of the endpoint (`reports`, `news`, `ipos`, `markets`, `companies` or `delivery`). | `403` `feature_not_available` |

Staff and superusers have all features and need no subscription. The endpoints `/api/v1/me` and
`/api/v1/health` need no feature. `/api/v1/me` also works for a user whose subscription ended.
That makes it a good first call to test a token.
