# SillyTavern

LLM chat UI with character cards, group chats, and image-gen integration.
Migrated from `ai-rp-stack` — now part of the home-server.

## Endpoint

- Local only: <http://127.0.0.1:8000>
- ST has its own auth layer; do not expose to LAN without hardening.

## Ops

```bash
./scripts/up.sh sillytavern      # start
./scripts/down.sh sillytavern    # stop
./scripts/logs.sh sillytavern    # tail logs
```

## Integration

- Network: `home-net` (external, shared with `home-forge`)
- Image gen wired to Forge at `http://home-forge:7860` (Auto1111 extension, container DNS)
- All character cards, chats, settings live in `./data/` (gitignored)
- Claude skills (`.claude/skills/st-*`): `/st-cook "<idea>"` is the front door (idea → card + persona + lorebooks + Chapter-1 Direction + sim gate; `--lang vi|en`, default vi, sets the campaign language end-to-end — PROMPT-PLAYBOOK 5.51; `--close` archives a finished scenario); `/st-setup`, `/st-persona`, `/st-arc-plan`, `/st-arc-save`, `/st-audit` remain usable on their own. Card writes go through the st-mcp character tools (see PROMPT-PLAYBOOK 5.46).

## Gotchas

- `data/` is owned by container UID (mapped via subuid) — use `podman unshare` for any host-side file ops (rm, mv, sed)
- After Forge restarts on a different IP, ST's connection still resolves via container DNS — no config change needed
- If migrating data from elsewhere: `podman unshare mv <src> ./data` to preserve ownership
