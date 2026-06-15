# Forge — Shared Image Generation Service

Stable Diffusion WebUI Forge as a shared service for ai-rp-stack workflow + Learning_English flashcard images + future LAN clients.

## Endpoints
- WebUI: http://localhost:7860 (localhost-only)
- API: http://localhost:7860/sdapi/v1/ (A1111-compatible REST)
- Container clients (SillyTavern on `home-net`): `http://home-forge:7860` via Podman DNS
- **NOT exposed to LAN** — Forge has no auth/HTTPS. If LAN access needed, add reverse proxy with auth in front (Caddy/Tailscale Funnel).

## Models (data/forge/models/Stable-diffusion/)
| Filename | Profile | Use case |
|----------|---------|----------|
| `NoobAI-XL-v1.1.safetensors` | NSFW-capable anime (Illustrious base) | Shared default — ai-rp-stack roleplay + Learning_English flashcards |
| `animagine-xl-4.0-opt.safetensors` | Clean SFW anime (Animagine v4 base) | Chimera project art — client-selectable |

Two checkpoints are mounted. `NoobAI-XL-v1.1` is the shared default — since 2026-05-17 both ai-rp-stack and Learning_English use it (NoobAI parses the pipelines' prompts better). Clients pick a checkpoint client-side via `POST /sdapi/v1/options` with `sd_model_checkpoint` before generating; switching costs ~3s.

## Conventions
- Default for all clients → `NoobAI-XL-v1.1.safetensors`
- `animagine-xl-4.0-opt` — Chimera project art; switch to it client-side when needed
- Don't run gen requests from both clients simultaneously — Forge serializes requests, and a checkpoint switch costs ~3s

## Operations
```bash
./scripts/up.sh forge          # start
./scripts/down.sh forge        # stop
./scripts/logs.sh forge -f     # follow logs
```

## Gotchas (from ai-rp-stack experience)
- `forge_args.conf` controls launch flags (NOT `WEBUI_FLAGS` env var alone)
- ai-dock image 19+ months old — vpred models don't work (Zero Terminal SNR option ignored). Stick with epsilon-prediction checkpoints.
- ADetailer extension required if clients send `alwayson_scripts.ADetailer` — install via WebUI if needed
- Cold start ~3 minutes (xformers download), healthcheck waits 180s
- Bind mount ownership: chown via `podman unshare chown -R 1000:1000 data/forge/` if permission errors

## VRAM
~12GB peak per generation (RTX 4070 Ti Super 16GB). Run `vram-guard.sh` before starting if Jellyfin transcoding active.
