---
title: Pagination
sidebar_label: Pagination
description: How list endpoints return pages, and how to read all rows.
---

# Pagination

Every list endpoint returns one page. It uses the `limit` and `offset` query parameters.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `limit` | 25 (`API_PAGE_SIZE`) | The most rows to return. The largest value is 100 (`API_PAGE_SIZE_MAX`). |
| `offset` | 0 | How many rows to skip. The largest value is 1,000,000. |

A `limit` above the largest value gives `422` `validation_error`. The API does not cut the value
silently. An admin can change the two settings on **Ops > Settings > REST API**.

## The answer

```json
{
  "items": [],
  "count": 132,
  "limit": 25,
  "offset": 0
}
```

| Field | Meaning |
| --- | --- |
| `items` | The rows of this page. |
| `count` | The number of rows in all pages, with your filters applied. |
| `limit` | The page size that the server used. |
| `offset` | The number of rows that the server skipped. |

## Read all rows

Increase `offset` by `limit` until `offset + len(items) >= count`.

```python
import os
import requests

base = "https://your-host/api/v1/news"
headers = {"Authorization": f"Bearer {os.environ['KASH_TOKEN']}"}
offset, rows = 0, []
while True:
    page = requests.get(base, headers=headers, params={"limit": 100, "offset": offset}, timeout=30)
    page.raise_for_status()
    body = page.json()
    rows += body["items"]
    offset += len(body["items"])
    if not body["items"] or offset >= body["count"]:
        break
```

## Order

The order of each list is fixed. It is documented on the page of the endpoint. Rows that are
equal in that order are sorted by their id, so a row does not move between two pages when you
read the pages one after the other.

:::note
New rows can come while you read. A new row at the start moves the other rows down, so a row can
appear on two pages. Use the id of a row to remove duplicates.
:::
