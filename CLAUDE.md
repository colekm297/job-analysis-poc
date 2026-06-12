# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Streamlit proof-of-concept (`app.py`) that runs an AI-driven **job analysis interview**. An I/O-psychologist persona (powered by the Anthropic API) interviews a subject-matter expert about a role one question at a time, then synthesizes the transcript into a structured **KSAO** analysis (Knowledge, Skills, Abilities, Other characteristics) returned as JSON and rendered/downloadable in the UI.

## Commands

```bash
pip install -r requirements.txt      # install deps (streamlit, anthropic)
streamlit run app.py                 # run locally on http://localhost:8501
```

There is no test suite, linter, or build step — the entire app is `app.py`.

## Required configuration

The app will not run without two secrets:

- `ANTHROPIC_API_KEY` — read implicitly by `anthropic.Anthropic()` from the environment.
- `app_password` — read via `st.secrets["app_password"]` to gate access (see `check_password`). Set it in `.streamlit/secrets.toml` (gitignored) or Streamlit Cloud secrets. Without it the password check raises on startup.

## Architecture

Everything lives in `app.py` and revolves around Streamlit's `st.session_state` as the single source of truth across reruns. Streamlit re-executes `main()` top-to-bottom on every interaction, so all persistent state (messages, coverage, results, setup flags) is stored in session state and the function branches on flags (`setup_complete`, `initialized`, `interview_complete`) to decide which screen to render.

Three logical phases:

1. **Setup** — collect job title (required) and optional formal job description.
2. **Interview loop** — each user turn appends to `messages`, calls `update_coverage` (keyword heuristics), rebuilds the system prompt, and calls the LLM. The system prompt is regenerated every turn to inject live coverage/progress so the interviewer self-paces toward `TARGET_EXCHANGES`.
3. **Synthesis** — `generate_synthesis` sends the full transcript and parses the model's JSON into the KSAO display.

Key design details to preserve when editing:

- **Two distinct LLM calls** with different prompts: `call_llm` (conversational, `INTERVIEWER_SYSTEM_PROMPT`, `max_tokens=500`) and `generate_synthesis` (`SYNTHESIS_PROMPT`, `max_tokens=2000`, JSON-only). Module constants: `MODEL`, `TARGET_EXCHANGES`.
- **Coverage tracking is heuristic, not LLM-driven.** `update_coverage` flips booleans in the `COVERAGE_AREAS` dict by scanning the user's message for keyword lists. The formatted coverage string is fed back into the prompt as hidden "INTERNAL TRACKING" — the prompt explicitly forbids the model from echoing it.
- **Defensive output cleanup in `call_llm`** strips any leaked tracking markers (`COVERAGE`, `PROGRESS:`, `INTERNAL`, progress glyphs) and trims trailing incomplete sentences. Keep this if you change prompts, since the tracking text could otherwise surface to users.
- **JSON extraction in `generate_synthesis`** slices between the first `{` and last `}` before `json.loads`, tolerating prose/markdown around the JSON. Errors are returned as `{"error": ...}` dicts and surfaced in the UI rather than raised.
- **`COVERAGE_AREAS` is deep-copied** into session state (`{k: dict(v) for k, v in ...}`) so the module-level template is never mutated across sessions.

## Deployment

`.devcontainer/devcontainer.json` configures a Codespaces/dev-container setup that installs `requirements.txt`, force-installs `streamlit`, and auto-runs the app on port 8501. This is the intended hosting path alongside Streamlit Cloud.
