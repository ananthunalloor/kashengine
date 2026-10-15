---
title: Kash Engine developer documentation
slug: /
---

# Kash Engine developer documentation

Kash Engine is a bot for the Indian market. It reads financial news, scores the sentiment of each
article with a local language model, predicts the direction of the Nifty 50 for the next trading
day, scores IPOs, and sends a daily report on Telegram. A web app shows all the data. A
read-only HTTP API gives the same data to other programs.

This site is for the developers and the operators of Kash Engine.

:::caution
Kash Engine is an analysis tool. It does not give investment advice. A prediction can be wrong.
Do not present a score as a sure result.
:::

## Find what you need

| I want to... | Go to |
| --- | --- |
| Run the project on my computer | [Getting started](./getting-started.md) |
| Understand how the parts fit | [Architecture overview](./architecture/overview.md) and [Data flow](./architecture/data-flow.md) |
| Call the API from my program | [HTTP API overview](./api/overview.md), then the [endpoint reference](./reference/generated/http/index.md) |
| Know how a part of the product works | [News](./domains/news.md), [Companies](./domains/companies.md), [Markets](./domains/markets-and-predictions.md), [IPOs](./domains/ipos.md), [Reports and delivery](./domains/reports-and-delivery.md) |
| Run and configure a server | [Self-hosting](./operations/self-hosting.md), [Settings](./operations/runtime-configuration.md), [Scheduling](./operations/scheduling.md) |
| Find a setting, a task or a command | [System reference](./reference/generated/system/settings.md) |
| Look up a function | [Python reference](./reference/generated/python/index.md) |
| Change the code | [Development workflow](./development/workflow.md), [Testing](./development/testing.md), [Docstring standard](./development/docstring-standard.md) |

## How this documentation is made

Some pages are written by hand (the guides). Other pages are **generated from the source code**
at build time, so they cannot differ from the code:

| Generated pages | Made from |
| --- | --- |
| [HTTP API reference](./reference/generated/http/index.md) | The OpenAPI file `docs/openapi/v1.json`, which the code exports. |
| [Python reference](./reference/generated/python/index.md) | The docstrings of every module, class and function. |
| [Settings](./reference/generated/system/settings.md), [Schedule](./reference/generated/system/schedule.md), [Jobs](./reference/generated/system/jobs.md), [Tasks](./reference/generated/system/tasks.md), [Commands](./reference/generated/system/commands.md), [Routes](./reference/generated/system/routes.md) | The registry, the defaults, and the code that registers them. |

To change a generated page, change the source code or the docstring. See
[Documentation site](./development/documentation-site.md).

## When sources differ

If two sources say different things, trust them in this order:

1. The source code and the migrations.
2. The automated tests.
3. This documentation. Fix it when you find an error.
4. The README, which is a short entry point.
