"""st-mcp MCP server: tools wrapping SillyTavern's REST API.

Local stdio MCP. Auth bypassed (single-user mode + SECURITYOVERRIDE=true on the
home-server compose). Hot-edit ST data without container restart.

Settings + character payloads can be 80–150KB; raw responses blow past Claude's MCP
output limit. Tools return SUMMARY shapes by default and offer `path` parameters for
surgical reads/writes.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import st_post, STError

mcp = FastMCP(
    "st",
    instructions=(
        "SillyTavern data API — manage characters, chats, settings, and lorebooks "
        "without restarting the ST container. ST hot-reloads on st_save_settings "
        "and st_save_worldinfo. Create/patch/delete characters with st_create_character, "
        "st_merge_character, st_delete_character — no PNG tEXt-patch, no container stop. "
        "Pair with /st-setup, /st-persona, /st-audit, "
        "/st-arc-save, /st-arc-plan, /st-gen-image-prompt skills. Use path-based getters/setters "
        "to avoid 80KB+ full-tree dumps."
    ),
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_path(path: str) -> list[str]:
    """Split a dotted path into segments, with bracket-escape for literal keys.

    Examples:
      "a.b.c"                              → ["a", "b", "c"]
      'power_user.personas.["X.png"]'      → ["power_user", "personas", "X.png"]
      'power_user.personas["X.png"]'       → ["power_user", "personas", "X.png"]
      '["weird.key"].sub'                  → ["weird.key", "sub"]

    Bracket form `["..."]` keeps a literal segment that may contain dots. The
    leading/trailing `.` around a bracket group is optional. Backwards compatible
    with all dotted paths that don't use `["`.
    """
    segments: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(path)
    while i < n:
        c = path[i]
        if c == "[" and i + 1 < n and path[i + 1] == '"':
            if buf:
                segments.append("".join(buf))
                buf = []
            end = path.find('"]', i + 2)
            if end < 0:
                raise ValueError(f"unterminated bracket-quoted segment in path '{path}' at {i}")
            segments.append(path[i + 2 : end])
            i = end + 2
            if i < n and path[i] == ".":
                i += 1
            continue
        if c == ".":
            if buf:
                segments.append("".join(buf))
                buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    if buf:
        segments.append("".join(buf))
    return segments


def _get_path(d: Any, path: str) -> Any:
    """Walk a (possibly bracket-escaped) dotted path. '' returns the whole thing."""
    if not path:
        return d
    cur = d
    for seg in _parse_path(path):
        if isinstance(cur, list):
            cur = cur[int(seg)]
        elif isinstance(cur, dict):
            cur = cur[seg]
        else:
            raise KeyError(f"path '{path}' bottoms out at non-container at '{seg}'")
    return cur


def _set_path(d: Any, path: str, value: Any) -> None:
    """Set value at dotted path (bracket-escape supported); raises on bad navigation."""
    if not path:
        raise ValueError("empty path; refusing to replace the entire tree")
    parts = _parse_path(path)
    cur = d
    for seg in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(seg)]
        elif isinstance(cur, dict):
            if seg not in cur:
                cur[seg] = {}
            cur = cur[seg]
        else:
            raise KeyError(f"path '{path}' bottoms out at non-container at '{seg}'")
    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value


async def _fetch_inner_settings() -> dict:
    """Get the unwrapped settings dict (the contents of settings.json, no wrapper)."""
    resp = await st_post("/api/settings/get")
    raw = resp.get("settings") if isinstance(resp, dict) else None
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    raise STError(f"unexpected /api/settings/get shape: {type(resp).__name__}")


async def _fetch_merged_settings() -> dict:
    """Get a merged read-only view: wrapper top-level fields + inner settings tree.

    Wrapper exposes world_names, openai_settings, novelai_settings, etc. — not in
    settings.json proper but lives alongside in the API response. Merging gives a
    flat path namespace for reads. WRITES still operate on inner-only via
    _fetch_inner_settings.
    """
    resp = await st_post("/api/settings/get")
    if not isinstance(resp, dict):
        raise STError(f"unexpected /api/settings/get shape: {type(resp).__name__}")
    raw = resp.get("settings")
    inner = json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
    # Wrapper keys (not in settings.json): world_names, koboldai_settings, etc.
    extras = {k: v for k, v in resp.items() if k != "settings"}
    # No key collisions expected — settings.json has firstRun/extension_settings/power_user/...
    # while wrapper has world_names/koboldai_settings/openai_settings/...
    return {**inner, **extras}


# ── Settings ────────────────────────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
async def st_get_settings(path: str = "") -> str:
    """Read ST settings — full tree or a subtree at a dotted path.

    Reads from a merged view: settings.json fields + wrapper extras (world_names,
    koboldai_settings, openai_settings, novelai_settings, etc.) at one flat namespace.

    Examples:
      path=""                                        → full merged tree (~85KB, may exceed token cap)
      path="extension_settings.sd"                   → SD extension subtree (~5KB)
      path="extension_settings.sd.character_prompts" → just char_prompts dict
      path="power_user.persona_descriptions"         → all persona descriptions
      path="user_avatar"                             → currently selected persona avatar
      path="world_names"                             → list of available lorebooks (wrapper field)

    Use the most specific path you need; full reads will likely exceed token cap.

    Pair with: st_save_settings_path (surgical write), st_save_settings (full write).
    """
    try:
        s = await _fetch_merged_settings()
        sub = _get_path(s, path)
        return json.dumps(sub, ensure_ascii=False, indent=2)
    except (STError, KeyError, ValueError) as e:
        raise RuntimeError(str(e))


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
async def st_save_settings_path(path: str, value: Any) -> str:
    """Surgically update one path in ST settings — no full-tree round-trip needed.

    Server fetches the current settings, applies value at path, saves back. ST
    hot-reloads (no container restart, no saveSettingsDebounced race).

    Examples:
      path="extension_settings.sd.character_prompts.Parasite", value="<booru tags>"
      path="extension_settings.sd.sampler", value="Euler"
      path="user_avatar", value="MyPersona (Persona).png"

    Empty path is rejected — use st_save_settings for whole-tree replacement.

    Pair with: st_get_settings (path-based read).
    """
    try:
        s = await _fetch_inner_settings()
        _set_path(s, path, value)
        # ST's /api/settings/save writes JSON.stringify(request.body) directly to disk.
        # Body must be the bare settings dict, NOT wrapped in {"settings": ...}.
        await st_post("/api/settings/save", s)
        return f"OK: set settings.{path}"
    except (STError, KeyError, ValueError) as e:
        raise RuntimeError(str(e))


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
async def st_save_settings(settings: str) -> str:
    """Overwrite ST settings.json with the full tree as a JSON string.

    For surgical updates, prefer st_save_settings_path — it avoids round-tripping
    80KB+ through Claude's context.

    ST hot-reloads — no container restart. This routes through ST's save handler so
    direct-file race conditions are impossible.

    Pair with: st_get_settings, st_save_settings_path.
    """
    try:
        # ST's /api/settings/save writes request.body to disk verbatim. Parse the JSON
        # string the caller supplied so the dict body matches settings.json shape.
        body = json.loads(settings)
        result = await st_post("/api/settings/save", body)
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
    except (STError, ValueError) as e:
        raise RuntimeError(str(e))


# ── Characters ──────────────────────────────────────────────────────────────

_LIST_FIELDS = (
    "name", "avatar", "fav", "tags",
    "create_date", "date_added", "date_last_chat",
    "chat_size", "data_size", "spec", "spec_version",
)

_CHAR_HEAVY_FIELDS = ("json_data",)  # mirror of `data`, ~44KB redundant


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
async def st_list_characters() -> str:
    """List every character card (summary only — name, avatar, tags, sizes, dates).

    Strips heavy fields. ST's /api/characters/all returns full card data per entry
    (50KB+ each). For a specific character's full data, use st_get_character.

    Pair with: st_get_character.
    """
    try:
        result = await st_post("/api/characters/all")
        if isinstance(result, list):
            slim = [
                {k: c.get(k) for k in _LIST_FIELDS if k in c}
                for c in result
            ]
            return json.dumps(slim, ensure_ascii=False, indent=2)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except STError as e:
        raise RuntimeError(str(e))


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
async def st_get_character(name: str) -> str:
    """Read a single character card's data (description, personality, scenario, etc.).

    Replaces legacy PNG tEXt binary parsing. Strips `json_data` (a 40KB+ duplicate of
    the parsed `data` field). Accepts bare name ("Parasite") or filename ("Parasite.png").

    Pair with: st_list_characters.
    """
    avatar = name if name.endswith(".png") else f"{name}.png"
    try:
        result = await st_post("/api/characters/get", {"avatar_url": avatar})
        if isinstance(result, dict):
            slim = {k: v for k, v in result.items() if k not in _CHAR_HEAVY_FIELDS}
            return json.dumps(slim, ensure_ascii=False, indent=2)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except STError as e:
        raise RuntimeError(str(e))


@mcp.tool(annotations={"openWorldHint": True})
async def st_create_character(name: str, fields: dict, file_name: str = "") -> str:
    """Create a new character card from flat V2 fields.

    Leave `world` unset — this tool forces it to "" always. A non-empty `world` makes ST
    embed a dead `character_book` copy of the lorebook inside the card, which then drifts
    from the live lorebook file since ST reads World Info from the linked lorebook, not
    the embedded copy. Link a lorebook AFTER creation instead:
      st_merge_character(avatar, {"data": {"extensions": {"world": "<LorebookName>"}}})

    No file upload — ST assigns its default avatar image and creates chats/<name>/ for
    the new character on disk. `fields` accepts any flat card field ST's create endpoint
    takes: description, personality, scenario, first_mes, mes_example, creator_notes,
    system_prompt, post_history_instructions, creator, character_version, talkativeness,
    fav, tags (list or comma string), alternate_greetings (list), depth_prompt_prompt,
    depth_prompt_depth, depth_prompt_role, extensions (dict — auto-serialized to a JSON
    string here; ST JSON.parses it and deep-merges into data.extensions).

    Returns the avatar filename ST assigned (e.g. "Name.png") — pass it straight into
    st_merge_character / st_delete_character / st_get_character.

    Pair with: st_merge_character (fill in the rest, link a lorebook), st_get_character.
    """
    body = {**fields, "ch_name": name, "file_name": file_name or name, "world": ""}
    if isinstance(body.get("extensions"), dict):
        body["extensions"] = json.dumps(body["extensions"], ensure_ascii=False)
    try:
        result = await st_post("/api/characters/create", body)
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except STError as e:
        raise RuntimeError(str(e))


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
async def st_merge_character(avatar: str, patch: dict) -> str:
    """Patch an existing character card in place — replaces the PNG tEXt-patch procedure.

    No container stop needed; ST rewrites the PNG through writeCharacterData and updates
    its own memory/disk caches on the spot. deepMerge semantics apply: nested objects
    merge key by key, but ARRAYS REPLACE WHOLESALE (e.g. patching `tags` with one entry
    wipes the rest of the list).

    ST does NOT mirror V1↔V2 fields for you — the caller must send both sides to keep
    them in sync, e.g.:
      {"description": "...", "data": {"description": "..."}}
    for description, personality, scenario, first_mes, mes_example (and any other V1/V2
    pair).

    Sentinel value "__@@UNSET@@__" as a field's value deletes that key instead of
    setting it.

    ST validates the merged card with TavernCardValidator before writing; an invalid
    shape returns 400 with a {message, error} body.

    Returns "ok" on success, or the ST error message on failure (never raises for a
    normal 4xx — check the returned string).

    Pair with: st_get_character (read before merge, to know what's already there),
    st_create_character.
    """
    av = avatar if avatar.endswith(".png") else f"{avatar}.png"
    try:
        result = await st_post("/api/characters/merge-attributes", {"avatar": av, **patch})
        if isinstance(result, str):
            return "ok" if not result.strip() else result
        return json.dumps(result, ensure_ascii=False)
    except STError as e:
        return str(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
async def st_delete_character(avatar: str, delete_chats: bool = False) -> str:
    """Delete a character card. IRREVERSIBLE — back up first (/st-cook --close does this).

    Removes the PNG card from disk and invalidates ST's thumbnail cache for it. Pass
    delete_chats=True to also remove chats/<name>/ (all chat history for the character);
    otherwise the chat files are orphaned but left on disk.

    Accepts bare name or avatar filename.

    Pair with: st_get_character (confirm identity before deleting), st_create_character.
    """
    av = avatar if avatar.endswith(".png") else f"{avatar}.png"
    try:
        result = await st_post("/api/characters/delete", {"avatar_url": av, "delete_chats": delete_chats})
        if isinstance(result, str):
            return "ok" if not result.strip() else result
        return json.dumps(result, ensure_ascii=False)
    except STError as e:
        raise RuntimeError(str(e))


# ── Chats ───────────────────────────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
async def st_get_recent_chat(char_name: str) -> str:
    """List recent chat sessions for a character (metadata only — file_name, size, last_mes).

    Returns chat summaries, NOT full message arrays. To read full messages, use the
    chat .jsonl file directly at sillytavern/data/default-user/chats/<CharName>/<file>.jsonl
    (a future st_get_chat tool will replace that direct read).

    Accepts bare name or avatar filename.
    """
    avatar = char_name if char_name.endswith(".png") else f"{char_name}.png"
    try:
        result = await st_post("/api/chats/recent", {"avatar_url": avatar})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except STError as e:
        raise RuntimeError(str(e))


# ── World Info (Lorebooks) ──────────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
async def st_get_worldinfo(name: str) -> str:
    """Read a World Info lorebook by name (without `.json` extension).

    Returns the entries dict + metadata. Use before st_save_worldinfo to merge changes
    rather than overwrite blindly.

    Pair with: st_save_worldinfo.
    """
    try:
        result = await st_post("/api/worldinfo/get", {"name": name})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except STError as e:
        raise RuntimeError(str(e))


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
async def st_save_worldinfo(name: str, data: dict) -> str:
    """Overwrite a World Info lorebook. Pass the full data dict (entries + metadata).

    Replaces the entire lorebook file — no diff merging. Always st_get_worldinfo first
    if you intend to add to existing entries.

    Pair with: st_get_worldinfo.
    """
    try:
        result = await st_post("/api/worldinfo/edit", {"name": name, "data": data})
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
    except STError as e:
        raise RuntimeError(str(e))


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
