---
title: Kash Engine developer documentation
slug: /
---

# Kash Engine developer documentation

Kash Engine collects Indian-market financial news, scores news sentiment, estimates the next trading day's market direction, scores IPOs, and delivers reports through Telegram. This site is the developer and operator reference for the Django application.

> **Important:** Kash Engine is an analysis tool, not a source of investment advice. Predictions can be wrong. Do not present an automated score as a guaranteed outcome.

## Start here

- [Set up a development environment](./getting-started.md).
- [Understand the system architecture](./architecture/overview.md) and [data flow](./architecture/data-flow.md).
- [Follow the development and testing workflow](./development/workflow.md).
- [Read the function-documentation standard](./development/function-documentation.md).
- [Operate the application](./operations/dashboard.md), [manage settings](./operations/runtime-configuration.md), and [self-host the service](./operations/self-hosting.md).
- Browse the [generated Python API reference](./reference/generated/index.md). It inventories functions and methods in the application source and includes their signatures, source locations, docstrings, and a coverage report.

## Source-of-truth order

When information differs, use this order:

1. Current source code and migrations.
2. Automated tests for expected behavior.
3. This documentation, which should be updated with code changes.
4. The repository README, which provides a short entry point.

The API reference is generated from the source used at build time. Do not edit generated pages by hand. Improve the function's source docstring and rebuild the site instead.
