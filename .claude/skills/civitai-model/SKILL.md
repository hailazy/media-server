---
name: civitai-model
description: "Search, download, and mine prompts from Civitai for Forge"
argument-hint: "search <query> | top-loras [base] | top-checkpoints [base] | download <id> [--version <vid>] | prompts <id> [--top N]"
allowed-tools: Bash, AskUserQuestion, mcp__civitai__search_models, mcp__civitai__get_model, mcp__civitai__get_model_version, mcp__civitai__get_model_version_mini, mcp__civitai__get_top_loras, mcp__civitai__get_top_checkpoints, mcp__civitai__get_model_images, mcp__civitai__get_image_generation_data, mcp__civitai__get_download_url, mcp__civitai__get_download_info, mcp__civitai__get_tags, mcp__civitai__get_creators, mcp__civitai__get_enums, mcp__civitai__get_current_user
---

# Civitai Model — Search, Download, Mine Prompts for Forge

Project-scoped skill bridging Civitai API → local Forge stack. Three modes: discover models, download to correct Forge path, extract working prompts from top community images.

## Constants

```
FORGE_LORA_PATH    = /home/haint/Projects/home-server/forge/data/forge/models/Lora
FORGE_CKPT_PATH    = /home/haint/Projects/home-server/forge/data/forge/models/Stable-diffusion
FORGE_EMB_PATH     = /home/haint/Projects/home-server/forge/data/forge/embeddings
FORGE_VAE_PATH     = /home/haint/Projects/home-server/forge/data/forge/models/VAE
DEFAULT_BASE_MODEL = "NoobAI"  # active stack base. Valid: NoobAI, Illustrious, Pony, SDXL 1.0, Flux.1 D, etc. — call mcp__civitai__get_enums for full list
```

**Civitai → Forge type mapping:**

| Civitai `type` | Forge folder |
|----------------|-------------|
| `Checkpoint` | `Stable-diffusion/` |
| `LORA` | `Lora/` |
| `LoCon` | `Lora/` |
| `TextualInversion` | `embeddings/` |
| `VAE` | `VAE/` |

---

## Phase 0: Parse Mode

Look at first positional arg:

| Token | Mode |
|-------|------|
| `search` | Mode A — Search |
| `top-loras` | Mode A — Top LoRA shortcut |
| `top-checkpoints` | Mode A — Top Checkpoint shortcut |
| `download` | Mode B — Download |
| `prompts` | Mode C — Prompt mining |
| _(empty)_ | Show usage |

If unrecognized → display usage line from frontmatter and exit.

---

## Mode A: Search

```
/civitai-model search "mature female housewife"
/civitai-model top-loras [SDXL 1.0]
/civitai-model top-checkpoints [SDXL 1.0]
```

### Steps

1. **Dispatch tool call** based on subcommand:
   - `search <query>` → `mcp__civitai__search_models(query=<q>, baseModel="NoobAI", nsfw=true, limit=15)`
   - `top-loras [base]` → `mcp__civitai__get_top_loras(baseModel=<base or "NoobAI">, limit=15)`
   - `top-checkpoints [base]` → `mcp__civitai__get_top_checkpoints(baseModel=<base or "NoobAI">, limit=15)`

2. **Format result table**:
   ```
   ═══ Civitai Search: <query> ═══

    ID      | Name                          | Type       | DLs   | ★    | NSFW
    --------|-------------------------------|------------|-------|------|------
    123456  | MatureWife-XL-v2              | LORA       | 45.2K | 4.8  | Mature
    789012  | NoobAI-XL-Vpred-1.0           | Checkpoint | 120K  | 4.9  | X
    ...
   ```
   - Truncate Name at 30 chars, append `…`
   - Format DLs: `1234` → `1.2K`, `12345` → `12.3K`, `123456` → `123K`
   - NSFW levels: None / Soft / Mature / X

3. **Footer hint**:
   ```
   Next:
     /civitai-model download <ID>          → download to Forge
     /civitai-model prompts <ID>           → see top community prompts
   ```

---

## Mode B: Download

```
/civitai-model download <model-id>
/civitai-model download <model-id> --version <version-id>
```

### Steps

1. **Get model metadata**: `mcp__civitai__get_model(model_id=<id>)`
   - Extract: `name`, `type`, `modelVersions[]`
   - Pick version: latest by default, or matching `--version`

2. **Determine target path** (from constants table above). If `type` không match table → ask user where to save.

3. **Get download info**: `mcp__civitai__get_download_info(model_id=<id>, version_id=<vid>)`
   - Returns: filename, file size, hash, download URL with auth template

