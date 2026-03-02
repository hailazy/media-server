# Media Server — Project Context

> Soul & identity: see ~/.claude/CLAUDE.md or ~/.gemini/GEMINI.md

## Project Values
- **Reliability over features** — A media server must be stable. Prefer battle-tested approaches over cutting-edge ones
- **Self-hosted first** — Privacy and control are priorities. Avoid solutions that depend on external services
- **Minimal impact** — Make the smallest changes necessary. Don't over-engineer
- **No dirty state** — Don't leave the environment broken. Verify changes work before completing a task
- **Reversibility** — Ensure significant changes can be undone if needed

### Boundaries
- Verify changes don't break existing media access before marking tasks complete
- Be cautious with data operations — media files are large and irreplaceable

## Memory Bank
Auto-loaded at session start (brief, context, tech). Full files in `.memory-bank/`:
- `brief.md` — Project goals and scope
- `product.md` — Product context and constraints
- `context.md` — Current focus and recent changes
- `architecture.md` — System architecture
- `tech.md` — Tech stack and tooling
- `tasks.md` — Task tracking

After major tasks or architectural changes, update relevant Memory Bank files.

## Security
**CRITICAL**: NEVER commit, push, or expose secrets, API keys, tokens, or credentials to version control.

- NEVER hardcode secrets in code — use environment variables and `.env` files
- NEVER commit files containing secrets — verify with `git diff --cached` before committing
- ALWAYS check `.gitignore` has `.env*`, `credentials.*`, `secrets.*`, `*.key`, `*.pem`
- ASK before committing sensitive-looking files (`config.json`, `.env*`, `credentials.*`)
- If secrets are accidentally committed: STOP, alert user to revoke, remove from history, add to `.gitignore`
