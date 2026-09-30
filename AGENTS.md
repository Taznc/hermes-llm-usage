# AGENTS.md — hermes-llm-usage

A Hermes Desktop plugin that shows account-level plan windows and balances for
Claude Code, Grok, Codex, Nous Research and Venice. It has a dockable panel, a
status-bar chip and ⌘K commands. Provider table, install steps, controls and
config are in [README.md](README.md). Workflow and the two hard constraints are in
[CONTRIBUTING.md](CONTRIBUTING.md). This file summarises them for agents.

## Layout

```text
desktop-plugins/llm-usage/plugin.js   Desktop UI: uncompiled ESM, no build step, no JSX
plugins/llm-usage/
  plugin.yaml                         plugin metadata (version shown to Hermes)
  __init__.py                         register() is a no-op; no agent tools or hooks
  dashboard/manifest.json             dashboard plugin manifest → plugin_api.py
  dashboard/plugin_api.py             FastAPI router: /api/plugins/llm-usage/{usage,health}
tests/                                stdlib unittest (fastapi is stubbed if absent)
.github/scripts/check-imports.mjs     replicates the Hermes loader's import regex
.github/workflows/check.yml           CI: the five checks below
install.sh                            copies both halves into $HERMES_HOME, enables the plugin
```

## Setup

No dependency install is needed. The requirements are Node ≥ 22 (so
`node --check` parses the plugin as ESM), Python 3 (stdlib only for tests) and
`shellcheck`. The tests stub `fastapi` when it isn't installed.

## Verified commands (the CI gate; run all before a PR)

| Command | Result on base |
| --- | --- |
| `node --check desktop-plugins/llm-usage/plugin.js` | pass |
| `bash -n install.sh` | pass |
| `shellcheck install.sh` | pass |
| `node .github/scripts/check-imports.mjs` | pass: "3 specifiers, all allowed" |
| `python3 -m unittest discover -s tests -v` | 31 tests, OK (<1 s) |

A single test file: `python3 -m unittest tests.test_cli_usage_scrape -v`.
There is no JS test runner, bundler, formatter or linter beyond these.

## Running locally

`./install.sh` (or `HERMES_HOME=/path/to/profile ./install.sh`) **overwrites the
installed copy in that live Hermes profile**: it `rm -rf`s both install
directories, then runs `hermes plugins enable llm-usage`. Only run it when asked
to, and against the intended profile. After installing:

- UI changes (`plugin.js`): Desktop ⌘K → Reload desktop plugins.
- Backend changes (`plugin_api.py`): the dashboard / `hermes serve` process must be
  restarted, because Reload does not remount Python. Leave that restart to the
  owner rather than restarting services yourself.
- Check the backend with `GET /api/plugins/llm-usage/health`, and with
  `GET /api/plugins/llm-usage/usage?force=true`, which bypasses the cache and can
  take about 15 s.

Snapshots are cached for about 5 minutes (`HERMES_LLM_USAGE_TTL_SEC`, minimum 30)
in memory and in `$HERMES_HOME/cache/llm-usage.json`. When the cache expires the
plugin serves the last good snapshot while it refreshes in the background.

## Hard constraints (CI enforces some of them)

- **Never write `from` followed by a quoted token anywhere in `plugin.js`, even in a
  comment.** The Hermes loader regex-scans raw source for imports.
  `check-imports.mjs` runs the same regex.
- Desktop imports are limited to `@hermes/plugin-sdk`, `react` and
  `react/jsx-runtime`. Use `jsx()`/`jsxs()` calls, not JSX syntax.
- Styling uses inline styles and live theme variables (`var(--ui-*)`,
  `var(--dt-*)`). Hex colours are forbidden, and
  `tests/test_desktop_plugin_compat.py` asserts there are none. Tailwind does not
  scan runtime plugin dirs. `--ui-warning` and `--ui-danger` don't exist; for
  attention states, mix accent toward `--dt-destructive`.
- Scope: account-level plan windows and balances only. Don't treat API-key rate
  caps as "balance", don't scrape browser cookies or dashboards, and don't invent
  undocumented billing routes. PRs doing any of these are declined.

## Backend conventions

- Claude Code and Grok are read by driving their CLIs' `/usage` screen inside a
  throwaway `tmux` session. Workdir is `HERMES_LLM_USAGE_WORKDIR`, default
  `$HOME`. Scrapers must tolerate first-run and trust dialogs and modal redesigns,
  and `tests/test_cli_usage_scrape.py` holds fixtures for them. Codex uses its
  app-server, Nous the Portal account API, and Venice the Admin billing API
  (the key is read from `$HERMES_HOME/.env`).
- Every quota window carries `used_pct`, `reset_label` and `resets_at` (epoch
  seconds). Keep that shape stable, because the UI depends on it.
- Collection is slow (tmux + CLIs), so it never runs inline on a request. Keep it
  behind the cache and lock in `plugin_api.py`.

## Repo and release notes

- `origin` is the `Taznc` fork and `upstream` is `kfa-ai/hermes-llm-usage`,
  whose `main` is protected. Land changes through PRs. The README badges and
  clone URL point at upstream.
- Bump `version` in `plugins/llm-usage/plugin.yaml` for user-visible releases.
  `dashboard/manifest.json` has its own version, 0.2.0, which is **not** kept in
  sync with it.
- Commit style is Conventional Commits with a scope, e.g. `fix(usage): …`,
  `feat(usage): …`, `docs: …`.

## Gotchas

- Changes under `plugins/llm-usage/dashboard/` appear to do nothing until the
  backend restarts. That is expected, not a bug.
- `install.sh` strips `__pycache__` and `*.pyc` from the installed copy. Don't
  depend on bytecode in the repo tree.
- If Desktop shows "0 installed" against a remote backend, that is a known
  Hermes Desktop issue (see README → Troubleshooting), not this plugin.
