# Research: tech stack and AI-assisted workflow

*Compiled 2026-10-17. Some items come from secondary sources and are marked [secondary].*

## Stack (why each piece is here)

| Need | Choice | Why |
|---|---|---|
| Install / env | **uv** + `uv.lock` + `.python-version` | One binary installs Python *and* the dependencies, so the recipient never installs Python. Lockfile works across OSes. `uv run` auto-syncs. |
| UI | **Streamlit** | Least code for "inputs → simulate → chart → download". `st.data_editor` handles assumption tables. Free Community Cloud is a zero-install option. |
| Data | **pandas** + **numpy** | Tables are small; Streamlit, Plotly and Excel all take pandas directly. Use vectorized numpy for Monte Carlo. |
| Cache | Parquet files, DuckDB if needed | Simplest local store for API pulls. |
| Validation / config | **pydantic** + **pydantic-settings** | Typed scenario inputs; `.env` read natively. |
| HTTP | **httpx** | Standard client; wrap with `st.cache_data(ttl=...)`. |
| Charts | **Plotly** | Interactive; fan charts for Monte Carlo bands. |
| Excel | **xlsxwriter** | Formatted export via `BytesIO` → `st.download_button`. |
| Quality | **ruff**, **pytest**, **pyright** | Fast lint/format, tests, types. CI on Linux/Win/Mac. |

Rejected:
- Dash, Panel: more boilerplate.
- Reflex: needs a JS toolchain.
- Poetry and pip+venv: both need Python already installed.
- Docker as the primary path: Docker Desktop is too heavy for a non-technical user.

**Launchers:**
- Each one: `cd` to the script's directory → install uv if it's missing → `uv run --locked streamlit run app.py`.
- Mac `.command` needs the executable bit committed (`git update-index --chmod=+x`).
- `.streamlit/config.toml` sets `gatherUsageStats=false` to avoid Streamlit's first-run email prompt.

**Community Cloud caveat:** support for `uv.lock` is unverified. Fallback:
`uv export --format requirements-txt > requirements.txt`.

## Workflow sources

**Boris Cherny (creator of Claude Code), Jan 2026 thread** —
<https://x.com/bcherny/status/2007179847949500714>:
- One team-shared `CLAUDE.md` in git. Whenever Claude gets something wrong, add a rule. Keep it around 100 lines and prune it. [secondary]
- Plan mode first; iterate on the plan, then let Claude implement.
- Slash commands / skills for repeated inner-loop work, checked into `.claude/`.
- Subagents for simplifying code and verifying the app.
- A PostToolUse hook auto-formats code.
- Pre-allow safe commands in `.claude/settings.json` rather than skipping permissions.
- **Verification is the most important thing.** Give Claude a feedback loop. He estimates it improves quality 2–3×.

**Anthropic docs** — <https://code.claude.com/docs/en/best-practices>,
<https://code.claude.com/docs/en/skills>:
- Workflow: explore → plan → implement → commit.
- CLAUDE.md:
  - Keep it under 200 lines. Test each line by asking "would removing this cause mistakes?"
  - Include commands, gotchas and conventions; leave out what can be learned by reading the code.
- Skills:
  - `.claude/skills/<name>/SKILL.md` with YAML frontmatter. `description` is the key field.
  - Use `disable-model-invocation: true` for side-effecting workflows.
  - Keep the body under 500 lines.
- Hooks are deterministic; CLAUDE.md is advisory.

**Karpathy** — nanochat, autoresearch:
- Minimal, flat, readable code. No config monsters or factories.
- autoresearch's `program.md`: a frozen harness/eval, a separate agent-editable surface, and one scalar metric.
- Jan 2026 complaints about agents: they over-abstract, bloat code, edit unrelated code and make silent assumptions. [secondary]
- Community four-rule distillation (not by Karpathy, <https://github.com/multica-ai/andrej-karpathy-skills>):
  1. Think before coding.
  2. Simplicity first.
  3. Surgical changes.
  4. Goal-driven execution (step → verify).

**Source-of-truth docs:**
- matklad ARCHITECTURE.md: a short code map plus invariants, with names rather than links.
- Anthropic's long-running-agent harness:
  - A progress log plus git history.
  - Start every session by running the app end to end.
  - One feature at a time, committing after each.
