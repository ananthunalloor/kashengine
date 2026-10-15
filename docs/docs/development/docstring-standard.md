---
title: Docstring standard
sidebar_label: Docstring standard
description: What every module, class, function and method docstring must contain, and how CI checks it.
---

# Docstring standard

Every module, class, function and method in `apps/`, `config/` and `manage.py` has a docstring.
The [Python reference](../reference/generated/python/index.md) is made from these docstrings. A
developer must be able to change the code safely after reading the docstring.

The style is Google style (Ruff `convention = "google"`). The text follows
[ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/): short sentences, active
voice, simple words, and the same word for the same thing.

## What the generator checks

`npm run reference:check` (and CI) fails when a definition breaks one of these rules:

| Definition | Rule |
| --- | --- |
| Module | Has a docstring with a summary line. |
| Class | Has a docstring with a summary line. |
| Function or method | Has a summary line. |
| Function or method with parameters | Has an `Args:` section that lists **every** parameter by its real name. It lists no name that is not a parameter. |
| Function or method with a return type other than `None` | Has a `Returns:` section (or `Yields:` for a generator). |
| Function or method with an explicit `raise` | Has a `Raises:` section. |

These definitions are exempt:

- Properties need only a summary. A function with one statement and no parameters needs no
  `Returns:`.
- Dunder methods and nested functions need only a summary.
- A django-ninja route function (`@router.get("/path", ...)`) needs only a summary and a
  body. Its docstring is the public description in the OpenAPI file, so it must not have
  `Args:` or `Returns:` sections. The OpenAPI file describes the parameters and the answer.
- Django `Meta` classes and `@overload` stubs need no docstring.

The checks are mechanical. They find missing parts, not wrong text. The review decides whether
the text is true.

## Sections

Use the sections in this order. Add a section only when it is true and useful.

```python
def next_after(cron: crontab, after: datetime) -> datetime:
    """Return the first run time of a cron schedule that is later than `after`.

    Celery computes the next run in the clock of the schedule. With `USE_TZ` on, that clock is
    UTC, so a plain call gives a time that is hours wrong for an IST schedule. This function
    first converts `after` into the zone of the schedule, then adds the remaining time.

    Args:
        cron: A Celery crontab made by `parse_cron`. It must carry its own `nowfun`.
        after: The reference time. It must be timezone-aware.

    Returns:
        An aware datetime in the zone of the schedule.

    Raises:
        ValueError: If `after` is naive.

    Note:
        The result is never earlier than or equal to `after`.
    """
```

| Part | Content |
| --- | --- |
| Summary | One sentence. Imperative mood. It ends with a period. It is at most 80 characters. |
| Body | What the code does and why, when the name does not say it. Rules, limits and edge cases. |
| `Args:` | Each parameter: meaning, allowed values, units, time zone, defaults that matter. Do not repeat the type that the annotation shows. |
| `Returns:` | What the value means. Say what an empty value or `None` means. Say the order of a list. |
| `Raises:` | One line for each exception: `ExcType: when it happens.` |
| `Side effects:` | Database writes, network calls, messages, cache changes, files. |
| `Security:` | Secrets, redaction, who may call the function. |
| `Note:` | A fact that surprises a reader. |
| `Example:` | A short example for a helper that is not obvious. |

## Rules for the text

1. **Say what the code does now.** Read the function, the code that it calls, its callers and its
   tests before you write.
2. **Check every fact.** Check units (seconds or minutes), time zones (IST is `Asia/Kolkata`),
   defaults, limits, what happens on failure, and what is saved to the database.
3. **Use short sentences.** One idea in each sentence. About 20 words or fewer.
4. **Use the active voice and the present tense.** "The function sends the report." Not "The
   report is sent."
5. **Use one word for one thing.** For example always "feed", "article", "prediction", "report",
   "task run" and "setting".
6. **Do not use idioms, marketing words, "simply" or "just".**
7. **Never write a secret in a docstring.** Do not write a token, a password, a real chat id or a
   URL that holds a token. Use a name like `<token>`.
8. **Write code in backticks.** Avoid a raw `<`, `>`, `{` or `}` outside backticks. The pages are
   MDX, and these characters are special. The generator escapes them, but plain text reads
   better.
9. **Use one line of at most 100 characters.** Ruff checks this.
10. **If you find a bug, do not hide it in the text.** Keep the docstring true to the current
    behavior and open an issue.

## Special code

| Code | What to write |
| --- | --- |
| Django view | The methods that it accepts, the form data, who may call it, the response or the redirect. |
| Model and service | The invariants, if it saves, the transaction behavior, the exceptions. |
| Celery task | The arguments, the result shape, the providers, the time limit, why it is safe to run again, and if a user may start it. |
| HTTP client and parser | The provider, the timeout, the expected content, what happens for bad data or a bad status. |
| Settings and security code | The order of values, the limits, what is secret, and what happens when the database fails. |
| API endpoint | The text of the docstring is the description in the OpenAPI file. Write for the user of the API. Name the required feature. |

## Check your work

```bash
cd docs
npm run reference:check        # the contract above
uv run ruff check .            # the D rules (Google style)
```

To see the backlog of one app:

```bash
python docs/scripts/generate_reference.py --no-write --list --source apps/ipos
```

## The baseline

Some older code does not meet the contract yet. The file `docs/scripts/docstring_baseline.txt`
lists these gaps, one for each line (`path::qualified name`). The check works like a ratchet:

- A gap that is **in** the baseline is accepted.
- A gap that is **not** in the baseline fails the check. New and changed code must be complete.
- A gap that is fixed but still **in** the baseline also fails the check. Remove its line.

So the baseline can only get shorter. Do not add a line to it. To make the file again after a
big change, run `python docs/scripts/generate_reference.py --no-write --write-baseline`, and read
the diff: it must only remove lines.

The coverage page (`reference/generated/python/coverage`) shows all gaps, with or without the
baseline.

## Why the check is a gate

A missing docstring is a defect of the same kind as a missing test. CI runs the check on every
pull request. A new definition without a good docstring fails the build.