4. **Display preview**:
   ```
   ═══ Download Preview ═══
   Name:     MatureWife-XL-v2
   Type:     LORA
   Version:  v2 (uploaded 2025-12-15)
   File:     mature_wife_xl_v2.safetensors
   Size:     147 MB
   Target:   /home/haint/Projects/home-server/forge/data/forge/models/Lora/mature_wife_xl_v2.safetensors
   SHA256:   abc123...
   ```

5. **Confirm via AskUserQuestion**:
   - Q: "Proceed with download?"
   - Options: "Download now" / "Cancel"

6. **On confirm**, run inside `podman unshare` (REQUIRED — Forge model dirs owned by container subuid 525287, host user `haint` cannot write directly):
   ```bash
   set -a; source /home/haint/Projects/home-server/.env; set +a
   podman unshare bash -c "
     curl -L --fail --create-dirs \
       -H 'Authorization: Bearer \$CIVITAI_API_KEY' \
       '<download_url>' \
       -o '<target_path>/<filename>'
   "
   ```
   Inside `podman unshare`, host user maps to namespace root → writes appear as container UID 1000 on host (subuid 525287). Forge reads natively. **Plain `curl` from host user fails with exit 23 (write error)** — verified 2026-05-07.

7. **Verify**:
   - File exists + size matches metadata (within 1% tolerance for HTTP overhead)
   - If hash provided: `sha256sum <file>` matches Civitai-provided hash

8. **Post-download note**:
   - LORA / Embedding → Forge hot-reloads when used in prompt; no restart needed
   - Checkpoint → either restart Forge container (`./scripts/down.sh forge && ./scripts/up.sh forge`) OR swap via API:
     ```bash
     curl -X POST http://localhost:7860/sdapi/v1/options \
       -H "Content-Type: application/json" \
       -d '{"sd_model_checkpoint": "<filename without ext>"}'
     ```

---

## Mode C: Prompt Mining

```
/civitai-model prompts <model-id>
/civitai-model prompts <model-id> --top 10
```

### Steps

1. **Get example images**: `mcp__civitai__get_model_images(model_id=<id>, limit=N)` (N default 5)

2. **For each image**: `mcp__civitai__get_image_generation_data(image_id=<iid>)`
   - Extract: `prompt`, `negativePrompt`, `sampler`, `cfgScale`, `steps`, `Size`, `seed`, `Model`
   - Skip images without `meta` data (manual uploads, not generated)

3. **Display formatted**:
   ```
   ═══ Top Prompts — MatureWife-XL-v2 ═══

   ─── [1] Reactions: 234, Comments: 12 ───
   Positive:
     1girl, mature female, milf, plump, large breasts, indoors,
     kitchen, apron, looking at viewer, soft lighting, ...

   Negative:
     low quality, worst quality, bad anatomy, ...

   Sampler: Euler | CFG: 5 | Steps: 35 | Size: 832×1216 | Seed: 1234567
   Model: NoobAI XL v1.1

   ─── [2] Reactions: 198, Comments: 7 ───
   ...
   ```

4. **Footer**:
   ```
   To use a prompt:
     /st-gen-image-prompt --describe '<paste positive prompt above>'
   Or paste directly into ST 🎨 Freestyle button.
   ```

---

## Edge Cases

| Case | Handling |
|------|----------|
| `search` returns empty | Display "No results — try broader query or check spelling" |
| Model is paid/restricted | Civitai API returns 403 → display "This model requires unlocking via Civitai Buzz. Visit civitai.red/models/<id> in browser." |
| Type not in mapping table (e.g. Hypernetwork) | Ask user via AskUserQuestion to pick target dir from constants |
| `CIVITAI_API_KEY` empty/missing | Stop, instruct: "Edit /home/haint/Projects/home-server/.env, then restart Claude Code via ./scripts/claude.sh" |
| Forge container not running | Download still works — Forge picks up files on next start |
| File already exists | Ask: overwrite / skip / save as `<name>.v2.safetensors` |
| Disk space low | `df -h $(dirname <target_path>)` before download — warn if <5GB free |
| NSFW filter blocks model | Verify env has `CIVITAI_API_KEY` + retry; key required for full NSFW access |

---

## Related Skills

- `/st-gen-image-prompt` — generates booru-tag prompts from chat context. Use prompts mined here as `--describe` input
- `/st-setup` — onboards new ST characters, can pair with downloaded character LoRAs

## References

- Civitai API: https://developer.civitai.com
- MCP server: https://github.com/timoncool/civitai-mcp-ultimate
- Forge model paths: home-server `forge/data/forge/models/`
- Auth method: Bearer token in `CIVITAI_API_KEY` env (loaded by `scripts/claude.sh` from `.env`)
