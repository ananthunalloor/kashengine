---
title: Rate limits
sidebar_label: Rate limits
description: The request limits of the HTTP API, the headers that show them, and how to behave.
---

# Rate limits

The API counts the requests of each caller in **windows of 60 seconds**. A window starts at
the start of a minute of the clock. The count goes back to zero in the next window.

| Limit | Applies to | Default | Setting |
| --- | --- | --- | --- |
| Requests for each minute | Each token. A web session counts for the user. | 60 | `API_RATE_LIMIT_PER_MINUTE` |
| Failed token checks for each minute | Each client address. | 10 | `API_AUTH_FAIL_LIMIT_PER_MINUTE` |

A superuser can change both on **Ops > Settings > REST API**. A change takes effect in a few
seconds.

The counters live in the Django cache. In production the cache is Redis (database 1 of the same
Redis server). If the cache is lost, the counters start again from zero.

## Headers

Each answer for a known caller has these headers:

| Header | Meaning |
| --- | --- |
| `RateLimit-Limit` | The most requests in the window. |
| `RateLimit-Remaining` | How many requests are left in the window. |
| `RateLimit-Reset` | Seconds until the window ends. |
| `RateLimit-Policy` | The policy, for example `60;w=60`. |

## When the limit is passed

The API answers `429` with the code `rate_limited`. The answer has `Retry-After` with the number
of seconds to wait. `RateLimit-Remaining` is `0`.

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json
Retry-After: 23
RateLimit-Limit: 60
RateLimit-Remaining: 0
RateLimit-Reset: 23
```

## Good behavior for a client

- Read `RateLimit-Remaining`. Slow down before it reaches zero.
- When you get `429`, wait for `Retry-After` seconds. Do not retry at once.
- Use `If-None-Match` with the `ETag` of the last answer. A `304` answer still counts as a
  request, but it is small and fast.
- Do not use many tokens to go around the limit. Each token has its own limit, but the failed
  checks count for the address.
