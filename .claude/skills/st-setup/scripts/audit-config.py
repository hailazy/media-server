#!/usr/bin/env python3
"""
Audit the SillyTavern config layers that silently fight each other.

Read-only. Safe to run while ST is up.

Four things govern how a character behaves and looks, and each can quietly
override the one below it. Editing only the card is the classic mistake:

    preset prompts   (OpenAI Settings/<preset>.json — 'main', 'jailbreak')
      └─ card fields (system_prompt / post_history_instructions override the two
                      above, but ONLY when prefer_character_prompt /
                      prefer_character_jailbreak are on)
      └─ linked lorebook (extensions.world → worlds/<name>.json; `constant:true`
                          entries inject EVERY turn, at their own depth)
      └─ SD char prompts (character_prompts / character_negative_prompts —
                          appended to every image gen for that character)

Usage:
    audit-config.py                 # everything
    audit-config.py --char Parasite # scope to one character
    audit-config.py --json          # machine-readable
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import sys
from pathlib import Path

ST_DATA = Path("/home/haint/Projects/home-server/sillytavern/data/default-user")
BASELINES = "/home/haint/Projects/home-server/.claude/skills/st-gen-image-prompt/data/identity-baselines"
CHATS = ST_DATA / "chats"

# Tags that describe a SHOT, not a character. In character_prompts they force
# every future image into one composition.
POSE_SCENE = re.compile(
    r"\b(lying down|prone|standing|sitting|squatting|from behind|from side|"
    r"close-?up|full body|upper body|cowboy shot|portrait|"
    r"tile floor|wet floor|puddle|indoors|outdoors|bedroom|bathroom|"
    r"dim lighting|backlighting|night|simple background|white background)\b",
    re.I,
)
# Tags that delete human anatomy. Only meaningful in a NEGATIVE — in a positive,
# `1girl` / `hair` / `eyes` are ordinary appearance and must not be flagged.
# Fine in a one-off creature-only render; catastrophic in a permanent field if
# the character ever shares a frame with a person.
HUMAN_SUPPRESS = re.compile(
    r"\b(1girl|1boy|human|humanoid|woman|girl|breasts|face|"
    r"limbs|legs|arms|hands|hair|eyes|person|people)\b",
    re.I,
)
# Blanket exclusions. In a positive these forbid a whole class of subject, so
# the character can never appear beside one. `no eyes` is an appearance trait,
# not an exclusion — the alternation must not swallow it.
POSITIVE_EXCLUSION = re.compile(r"\bno (humans|people|males|females|males or females)\b", re.I)
# Preset directives that commonly contradict a card's own rules.
PRESET_CONFLICT = re.compile(
    r"(never write \{\{user\}\}|never (speak|act)[^.]{0,40}\{\{user\}\}|"
    r"stay strictly in \{\{char\}\}'s pov|"
    r"reply length:\s*\d+[–-]\d+\s*paragraph)",
    re.I,
)

OK, WARN, FLAG = "ok", "warn", "flag"
findings: list[dict] = []


def add(level: str, area: str, subject: str, msg: str, fix: str = "") -> None:
    findings.append(
        {"level": level, "area": area, "subject": subject, "message": msg, "fix": fix}
    )


def load_settings() -> dict:
    with open(ST_DATA / "settings.json", encoding="utf-8") as f:
        return json.load(f)


def card_chunks(png: Path) -> list[dict]:
    """Every chara/ccv3 tEXt payload in a card PNG."""
    out = []
    data = png.read_bytes()
    i = 8
    while i < len(data) - 12:
        length = struct.unpack(">I", data[i : i + 4])[0]
        if data[i + 4 : i + 8] == b"tEXt":
            kw, _, txt = data[i + 8 : i + 8 + length].partition(b"\x00")
            if kw in (b"chara", b"ccv3"):
                try:
                    out.append(json.loads(base64.b64decode(txt).decode("utf-8")))
                except Exception:
                    pass
        i += 8 + length + 4
    return out


# ─────────────────────────── layer 1: SD char prompts ───────────────────────────
def audit_sd_prompts(s: dict, only: str | None) -> None:
    sd = s.get("extension_settings", {}).get("sd", {})
    pos_all = sd.get("character_prompts") or {}
    neg_all = sd.get("character_negative_prompts") or {}
    on_disk = {p.stem for p in (ST_DATA / "characters").glob("*.png")}

    for name in sorted(set(pos_all) | set(neg_all)):
        if only and name != only:
            continue
        pos, neg = pos_all.get(name, ""), neg_all.get(name, "")

        if name not in on_disk:
            add(WARN, "sd-prompts", name,
                "no characters/%s.png — orphan entry from a deleted card" % name,
                "drop the key, or restore the card")

        hits = sorted({h.lower() for h in POSE_SCENE.findall(pos)})
        if hits:
            add(FLAG, "sd-prompts", name,
                "positive bakes a pose/setting into every render: %s" % ", ".join(hits),
                "keep only always-true appearance here; move composition to "
                "%s/%s.txt" % (BASELINES, name))

        hits = sorted({"no " + h.lower() for h in POSITIVE_EXCLUSION.findall(pos)})
        if hits:
            add(FLAG, "sd-prompts", name,
                "positive carries a blanket exclusion (%s) — the character can "
                "never share a frame with that subject" % ", ".join(hits),
                "move to the per-shot baseline file; a permanent field cannot "
                "know whether this render is a solo shot")

        hits = sorted({h.lower() for h in HUMAN_SUPPRESS.findall(neg)})
        if hits:
            add(FLAG, "sd-prompts", name,
                "negative suppresses human anatomy: %s — every image containing "
                "the host silently loses those features" % ", ".join(hits),
                "negative holds only always-wrong APPEARANCE (colors, textures, "
                "materials); human-suppression belongs in a one-off negative")

        if not pos and not neg and name in on_disk:
            add(WARN, "sd-prompts", name, "both prompts empty — gens fall back to bare scene tags")

    # a style record that no longer matches the live values will clobber them
    # the moment anyone touches the Style dropdown
    for st in sd.get("styles") or []:
        if st.get("prefix") != sd.get("prompt_prefix") or st.get("negative") != sd.get("negative_prompt"):
            add(WARN, "sd-style", st.get("name", "?"),
                "saved style differs from the live prefix/negative",
                "selecting this style overwrites your tuned values — resave it, "
                "or keep it deliberately as a reset preset")


# ─────────────────────── layer 2: preset vs card precedence ───────────────────────
def audit_precedence(s: dict, only: str | None) -> None:
    pu = s.get("power_user", {})
    prefer_main = pu.get("prefer_character_prompt")
    prefer_jb = pu.get("prefer_character_jailbreak")

    conflicts: list[tuple[str, str, str]] = []
    for preset in sorted((ST_DATA / "OpenAI Settings").glob("*.json")):
        try:
            d = json.loads(preset.read_text(encoding="utf-8"))
        except Exception:
            continue
        enabled = {
            it.get("identifier")
            for blk in (d.get("prompt_order") or [])
            for it in blk.get("order", [])
            if it.get("enabled")
        }
        for p in d.get("prompts") or []:
            if p.get("identifier") not in ("main", "jailbreak"):
                continue
            if enabled and p["identifier"] not in enabled:
                continue
            for line in (p.get("content") or "").split("\n"):
                if PRESET_CONFLICT.search(line):
                    conflicts.append((preset.stem, p["identifier"], line.strip()))

    for preset, ident, line in conflicts:
        overridable = prefer_main if ident == "main" else prefer_jb
        field = "system_prompt" if ident == "main" else "post_history_instructions"
        if overridable:
            add(WARN, "precedence", f"{preset}:{ident}",
                "outranks card description: %r" % line[:110],
                "a card can beat it by filling data.%s (prefer flag is ON)" % field)
        else:
            add(FLAG, "precedence", f"{preset}:{ident}",
                "outranks card description and CANNOT be overridden: %r" % line[:110],
                "turn on prefer_character_%s, or edit the preset (affects every character)"
                % ("prompt" if ident == "main" else "jailbreak"))

    for png in sorted((ST_DATA / "characters").glob("*.png")):
        if only and png.stem != only:
            continue
        chunks = card_chunks(png)
        if not chunks:
            add(WARN, "card", png.stem, "no chara/ccv3 chunk found")
            continue
        if len({json.dumps(c, sort_keys=True) for c in chunks}) > 1:
            add(FLAG, "card", png.stem,
                "chara and ccv3 chunks DISAGREE — ST reads ccv3, so the other is stale",
                "patch every card-bearing chunk with identical content")
        d = chunks[0].get("data", chunks[0])
        if d.get("character_book"):
            add(WARN, "card", png.stem,
                "embedded character_book (%d entries) — NOT injected; ST only loads "
                "extensions.world" % len(d["character_book"].get("entries", [])),
                "dead weight in the PNG; strip it, or keep it for portability")
        if conflicts and not d.get("system_prompt"):
            add(WARN, "card", png.stem,
                "system_prompt empty while a preset 'main' directive conflicts",
                "fill data.system_prompt to override for this character only")


# ───────────────────────────── layer 3: lorebooks ─────────────────────────────
def audit_lorebooks(s: dict, only: str | None) -> None:
    pu = s.get("power_user", {})
    linked: dict[str, list[str]] = {}

    for png in sorted((ST_DATA / "characters").glob("*.png")):
        if only and png.stem != only:
            continue
        for c in card_chunks(png)[:1]:
            w = (c.get("data", c).get("extensions") or {}).get("world")
            if w:
                linked.setdefault(w, []).append(f"char:{png.stem}")
    for avatar, pd in (pu.get("persona_descriptions") or {}).items():
        if pd.get("lorebook"):
            linked.setdefault(pd["lorebook"], []).append(f"persona:{avatar}")

    for world, owners in sorted(linked.items()):
        path = ST_DATA / "worlds" / f"{world}.json"
        if not path.exists():
            add(FLAG, "lorebook", world, "linked by %s but the file is missing" % ", ".join(owners))
            continue
        entries = json.loads(path.read_text(encoding="utf-8")).get("entries", {})
        char_refs = sum(len(re.findall(r"\{\{char\}\}", e.get("content", ""))) for e in entries.values())
        consts = [e for e in entries.values() if e.get("constant")]
        always_on = sum(len(e.get("content", "")) for e in consts)

        if char_refs:
            add(WARN, "lorebook", world,
                "%d × {{char}} — these bind to whoever the card currently IS; a POV "
                "or role change silently repoints them" % char_refs,
                "name the entity explicitly when the card is a narrator or the role changed")
        if always_on:
            level = FLAG if always_on > 4000 else OK
            add(level, "lorebook", world,
                "%d constant entries, %d chars injected EVERY turn (~%d tok)"
                % (len(consts), always_on, always_on // 4),
                "constant entries are the most expensive and the most likely to "
                "contradict the card — re-read them after any card rewrite")
        for e in consts:
            if (e.get("depth") or 0) <= 2:
                add(WARN, "lorebook", world,
                    "constant entry %r sits at depth %s — same level as depth_prompt, "
                    "so it competes with the card's per-turn anchors"
                    % (e.get("comment", "?")[:44], e.get("depth")),
                    "move to depth 4 unless it genuinely must outrank the card")


# ───────────────────── layer 4: voice contract + steering entries ─────────────────────
FENCE = re.compile(r"never \{\{user\}\}'s speech|never \{\{user\}\}'s speech or decisions", re.I)
DOOR = re.compile(r"end on a door", re.I)


def audit_voice(s: dict) -> None:
    """The impersonation prompt and the Guided Generations wrappers are GLOBAL but
    must describe the ACTIVE persona; a Direction entry must be a menu (≤120 words),
    not a beat sheet."""
    pu = s.get("power_user", {})
    avatar = s.get("user_avatar", "")
    name = (pu.get("personas") or {}).get(avatar, "")
    imp = (s.get("oai_settings") or {}).get("impersonation_prompt", "") or ""
    if name and name.lower() not in imp.lower():
        add(FLAG, "voice", "impersonation_prompt",
            "does not name the active persona %r — Guided Impersonate writes a generic {{user}}" % name,
            "run /st-persona %s --voice" % name)
    desc = (pu.get("persona_descriptions") or {}).get(avatar) or {}
    active_name = (pu.get("personas") or {}).get(avatar, "")
    if active_name and (s.get("username") or "") != active_name:
        add(FLAG, "voice", "username",
            "settings.username (= name1, the name shown on every user message) is %r but the active persona is %r — "
            "activating a persona via MCP must also write top-level `username`" % (s.get("username"), active_name),
            "st_save_settings_path('username', '%s')" % active_name)
    if (pu.get("persona_description_lorebook") or "") != (desc.get("lorebook") or ""):
        add(FLAG, "voice", "persona_description_lorebook",
            "global persona lorebook %r != active persona's %r — ST injects the GLOBAL one (world-info.js getPersonaLorebook)"
            % (pu.get("persona_description_lorebook"), desc.get("lorebook")),
            "st_save_settings_path('power_user.persona_description_lorebook', '%s')" % (desc.get("lorebook") or ""))
    gg = (s.get("extension_settings") or {}).get("GuidedGenerations-Extension") or {}
    for key in ("promptGuidedResponse", "promptGuidedContinue"):
        txt = gg.get(key, "") or ""
        if not (FENCE.search(txt) and DOOR.search(txt)):
            add(WARN, "voice", key,
                "guide wrapper lacks the voice fence / door rule — a guide can make the narrator speak for {{user}}",
                "run /st-persona %s --voice" % (name or "<Name>"))
    if name and name.lower() not in (gg.get("promptImpersonate1st", "") or "").lower():
        add(WARN, "voice", "promptImpersonate1st", "wrapper does not name the active persona",
            "run /st-persona %s --voice" % name)

    for path in sorted((ST_DATA / "worlds").glob("*.json")):
        try:
            entries = json.loads(path.read_text(encoding="utf-8")).get("entries", {})
        except Exception:
            continue
        for e in entries.values():
            if "Direction" not in (e.get("comment") or "") or e.get("disable"):
                continue
            txt = e.get("content") or ""
            words = len(re.findall(r"[^\W_]+(?:'[^\W_]+)?", txt))  # real words, not separators/markdown
            if words > 120 or re.search(r"beats to reach|centre of the arc|give it room", txt, re.I):
                add(FLAG, "steering", f"{path.stem}:{e.get('comment','?')[:40]}",
                    "Direction entry is a beat sheet (%d words) — the narrator will run it as a script" % words,
                    "rewrite as Destination / Forks / Menu / Guards, ≤120 words (/st-arc-plan Phase 3)")
            if (e.get("order") or 100) > 100:
                add(WARN, "steering", f"{path.stem}:{e.get('comment','?')[:40]}",
                    "Direction entry order %s outranks Established State" % e.get("order"),
                    "order 100 — it is context, not a command")


# ────────────────────────── layer 5: Author's Note ──────────────────────────
def audit_note(s: dict) -> None:
    """A default Author's Note (extension_settings.note.default) injects into
    EVERY new chat; a per-chat note_prompt injects only into that one chat —
    both are easy to leave switched on after using a chat as a scratchpad."""
    note = s.get("extension_settings", {}).get("note", {}) or {}
    default = (note.get("default") or "").strip()
    if default:
        add(FLAG, "note", "extension_settings.note.default",
            "a default Author's Note is set — it injects into EVERY new chat "
            "at depth %s" % note.get("defaultDepth"),
            "st_save_settings_path('extension_settings.note.default', '')")

    for path in sorted(CHATS.glob("*/*.jsonl")):
        try:
            with open(path, encoding="utf-8") as f:
                first_line = f.readline()
            meta = json.loads(first_line)
        except Exception:
            continue
        note_prompt = (meta.get("chat_metadata", {}).get("note_prompt") or "").strip()
        if note_prompt:
            add(WARN, "note", str(path.relative_to(ST_DATA)),
                "per-chat Author's Note is set: %s" % note_prompt[:60])


# ───────────────────────────── layer 6: orphans ─────────────────────────────
def audit_orphans(s: dict) -> None:
    """Entries that outlive the card/persona they describe — nobody deletes
    these on their own, so they silently pile up."""
    # (orphan character_prompts keys are already reported by audit_sd_prompts)
    on_disk = {p.stem for p in (ST_DATA / "characters").glob("*.png")}
    persona_names = set((s.get("power_user", {}).get("personas") or {}).values())
    owners = on_disk | persona_names
    for txt in sorted(Path(BASELINES).glob("*.txt")):
        if txt.stem not in owners:
            add(WARN, "orphans", txt.stem, "identity baseline has no owner")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--char", help="scope to one character name (no .png)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    a = ap.parse_args()

    if not (ST_DATA / "settings.json").exists():
        print(f"settings.json not found under {ST_DATA}", file=sys.stderr)
        return 2

    s = load_settings()
    audit_sd_prompts(s, a.char)
    audit_precedence(s, a.char)
    audit_lorebooks(s, a.char)
    audit_voice(s)
    audit_note(s)
    audit_orphans(s)

    if a.as_json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
        return 1 if any(f["level"] == FLAG for f in findings) else 0

    icon = {OK: "·", WARN: "!", FLAG: "X"}
    order = {FLAG: 0, WARN: 1, OK: 2}
    if not findings:
        print("No config-layer problems found.")
        return 0
    for area in ["sd-prompts", "sd-style", "precedence", "card", "lorebook", "voice",
                 "steering", "note", "orphans"]:
        rows = [f for f in findings if f["area"] == area]
        if not rows:
            continue
        print(f"\n── {area}")
        for f in sorted(rows, key=lambda x: order[x["level"]]):
            print(f"  [{icon[f['level']]}] {f['subject']}: {f['message']}")
            if f["fix"]:
                print(f"        → {f['fix']}")
    n = sum(1 for f in findings if f["level"] == FLAG)
    print(f"\n{n} flagged, {sum(1 for f in findings if f['level']==WARN)} warnings.")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
