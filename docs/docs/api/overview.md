---
title: HTTP API overview
sidebar_label: Overview
description: What the Kash Engine HTTP API is, how to call it, and where to find each part.
---

# HTTP API overview

The Kash Engine HTTP API gives read-only access to the data of the application. It returns JSON.
You can use it to read the daily reports, the scored news, the IPOs, the market prediction, the
companies and the delivery log from your own program.

The API has the version `v1`. Its base path is `/api/v1/`.

## What the API can do

| Group | What you can read | Feature that you need |
| --- | --- | --- |
| Reports | The list of daily reports, and one report with its full text and data. | `reports` |
| News | Scored news articles, with the sentiment and the linked companies. | `news` |
| IPOs | The list of IPOs, and one IPO with the inputs of its score. | `ipos` |
| Markets | The newest prediction, the past predictions, the accuracy, and the newest quotes. | `markets` |
| Companies | The list of companies. | `companies` |
| Delivery | The attempts to send a report. | `delivery` |
| Service | A health check, and the caller (`/me`). | None |

The API cannot change data. Every endpoint uses the `GET` method.

## Make your first call

1. Sign in to the web app and open the **Account** page.
2. In **API access**, enter a name and select **Make token**. Copy the token. The page shows it
   one time only.
3. Send a request with the token:

```bash
curl -s https://your-host/api/v1/me \
  -H "Authorization: Bearer $KASH_TOKEN"
```

A good answer looks like this:

```json
{
  "id": 7,
  "username": "anan",
  "is_staff": false,
  "subscription_required": false,
  "subscription": null,
  "features": ["reports", "news", "ipos", "markets", "companies", "delivery"],
  "token": {
    "name": "Excel",
    "prefix": "1a2b3c4d",
    "created_at": "2026-10-12T03:45:00Z",
    "expires_at": "2027-01-10T03:45:00Z",
    "last_used_at": null
  }
}
```

If the call fails, read [Errors](./errors.md).

## Rules that apply to every endpoint

- **Same access as the web app.** The API uses the same rules as the web pages. A user needs the
  feature of the endpoint. If an admin turned on subscriptions, the user also needs an active trial
  or subscription. A staff user needs neither.
- **Rate limit.** Each token has a limit for each minute. See [Rate limits](./rate-limits.md).
- **Paging.** List endpoints return one page. See [Pagination](./pagination.md).
- **Errors.** Errors use `application/problem+json`. See [Errors](./errors.md).
- **Caching.** Each `200` answer has an `ETag`. Send it back in `If-None-Match` to get `304`
  with no body when the data did not change. The answers are `private`. A shared cache must not
  keep them.
- **Time.** A date-time value is in ISO 8601 format in UTC, with the letter `Z`, for example
  `2026-10-12T03:45:00Z`. A date value is a calendar day, for example `2026-10-12`. The days of
  the reports and the market data are days in IST (Asia/Kolkata).
- **Version.** Each answer has the header `API-Version` with the full version of the contract.
  See [Versioning](./versioning.md).

## Tools

| Tool | Where |
| --- | --- |
| Swagger UI | `/api/v1/docs`. You must be signed in to the web app. The page can call the API with your session. |
| OpenAPI file | `/api/v1/openapi.json` (sign in or send a token). A copy is at [`/docs/openapi/v1.json`](pathname:///docs/openapi/v1.json). |
| Endpoint reference | [HTTP API reference](../reference/generated/http/index.md). The pages are made from the OpenAPI file. |

You can make a client with any OpenAPI generator. Use the OpenAPI file as the input.

## Turn the API off

A superuser can turn the API off on **Ops > Settings > REST API** (`API_ENABLED`). Every address
below `/api/` then answers `503` with the code `api_disabled`. The web pages do not change.
