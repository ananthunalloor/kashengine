---
title: API changelog
sidebar_label: Changelog
description: Changes of the HTTP API for each contract version.
---

# API changelog

The format follows [Keep a Changelog](https://keepachangelog.com). The versions follow the
[policy](./versioning.md).

## 1.0.0 (October 2026)

First release of the API.

### Added

- Read-only endpoints under `/api/v1/`:
  `/health`, `/me`, `/reports`, `/reports/{day}`, `/news`, `/ipos`, `/ipos/{ipo_id}`,
  `/markets/outlook`, `/markets/predictions`, `/markets/accuracy`, `/markets/quotes`,
  `/companies` and `/delivery/logs`.
- Bearer tokens that a user makes on the Account page, and session authentication.
- Rate limits for each token and for failed checks for each address.
- Errors in the `application/problem+json` format with stable codes.
- `limit` and `offset` paging, `ETag` and `If-None-Match`.
- The OpenAPI 3.1 file and the Swagger UI at `/api/v1/docs`.
- The `API-Version` header, and the `Deprecation` and `Sunset` headers for the future.
