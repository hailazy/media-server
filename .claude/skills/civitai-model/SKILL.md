---
name: civitai-model
model: haiku
description: "Search, download, and mine prompts from Civitai for the local Forge stack (LoRA, checkpoint, VAE, embedding). USE on 'find a LoRA for X', 'download model <id>', 'tải model Civitai', 'what prompts does this model use'."
argument-hint: "search <query> | top-loras [base] | top-checkpoints [base] | download <id> [--version <vid>] | prompts <id> [--top N]"
allowed-tools: Bash, Read, Edit, AskUserQuestion, mcp__civitai__search_models, mcp__civitai__get_model, mcp__civitai__get_top_loras, mcp__civitai__get_top_checkpoints, mcp__civitai__get_model_images, mcp__civitai__get_image_generation_data, mcp__civitai__get_download_url, mcp__civitai__get_download_info, mcp__civitai__get_enums, mcp__civitai__check_permissions
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
| `DoRA` | `Lora/` |
| `TextualInversion` | `embeddings/` |
| `VAE` | `VAE/` |
| `Controlnet` | `ControlNet/` |
| `Upscaler` | `RealESRGAN/` (or `ESRGAN/` for legacy `.pth`) |

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
   - `search <query>` → `mcp__civitai__search_models(query=<q>, base_model="NoobAI", nsfw=true, limit=15)`
   - `top-loras [base]` → `mcp__civitai__get_top_loras(base_model=<base or "NoobAI">, nsfw=true, limit=15)`
   - `top-checkpoints [base]` → `mcp__civitai__get_top_checkpoints(base_model=<base or "NoobAI">, limit=15)`

   **Note:** civitai MCP tool params are snake_case (`base_model`, not `baseModel`). NoobAI base requires explicit `base_model="NoobAI"` — default of these tools is `"SDXL 1.0"`. `get_top_checkpoints` doesn't accept `nsfw` (always returns full set; filter on display side if needed).

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

2.5. **Check access gate**: `mcp__civitai__check_permissions(version_ids=[<vid>])`
   - Returns `{<vid>: true/false}` per version. If `false` → version is gated (early access / membership required) → STOP, inform user, suggest a different version từ `get_model` output. Skip step 3-7.
   - If `true` → proceed.

3. **Get download URL**: `mcp__civitai__get_download_url(version_id=<vid>)` — returns a token-bearing URL that needs no manual `Authorization` header, avoiding the header-quoting pitfall of hand-built curl auth. Cross-check filename/size/hash against `mcp__civitai__get_download_info(model_id=<id>, version_id=<vid>)`.

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

6. **On confirm**, run inside `podman unshare` (REQUIRED — parent Forge model dir is owned by subuid 525287, `haint` cannot write into it directly). Use the token-bearing URL from `get_download_url` as-is — it already carries auth, so no manual `Authorization` header (and no header-quoting to get wrong):
   ```bash
   podman unshare bash -c "
     curl -L --fail --create-dirs \
       '<download_url_from_get_download_url>' \
       -o '<target_path>/<filename>'
   "
   ```
   The `podman unshare` write lands owned by host user `haint` (644 perms) — the parent dir is what's subuid-owned, not the resulting file — and Forge (container UID 1000) reads it fine. **Plain `curl` from host user fails with exit 23 (write error)** because it can't write into that parent dir at all.

7. **Verify**:
   - File exists + size matches metadata (within 1% tolerance for HTTP overhead)
   - If hash provided: `sha256sum <file>` matches Civitai-provided hash
   - **Sanity-check the body isn't HTML**: `head -c 256 <file>` and confirm it doesn't start with `<!DOCTYPE` / `<html` — a gated or expired-token download can return a 200 OK login/redirect page instead of the model file, which `curl --fail` and the loose size tolerance won't catch on their own.

8. **Post-download note**:
   - LORA / Embedding → Forge hot-reloads when used in prompt; no restart needed
   - Checkpoint → swap is optional to do now — Forge picks up the new checkpoint on its next start regardless. If swapping live, gate it: run `./scripts/vram-guard.sh` first (soft warn 13GB, hard refuse 15GB on the 16GB card — a live swap while Jellyfin is transcoding can OOM, exit 137). Then either restart the container (`./scripts/down.sh forge && ./scripts/up.sh forge`) OR swap via API:
     ```bash
     curl -X POST http://localhost:7860/sdapi/v1/options \
       -H "Content-Type: application/json" \
       -d '{"sd_model_checkpoint": "<filename without ext>"}'
     ```

9. **Register LoRA in the catalog** (LORA / LoCon only — this is what drives `<lora:name:weight>` injection for `/st-gen-image-prompt` and the gen pipeline; a downloaded LoRA never added here is functionally invisible to them):
   - Pull trigger words + a suggested weight from the `get_model` response (step 1).
   - Read `forge/knowledge/lora-catalog.md`, follow its existing row format, and append a row for the new LoRA (name, trigger words, weight band, base model).
   - If the catalog's format is unclear or the skill shouldn't write autonomously, instead print a ready-to-paste catalog row and tell the user to add it (or run `/st-gen-image-prompt` to register it).

---

## Mode C: Prompt Mining

```
/civitai-model prompts <model-id>
/civitai-model prompts <model-id> --top 10
```

### Steps

1. **Get generation data in one call**: `mcp__civitai__get_image_generation_data(model_id=<id>, limit=N, sort="Most Reactions")` (N default 5) — this already returns only images that carry generation metadata, so there's no separate per-image loop and no manual-upload filtering to do.
   - Extract per result: `prompt`, `negativePrompt`, `sampler`, `cfgScale`, `steps`, `Size`, `seed`, `Model`
   - Fallback: if this returns nothing (e.g. model has no meta-tagged images), use `mcp__civitai__get_model_images(model_id=<id>, limit=N)` instead and note that per-image prompt data may be sparser.

2. **Display formatted**:
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

3. **Reconciliation note**: mined prompts often carry `<lora:...>` tags and sampler/size settings tuned for a different setup than the local stack.
   - For each `<lora:...>` tag in the mined prompt, check whether it exists locally (`forge/knowledge/lora-catalog.md` and `FORGE_LORA_PATH`). Flag any that don't, and offer `/civitai-model download <id>` for the missing ones — pasting the prompt as-is silently drops unknown LoRA tags.
   - The mined Sampler/CFG/Steps/Size are informational only — do not retune the local ST baseline (Euler/karras — NOT "Euler a" — steps 35, CFG 5, 832×1216, 4x-AnimeSharp @ 0.25 denoise) to match them.

4. **Footer**:
   ```
   To use a prompt:
     /st-gen-image-prompt --describe '<paste positive prompt above>'
   ```
   Paste the prompt into the ST message textarea, then click 🎨 Freestyle (the Quick Reply is `/sd {{input}}`, which reads the textarea — not the clipboard or the button itself).

---

## Edge Cases

| Case | Handling |
|------|----------|
| `search` returns empty | Display "No results — try broader query or check spelling" |
| Model is paid/restricted | Civitai API returns 403 → display "This model requires unlocking via Civitai Buzz. Visit https://civitai.com/models/<id> in browser." (try an alternate/mirror domain only if the canonical one is blocked) |
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
