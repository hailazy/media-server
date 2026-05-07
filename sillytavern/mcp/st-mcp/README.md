# st-mcp

MCP server wrapping SillyTavern's internal REST API (`localhost:8000/api/*`) for Claude Code.

## Tools

- `st_get_settings` — read current ST settings.json
- `st_save_settings` — write settings; ST hot-reloads (no restart)
- `st_list_characters` — list all character cards
- `st_get_character` — read character card data
- `st_get_recent_chat` — read most recent chat for a character
- `st_get_worldinfo` — read a World Info lorebook
- `st_save_worldinfo` — write a World Info lorebook

## Auth

None required when ST runs in single-user mode (the home-server default — see `compose.yml`
with `SILLYTAVERN_SECURITYOVERRIDE=true`). `setUserDataMiddleware` auto-sets the request
user, so `requireLoginMiddleware` passes without a session cookie.

## Install

```bash
pip install --user -e .
```

Binary lands at `~/.local/bin/st-mcp`.

## Config

```json
{
  "mcpServers": {
    "st": {
      "command": "/home/haint/.local/bin/st-mcp",
      "env": { "ST_URL": "http://localhost:8000" }
    }
  }
}
```

`ST_URL` defaults to `http://localhost:8000` if env var is not set.
