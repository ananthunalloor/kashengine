# AI skills

Agent skills used for work on KashEngine. Each folder holds a `SKILL.md` with YAML frontmatter
(`name`, `description`) and, for some skills, supporting reference files.

`.github/skills` (GitHub Copilot) and `.claude/skills` (Claude) are relative symlinks to this
folder, so edit skills only here. `tests/test_skills.py` checks the format rules: `name` matches
the folder (1-64 lowercase letters, digits, and hyphens), `description` is 1-1024 characters,
`SKILL.md` is under 500 lines, and resource files are at most one level deep.

## How to use the skills

No setup is needed. Open the repository and the agent finds the skills through the links.

### Automatic loading

The agent reads the `name` and `description` of every skill. When your request matches a
description, the agent loads that `SKILL.md` and follows it. Describe the task in plain words:

```text
Add a "sector" column to the companies table.
```

This request loads `kashengine-private-api-react-page` and `kashengine-frontend-ui`.

### Call a skill by name

| Tool | How |
| --- | --- |
| GitHub Copilot Chat (VS Code) | Type `/` in chat and pick the skill, for example `/kashengine-docstrings fix apps/ipos/scoring.py`. Skills need agent mode. |
| GitHub Copilot CLI | Run `/skills` to list the skills. Use `/kashengine-quality-checks` or name the skill in the prompt. |
| Copilot coding agent (github.com) | Name the skill in the issue or task, for example "Follow the kashengine-public-api-v1 skill". |
| Claude Code | Type `/` and pick the skill, or name it in the prompt: "Use the kashengine-backend-change skill to add a Celery task". |

To check what loaded, ask the agent "Which skills did you use?". In VS Code, the
`troubleshoot` skill reads the debug logs.

### Add or change a skill

1. Create `skills/<skill-name>/SKILL.md`. The folder name and `name` must match.
2. Start the file with frontmatter:

   ```yaml
   ---
   name: skill-name
   description: What the skill does. Use when <trigger words and tasks>.
   ---
   ```

3. Write numbered steps, the commands to run, and the files to change. Put long reference text
   in a sub-folder such as `references/` and link to it with `./references/<file>.md`.
4. Add the skill to a table in this file.
5. Run `uv run pytest tests/test_skills.py`.

## Project skills

| Skill | Use it for |
| --- | --- |
| [kashengine-backend-change](./kashengine-backend-change/SKILL.md) | Django models, services, Celery tasks, settings, migrations, Ops jobs |
| [kashengine-private-api-react-page](./kashengine-private-api-react-page/SKILL.md) | `/api/app` endpoints, OpenAPI export, generated client, React routes and queries |
| [kashengine-frontend-ui](./kashengine-frontend-ui/SKILL.md) | Mantine/TanStack UI, `DataTable`, `MetricValue`, icons, CSP-safe styling |
| [kashengine-public-api-v1](./kashengine-public-api-v1/SKILL.md) | Additive changes to the public `/api/v1` contract |
| [kashengine-docstrings](./kashengine-docstrings/SKILL.md) | Docstring contract gate and baseline ratchet |
| [kashengine-quality-checks](./kashengine-quality-checks/SKILL.md) | Running tests and quality gates, debugging failures |

## General skills

Copied from the VS Code Copilot, Pylance, and TypeScript extensions.

| Skill | Use it for |
| --- | --- |
| [python-fact-grounded-coding](./python-fact-grounded-coding/SKILL.md) | Ground Python changes in Pylance facts, runtime values, and tests |
| [python-add-type-annotations](./python-add-type-annotations/SKILL.md) | Add inline type annotations in bulk |
| [python-type-inference](./python-type-inference/SKILL.md) | Determine the correct type of a symbol |
| [python-write-stubs](./python-write-stubs/SKILL.md) | Write `.pyi` stubs for third-party packages |
| [pylance-refactoring](./pylance-refactoring/SKILL.md) | Automated Python refactorings (unused imports, fix-all) |
| [pylance-python-profiling](./pylance-python-profiling/SKILL.md) | CPU, call, and memory profiling |
| [pylance-docs](./pylance-docs/SKILL.md) | Pylance settings and diagnostics |
| [add-python-version-support](./add-python-version-support/SKILL.md) | Support a newer Python release |
| [drop-python-version-support](./drop-python-version-support/SKILL.md) | Raise the minimum Python version |
| [typescript-setup](./typescript-setup/SKILL.md) | Set up a TypeScript project |
| [typescript-update](./typescript-update/SKILL.md) | Upgrade TypeScript versions |
| [agent-customization](./agent-customization/SKILL.md) | Create or fix instructions, prompts, agents, and skills |
| [create-canvas](./create-canvas/SKILL.md) | Create a Copilot extension canvas |
| [troubleshoot](./troubleshoot/SKILL.md) | Investigate agent behavior from debug logs |
