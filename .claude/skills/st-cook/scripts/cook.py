#!/usr/bin/env python3
"""cook.py — the deterministic half of /st-cook.

Subcommands: inventory | render | validate | plan | ledger | close | selftest.
python3 stdlib only (no jsonschema, no httpx — this script never talks to ST; all
ST/MCP writes are the SKILL's job, dispatched via the Skill/mcp__st__* tools after
`plan --dry-run` has been read by Hải).

Exit codes: 0 ok · 1 assertion failure or novelty collision · 2 missing input
(recipe/fixture/template file not found, or a required binding absent).

Array placeholders
-------------------
Placeholder syntax is «UPPER_SNAKE» (guillemets never occur in live ST fields, so a
render is clean iff zero « remain in its output). Inside a JSON template, a
placeholder that is the ENTIRE value of a string field — e.g. `"key": "«KEYS_DOMINANCE»"`
— renders as a raw JSON array when its binding is a Python list: the quotes are
consumed and `"key": ["a","b"]` comes out. A placeholder embedded inside a larger
string (e.g. "...never «HER» words...") always renders as text: a list binding used
there is joined with " · " first. This lets one binding (recipe.lore.generic[i].keys)
serve a template field that must become `[]`/`["a","b"]` without a second templating
language.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import re
import shutil
import struct
import sys
import zlib
from pathlib import Path

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
SKILL_ROOT = Path(__file__).resolve().parent.parent          # .claude/skills/st-cook
REPO_ROOT = SKILL_ROOT.parents[2]                              # home-server/
ST_DATA = REPO_ROOT / "sillytavern" / "data" / "default-user"
SCRIPTS_DIR = ST_DATA / "_scripts"
LEDGER = SCRIPTS_DIR / "ledger.json"
BASELINES = REPO_ROOT / ".claude" / "skills" / "st-gen-image-prompt" / "data" / "identity-baselines"
ASSETS = SKILL_ROOT / "assets"
SETTINGS_PATH = ST_DATA / "settings.json"
CHARACTERS_DIR = ST_DATA / "characters"
WORLDS_DIR = ST_DATA / "worlds"
BACKUPS_DIR = ST_DATA / "backups"

PLACEHOLDER_RE = re.compile(r"«([A-Z0-9_]+)»")
QUOTED_PLACEHOLDER_RE = re.compile(r'"«([A-Z0-9_]+)»"')
WORD_RE = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)  # same regex as audit-config.py
# Vietnamese mode (PROMPT-PLAYBOOK 5.51): the anchors the model imitates must be in the
# campaign language, and trigger keys must be compound forms — ST's whole-word match
# (?:^|\W)key(?:$|\W) treats Vietnamese syllable boundaries as \W, so a bare monosyllable
# fires inside other words (bò→bò sát, cá→cá nhân, rắn→rắn chắc, mực = ink, gián→gián đoạn).
VI_DIACRITICS = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
VI_BARE_KEYS = {"bò", "cá", "rắn", "mực", "sán", "gián", "ong", "bọ", "dê", "ốc", "sên", "ếch", "cóc"}


class CookError(Exception):
    """Base for errors that should set a specific exit code."""
    exit_code = 1


class MissingInput(CookError):
    exit_code = 2


class AssertionFailed(CookError):
    exit_code = 1


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------
def load_json(path: Path):
    if not path.exists():
        raise MissingInput(f"missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MissingInput(f"invalid JSON in {path}: {e}")


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def today() -> str:
    return datetime.date.today().isoformat()


# --------------------------------------------------------------------------
# Template rendering
# --------------------------------------------------------------------------
def render_template_text(text: str, bindings: dict) -> str:
    """Fill «PLACEHOLDER» tokens in `text` from `bindings`.

    Two passes: first, a whole-field JSON string placeholder (`"«KEY»"`) whose
    binding is a list becomes a raw JSON array. Second, every remaining «KEY»
    (embedded in running text) is substituted as a string — a list binding is
    joined with " · " (this is how recipe.direction.ch1.forks/menu become the
    Direction entry's Forks/Menu lines).
    """

    def _array_sub(m: "re.Match[str]") -> str:
        key = m.group(1)
        if key not in bindings:
            raise MissingInput(f"unbound placeholder «{key}»")
        val = bindings[key]
        if isinstance(val, list):
            return json.dumps(val, ensure_ascii=False)
        return m.group(0)  # not a list — let the scalar pass handle it

    text = QUOTED_PLACEHOLDER_RE.sub(_array_sub, text)

    def _scalar_sub(m: "re.Match[str]") -> str:
        key = m.group(1)
        if key not in bindings:
            raise MissingInput(f"unbound placeholder «{key}»")
        val = bindings[key]
        if isinstance(val, list):
            val = " · ".join(str(v) for v in val)
        return str(val)

    text = PLACEHOLDER_RE.sub(_scalar_sub, text)
    return text


def assert_no_placeholders(text: str, label: str):
    if "«" in text or "»" in text:
        remaining = set(PLACEHOLDER_RE.findall(text))
        raise AssertionFailed(f"{label}: unrendered placeholders remain: {sorted(remaining)}")


# --------------------------------------------------------------------------
# Recipe schema helpers (hand-rolled validator; no jsonschema dependency)
# --------------------------------------------------------------------------
def load_recipe_schema() -> dict:
    return load_json(ASSETS / "recipe.schema.json")


PY_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _check_type(value, type_spec, path: str, errors: list):
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    py_types = tuple(PY_TYPE_MAP[t] for t in types if t in PY_TYPE_MAP)
    if py_types and not isinstance(value, py_types):
        # bool is a subclass of int in python — integer check already covers it
        errors.append(f"{path}: expected type {types}, got {type(value).__name__}")


def _validate_node(data, schema, schema_root, path, errors):
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/definitions/"), f"unsupported $ref {ref}"
        schema = schema_root["definitions"][ref.split("/")[-1]]

    if "type" in schema:
        _check_type(data, schema["type"], path, errors)

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: {data!r} not in enum {schema['enum']}")

    if isinstance(data, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                errors.append(f"{path}: missing required key '{key}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(data.keys()) - set(props.keys())
            if extra:
                errors.append(f"{path}: unexpected keys {sorted(extra)}")
        for key, subschema in props.items():
            if key in data:
                _validate_node(data[key], subschema, schema_root, f"{path}.{key}", errors)

    if isinstance(data, list) and "items" in schema:
        for i, item in enumerate(data):
            _validate_node(item, schema["items"], schema_root, f"{path}[{i}]", errors)


def validate_recipe(recipe: dict, schema: dict) -> list:
    errors: list = []
    _validate_node(recipe, schema, schema, "recipe", errors)
    return errors


# --------------------------------------------------------------------------
# PNG chara-chunk reading (mirrors scratchpad/reboot/patch-card.py's parser)
# --------------------------------------------------------------------------
def read_card_png(path: Path) -> dict | None:
    """Best-effort read of a character PNG's chara/ccv3 tEXt chunk. Returns the
    decoded card dict (V2 'data' subtree if present, else the root) or None."""
    try:
        png = path.read_bytes()
    except OSError:
        return None
    i = 8
    chunks = []
    while i < len(png) - 12:
        try:
            ln = struct.unpack(">I", png[i : i + 4])[0]
            ct = png[i + 4 : i + 8]
            data = png[i + 8 : i + 8 + ln]
        except struct.error:
            break
        if ct == b"tEXt":
            kw, _, txt = data.partition(b"\x00")
            if kw in (b"chara", b"ccv3"):
                try:
                    chunks.append((kw, json.loads(base64.b64decode(txt))))
                except Exception:
                    pass
        i += 8 + ln + 4
    if not chunks:
        return None
    # prefer ccv3 (ST's own preference, per patch-card.py)
    card = dict(chunks)
    raw = card.get(b"ccv3") or card.get(b"chara")
    return raw.get("data", raw) if isinstance(raw, dict) else None


def card_world(card_data: dict | None) -> str | None:
    if not card_data:
        return None
    return (card_data.get("extensions") or {}).get("world") or None


# --------------------------------------------------------------------------
# inventory
# --------------------------------------------------------------------------
def cmd_inventory(args):
    settings = load_json(SETTINGS_PATH) if SETTINGS_PATH.exists() else {}
    power_user = settings.get("power_user", {})
    personas = power_user.get("personas", {})
    persona_descriptions = power_user.get("persona_descriptions", {})
    user_avatar = settings.get("user_avatar")
    global_persona_lorebook = power_user.get("persona_description_lorebook")
    character_prompts = settings.get("character_prompts", {}) or {}
    note_default = (settings.get("extension_settings", {}) or {}).get("note", {}).get("default", "")
    gg = (settings.get("extension_settings", {}) or {}).get("GuidedGenerations-Extension", {}) or {}

    cards = {}
    if CHARACTERS_DIR.exists():
        for png in sorted(CHARACTERS_DIR.glob("*.png")):
            data = read_card_png(png)
            cards[png.stem] = {
                "world": card_world(data),
                "readable": data is not None,
            }

    worlds = {}
    world_bak_files = []
    if WORLDS_DIR.exists():
        for wf in sorted(WORLDS_DIR.glob("*.json")):
            w = load_json(wf) if wf.exists() else {}
            entries = w.get("entries", {})
            const_count = sum(1 for e in entries.values() if e.get("constant"))
            pointed_by_card = [name for name, c in cards.items() if c["world"] == wf.stem]
            pointed_by_persona_lorebook = [
                av for av, pd in persona_descriptions.items() if pd.get("lorebook") == wf.stem
            ]
            pointed_by_global = global_persona_lorebook == wf.stem
            worlds[wf.stem] = {
                "entry_count": len(entries),
                "constant_count": const_count,
                "pointed_by_card": pointed_by_card,
                "pointed_by_persona_lorebook": pointed_by_persona_lorebook,
                "pointed_by_global_persona_lorebook": pointed_by_global,
            }
        world_bak_files = [str(p.relative_to(ST_DATA)) for p in WORLDS_DIR.glob("*.json.bak-*")]

    baselines = sorted(p.stem for p in BASELINES.glob("*.txt")) if BASELINES.exists() else []

    ledger_rows = load_json(LEDGER) if LEDGER.exists() else []
    ledger_slugs = {row.get("slug") for row in ledger_rows}

    gg_prompts_present = {
        k: bool(v) for k, v in gg.items() if k.startswith("prompt") and isinstance(v, str)
    }

    # -------- orphan flags --------
    orphans = {"cards_without_recipe_or_ledger": [], "persona_name_collisions": [],
               "worlds_nobody_points_at": [], "character_prompts_without_png": [],
               "baselines_without_owner": [], "world_backup_files": world_bak_files}

    recipes = {}
    if SCRIPTS_DIR.exists():
        for rp in SCRIPTS_DIR.glob("*/recipe.json"):
            try:
                recipes[rp.parent.name] = load_json(rp)
            except MissingInput:
                pass
    recipe_char_names = {r.get("char", {}).get("name") for r in recipes.values()}

    for name in cards:
        if name in ledger_slugs:
            continue
        if name in recipe_char_names:
            continue
        if any(r.get("char", {}).get("name") == name for r in recipes.values()):
            continue
        orphans["cards_without_recipe_or_ledger"].append(name)

    display_names: dict[str, list[str]] = {}
    for avatar, display in personas.items():
        display_names.setdefault(display, []).append(avatar)
    for display, avatars in display_names.items():
        if len(avatars) > 1:
            orphans["persona_name_collisions"].append({display: avatars})

    for wname, w in worlds.items():
        pointed = w["pointed_by_card"] or w["pointed_by_persona_lorebook"] or w["pointed_by_global_persona_lorebook"]
        if not pointed:
            orphans["worlds_nobody_points_at"].append(wname)

    for key in character_prompts:
        if key not in cards:
            orphans["character_prompts_without_png"].append(key)

    for stem in baselines:
        if stem not in cards and stem not in personas.values():
            orphans["baselines_without_owner"].append(stem)

    result = {
        "cards": cards,
        "personas": personas,
        "persona_descriptions_lorebooks": {
            av: pd.get("lorebook") for av, pd in persona_descriptions.items()
        },
        "user_avatar": user_avatar,
        "global_persona_lorebook": global_persona_lorebook,
        "worlds": worlds,
        "baselines": baselines,
        "character_prompts_keys": list(character_prompts.keys()),
        "gg_prompts_present": gg_prompts_present,
        "note_default_empty": note_default == "",
        "ledger_rows": len(ledger_rows),
        "orphans": orphans,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(f"Cards ({len(cards)}): {', '.join(cards) or '(none)'}")
    print(f"Personas ({len(personas)}): {', '.join(personas.values()) or '(none)'}")
    print(f"  user_avatar={user_avatar}  global_persona_lorebook={global_persona_lorebook}")
    print(f"Worlds ({len(worlds)}):")
    for wname, w in worlds.items():
        print(f"  {wname}: {w['entry_count']} entries ({w['constant_count']} constant), "
              f"pointed-at={bool(w['pointed_by_card'] or w['pointed_by_persona_lorebook'] or w['pointed_by_global_persona_lorebook'])}")
    print(f"Baselines ({len(baselines)}): {', '.join(baselines) or '(none)'}")
    print(f"character_prompts keys: {', '.join(character_prompts) or '(none)'}")
    print(f"note.default empty: {note_default == ''}")
    print(f"Ledger rows: {len(ledger_rows)}")
    print("Orphans:")
    for k, v in orphans.items():
        print(f"  {k}: {v}")
    return 0


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------
def build_bindings(recipe: dict, schema: dict) -> dict:
    bindings = dict(schema.get("x-defaults", {}))
    bindings = {k: v for k, v in bindings.items() if not k.startswith("_")}

    language = recipe.get("language", "vi")
    language_name = "Vietnamese" if language == "vi" else "English"
    persona = recipe.get("persona", {})
    voice = persona.get("voice", {})
    derived = {
        "SLUG": recipe.get("slug"),
        # LANGUAGE / LANGUAGE_NAME are aliases for the same human-readable value
        # ("Vietnamese"/"English") — assets/persona/voice-block.tmpl and
        # assets/gg/prompts.json both read «LANGUAGE»; keep LANGUAGE_NAME too so
        # anything (docs, a future template) written against the other name still
        # resolves. FIRST_PERSON is the literal first-person pronoun the persona's
        # own (impersonation) turns should use — never the narrator's third-person
        # pages, which stay «PERSONA_NAME»/cô/chị/etc per the Vietnamese key rule.
        "LANGUAGE": language_name,
        "LANGUAGE_NAME": language_name,
        "FIRST_PERSON": "tôi" if language == "vi" else "I",
        "NAME": persona.get("name"),
        "PERSONA_NAME": persona.get("name"),
        "AGE": persona.get("age"),
        "GENDER": persona.get("gender"),
        "ETHNICITY": persona.get("ethnicity"),
        "APPEARANCE": persona.get("appearance"),
        "DEMEANOR": persona.get("demeanor"),
        "SOCIAL_CONTEXT": persona.get("social_context"),
        "KEYWORDS": persona.get("keywords"),
        "FACE_ID": persona.get("face_id"),
        "POV_TENSE": voice.get("pov_tense"),
        "REGISTER": voice.get("register"),
        "REGISTER_EARLY": voice.get("register"),
        "SHE_OWNS": voice.get("she_owns"),
        "SHE_NEVER_WRITES": voice.get("she_never_writes"),
        "ANATOMY_STOP_WORDS": voice.get("anatomy_stop"),
    }

    ch1 = recipe.get("direction", {}).get("ch1", {})
    derived.update({
        "N": 1,
        "TITLE": ch1.get("title"),
        "DESTINATION": (ch1.get("destination") or "").rstrip(". "),
        "FORKS": ch1.get("forks"),
        "MENU": ch1.get("menu"),
        "N_GUARD": ch1.get("n_guard"),
        "H_LIMIT": ch1.get("h_limit"),
        "COVER_WORDS": ch1.get("cover_words"),
        "DISSOCIATION": ch1.get("dissociation"),
    })

    for entry in recipe.get("lore", {}).get("generic", []):
        eid = entry.get("id", "").upper().replace("-", "_")
        derived[f"KEYS_{eid}"] = entry.get("keys", [])

    derived = {k: v for k, v in derived.items() if v is not None}

    bindings.update(derived)
    bindings.update(recipe.get("char", {}).get("params", {}))
    return bindings


def complete_lore_entry(shell: dict, uid: int, entry_defaults: dict) -> dict:
    entry = dict(entry_defaults["defaults"])
    entry["uid"] = uid
    entry["key"] = shell.get("key", [])
    entry["keysecondary"] = shell.get("keysecondary", [])
    entry["comment"] = shell["comment"]
    entry["content"] = shell["content"]
    entry["constant"] = shell.get("constant", False)
    entry["selective"] = not entry["constant"]
    entry["position"] = shell.get("position", 4)
    entry["depth"] = shell.get("depth", 4)
    entry["order"] = shell.get("order", 100)
    return entry


def assert_lore_entry_complete(entry: dict, entry_defaults: dict, label: str):
    expected = set(entry_defaults["defaults"].keys()) | set(entry_defaults["authored_fields"])
    missing = expected - set(entry.keys())
    if missing:
        raise AssertionFailed(f"{label}: lore entry missing fields {sorted(missing)}")


def cmd_render(args):
    recipe_path = Path(args.recipe)
    recipe = load_json(recipe_path)
    schema = load_recipe_schema()
    bindings = build_bindings(recipe, schema)

    out_dir = Path(args.out) if args.out else SCRIPTS_DIR / recipe["slug"] / "rendered"
    out_dir.mkdir(parents=True, exist_ok=True)

    only = set(args.only.split(",")) if args.only else None
    summary = []

    def want(name: str) -> bool:
        return only is None or name in only

    def render_file(rel_path: str, extra_bindings: dict | None = None) -> str:
        text = (ASSETS / rel_path).read_text(encoding="utf-8")
        b = dict(bindings)
        if extra_bindings:
            b.update(extra_bindings)
        return render_template_text(text, b)

    char = recipe.get("char", {})
    kind = char.get("kind", "narrator")
    language = recipe.get("language", "vi")

    # ---- card fields ----
    if want("card"):
        system_prompt = render_file("card/system_prompt.tmpl")
        assert_no_placeholders(system_prompt, "card/system_prompt")
        # v3 (prose-layer freed, 2026-08-31): structure lives in Direction/bible, not
        # in per-message rationing rules — VOICE FENCE / DOOR-rotation / TEMPO's
        # one-beat cap are dead. These 8 headers are the steering-not-fence contract.
        for header in ["ROLE.", "{{user}} STEERS.", "HER INTERIORITY", "THE CREATURE NEVER SPEAKS.",
                        "PACING — THE MANGA PAGE.", "THE LONG GAME.", "WORLD ALIVE.", "STYLE.", "LIMITS"]:
            if header not in system_prompt:
                raise AssertionFailed(f"card/system_prompt: missing section header '{header}'")

        phi = render_file("card/post_history_instructions.tmpl")
        assert_no_placeholders(phi, "card/post_history_instructions")
        # v3 PHI shape: bracketed, exactly 3 paragraphs (floor / creature-anatomy /
        # drive) — the old 8-item numbered checklist was itself part of the
        # over-constraint that strangled prose; never bring it back.
        phi_body = phi.strip()
        if not (phi_body.startswith("[") and phi_body.endswith("]")):
            raise AssertionFailed("card/post_history_instructions: must be a single [...] block")
        phi_paragraphs = [p for p in phi_body[1:-1].split("\n\n") if p.strip()]
        if len(phi_paragraphs) != 3:
            raise AssertionFailed(
                f"card/post_history_instructions: expected 3 paragraphs (v3 shape), got {len(phi_paragraphs)}"
            )

        personality = render_file("card/personality.tmpl").strip()
        assert_no_placeholders(personality, "card/personality")

        depth_prompt = render_file("card/depth_prompt.tmpl").strip()
        assert_no_placeholders(depth_prompt, "card/depth_prompt")

        scenario = render_file("card/scenario.tmpl").strip()
        assert_no_placeholders(scenario, "card/scenario")

        creator_notes = render_file("card/creator_notes.tmpl").strip()
        assert_no_placeholders(creator_notes, "card/creator_notes")

        # mes_example is REQUIRED on every cooked card (v3): a 2-exchange few-shot
        # voice anchor authored by the main loop at cook time. cook.py only passes
        # it through — never rejects the content — but a blank slot ships a card
        # with no style anchor at all, so that fails loudly here.
        mes_example = char.get("mes_example", "")
        if not mes_example.strip():
            raise AssertionFailed(
                "card-fields: mes_example must not be empty — every cooked card needs a "
                "2-exchange few-shot voice anchor (recipe.char.mes_example)"
            )
        # In a Vietnamese campaign the anchors MUST be Vietnamese: an English few-shot
        # under the lang_vi switch is exactly what drifted the narrator into first
        # person and English narration on 2026-09-06 (Playbook 5.51).
        if language == "vi":
            for field in ("mes_example", "first_mes"):
                txt = char.get(field, "") or ""
                if txt.strip() and not VI_DIACRITICS.search(txt):
                    raise AssertionFailed(
                        f"card-fields: recipe.language is 'vi' but char.{field} has no Vietnamese "
                        "diacritics — write the anchor in Vietnamese (narrator third person) or set language 'en'"
                    )

        create_schema = load_json(ASSETS / "card/create-body.schema.json")
        allowed_keys = set(create_schema["properties"].keys())
        card_fields = {
            "ch_name": char.get("name"),
            "description": char.get("description", ""),
            "personality": personality,
            "scenario": scenario,
            "first_mes": char.get("first_mes", ""),
            "mes_example": mes_example,
            "creator_notes": creator_notes,
            "system_prompt": system_prompt,
            "post_history_instructions": phi,
            "tags": char.get("tags", []),
            "alternate_greetings": char.get("alternate_greetings", []),
            "depth_prompt_prompt": depth_prompt,
            "depth_prompt_depth": 2,
            "depth_prompt_role": "system",
            "extensions": json.dumps({"depth_prompt": {"prompt": depth_prompt, "depth": 2, "role": "system"}}, ensure_ascii=False),
            "world": "",
        }
        extra = set(card_fields.keys()) - allowed_keys
        if extra:
            raise AssertionFailed(f"card-fields: keys not in create-body.schema.json: {sorted(extra)}")
        if card_fields["world"] != "":
            raise AssertionFailed("card-fields: world must be ''")
        (out_dir / "card-fields.json").write_text(
            json.dumps(card_fields, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary.append(("card-fields.json", f"system_prompt {len(system_prompt)}B, PHI {len(phi)}B"))

    # ---- lore ----
    if want("lore"):
        entry_defaults = load_json(ASSETS / "lore/entry.schema.json")
        generic_shells = load_json(ASSETS / "lore/generic-mechanics.json")["entries"]
        recipe_generic = {e["id"]: e for e in recipe.get("lore", {}).get("generic", [])}

        entries = {}
        uid = 0
        for shell in generic_shells:
            rendered_comment = render_template_text(shell["comment"], bindings)
            rendered_content = render_template_text(shell["content"], bindings)
            # Vietnamese campaigns use the shell's own key_vi (compound-form, fixed
            # vocabulary for the generic mechanic) instead of the English key
            # placeholder bound from recipe.lore.generic[].keys — see the Vietnamese
            # key rule (PROMPT-PLAYBOOK 5.51): bare Vietnamese monosyllables fire
            # inside unrelated compounds, so the vi vocabulary is authored once,
            # here, in compound form, rather than per-campaign.
            if language == "vi" and "key_vi" in shell:
                key_val = shell["key_vi"]
            else:
                key_val = shell["key"]
                if isinstance(key_val, str):
                    # array placeholder on its own — render via the whole-field path
                    key_val = json.loads(render_template_text(f'"{key_val}"', bindings)) \
                        if key_val.startswith("«") else render_template_text(key_val, bindings)
            entry_shell = {
                "comment": rendered_comment, "content": rendered_content, "key": key_val,
                "constant": shell["constant"], "position": shell["position"], "depth": shell["depth"],
                "order": shell["order"],
            }
            entry = complete_lore_entry(entry_shell, uid, entry_defaults)
            assert_no_placeholders(json.dumps(entry, ensure_ascii=False), f"lore/{shell['id']}")
            assert_lore_entry_complete(entry, entry_defaults, f"lore/{shell['id']}")
            entries[str(uid)] = entry
            uid += 1

        for spec in recipe.get("lore", {}).get("specific", []):
            entry = complete_lore_entry(spec, uid, entry_defaults)
            assert_lore_entry_complete(entry, entry_defaults, "lore/specific")
            entries[str(uid)] = entry
            uid += 1

        if language == "vi":
            for uid_s, entry in entries.items():
                bare = [k for k in entry.get("key", []) if isinstance(k, str) and k.strip().lower() in VI_BARE_KEYS]
                if bare:
                    raise AssertionFailed(
                        f"lore entry {uid_s} ({entry.get('comment','?')[:40]}): bare Vietnamese keys {bare} "
                        "fire inside other words — use compound forms (con bò, con rắn, mực ống, sán dây)"
                    )

        card_lorebook = {"name": char.get("name", "") + " Lore", "entries": entries}
        (out_dir / "card-lorebook.json").write_text(
            json.dumps(card_lorebook, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary.append(("card-lorebook.json", f"{len(entries)} entries"))

    # ---- persona lorebook (novelty ledger + direction) ----
    if want("persona-lorebook"):
        entry_defaults = load_json(ASSETS / "lore/entry.schema.json")

        ledger_shell = json.loads(render_file("lore/novelty-ledger.tmpl"))
        ledger_entry = complete_lore_entry(ledger_shell, 0, entry_defaults)
        assert_no_placeholders(json.dumps(ledger_entry, ensure_ascii=False), "lore/novelty-ledger")
        assert_lore_entry_complete(ledger_entry, entry_defaults, "lore/novelty-ledger")

        direction_shell = json.loads(render_file("direction/chapter.tmpl"))
        direction_entry = complete_lore_entry(direction_shell, 1, entry_defaults)
        assert_no_placeholders(json.dumps(direction_entry, ensure_ascii=False), "direction/chapter")
        assert_lore_entry_complete(direction_entry, entry_defaults, "direction/chapter")

        words = word_count(direction_entry["content"])
        if words > 120:
            raise AssertionFailed(f"direction/chapter: Direction is {words} real words (> 120)")

        # The persona book is seeded with the Novelty Ledger only; /st-arc-plan
        # --from-recipe adds the Direction from direction-ch1.json (it owns uids,
        # the previous-Direction check and the arc-save disable step).
        persona_lorebook = {
            "name": (bindings.get("PERSONA_NAME") or "") + " Lore",
            "entries": {"0": ledger_entry},
        }
        (out_dir / "persona-lorebook.json").write_text(
            json.dumps(persona_lorebook, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "direction-ch1.json").write_text(
            json.dumps(direction_entry, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary.append(("persona-lorebook.json", "Novelty Ledger seed"))
        summary.append(("direction-ch1.json", f"Direction {words} words"))

    # ---- persona description ----
    if want("persona"):
        voice_block = render_file("persona/voice-block.tmpl").strip()
        assert_no_placeholders(voice_block, "persona/voice-block")
        vb_words = word_count(voice_block)
        if vb_words > 90:
            raise AssertionFailed(f"persona/voice-block: {vb_words} words (> 90)")

        description = render_file("persona/description.tmpl", {"VOICE_BLOCK": voice_block}).strip()
        assert_no_placeholders(description, "persona/description")

        (out_dir / "persona-description.txt").write_text(description, encoding="utf-8")
        summary.append(("persona-description.txt", f"voice block {vb_words} words"))

    # ---- gg prompts ----
    if want("gg"):
        gg_raw = json.loads((ASSETS / "gg/prompts.json").read_text(encoding="utf-8"))
        gg_out = {}
        for key, val in gg_raw.items():
            if key.startswith("_"):
                continue
            gg_out[key] = render_template_text(val, bindings)
            assert_no_placeholders(gg_out[key], f"gg/{key}")
        gg_out["promptImpersonate1st_with_register"] = gg_out["promptImpersonate1st"] + gg_out["register_line"]
        (out_dir / "gg.json").write_text(
            json.dumps(gg_out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary.append(("gg.json", f"{len(gg_out)} fields"))

    # ---- baseline ----
    if want("baseline"):
        raw = (ASSETS / "baseline.tmpl").read_text(encoding="utf-8")
        marker = "## embodied" if kind == "embodied" else "## creature-only"
        other_marker = "## creature-only" if kind == "embodied" else "## embodied"
        section = raw.split(marker, 1)[1].split(other_marker, 1)[0]
        baseline = render_template_text(section.strip(), bindings)
        assert_no_placeholders(baseline, "baseline")
        (out_dir / "baseline.txt").write_text(baseline + "\n", encoding="utf-8")
        summary.append(("baseline.txt", f"kind={kind}"))

    # ---- sim scenarios ----
    if want("sim"):
        sim_raw = (ASSETS / "sim-scenarios.tmpl.json").read_text(encoding="utf-8")
        sim_rendered = render_template_text(sim_raw, bindings)
        assert_no_placeholders(sim_rendered, "sim-scenarios")
        json.loads(sim_rendered)  # must still be valid JSON after substitution
        (out_dir / "sim-scenarios.json").write_text(sim_rendered, encoding="utf-8")
        summary.append(("sim-scenarios.json", "S1-S8"))

    # ---- language switch state (read by the SKILL's Phase-3 dispatch step) ----
    if want("lang"):
        lang_state = {
            "language": language,
            "lang_vi_enabled": language == "vi",
            "openai_max_tokens": 6144 if language == "vi" else 4096,
        }
        (out_dir / "lang.json").write_text(json.dumps(lang_state, indent=2, ensure_ascii=False), encoding="utf-8")
        summary.append(("lang.json", f"language={language}, lang_vi_enabled={lang_state['lang_vi_enabled']}"))

    print(f"Rendered into {out_dir}")
    for name, note in summary:
        print(f"  {name}: {note}")
    return 0


# --------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------
def cmd_validate(args):
    recipe = load_json(Path(args.recipe))
    schema = load_recipe_schema()
    errors = validate_recipe(recipe, schema)
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print(f"OK: {args.recipe} matches recipe.schema.json")
    return 0


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------
def derive_dispatch(recipe: dict) -> list:
    """The canonical Phase-3 order, derived from the recipe when recipe.dispatch is empty.
    Each step removes one joint bug by construction (see SKILL.md Phase 3)."""
    slug = recipe.get("slug"); char = recipe.get("char", {}); persona = recipe.get("persona", {})
    cname = char.get("name"); pname = persona.get("name"); kind = char.get("kind", "narrator")
    full = recipe.get("profile") == "full"
    lang = recipe.get("language", "vi")
    rd = f"_scripts/{slug}/rendered"
    steps = [
        {"kind": "mcp", "args": "st_save_settings_path('extension_settings.note.default', '')", "why": "stale default Author's Note injects into every chat (joint bug #3)"},
        {"kind": "mcp", "args": f"st_create_character(name='{cname}', fields=<{rd}/card-fields.json>)  # world forced to ''", "why": "create the card with ST's default avatar"},
        {"kind": "mcp", "args": f"st_merge_character('{cname}.png', {{'data': {{'extensions': {{'world': '{cname}'}}}}}})", "why": "link the card lorebook after create (no embedded character_book)"},
    ]
    if kind == "narrator" and not full:
        steps += [
            {"kind": "mcp", "args": f"st_save_settings_path('extension_settings.sd.character_prompts.{cname}', '') + character_negative_prompts", "why": "narrator has no body — anything here is painted onto whoever is on screen"},
            {"kind": "file", "args": f"write identity-baselines/{cname}.txt from {rd}/baseline.txt", "why": "creature-only per-shot baseline"},
        ]
    else:
        steps.append({"kind": "skill", "args": f"/st-setup {cname} --from-recipe _scripts/{slug}/recipe.json --no-audit", "why": "embodied card or --full: SD baseline via st-setup"})
    steps += [
        {"kind": "mcp", "args": f"st_save_worldinfo('{cname}', <{rd}/card-lorebook.json>)", "why": "3 generic mechanics (Pressure Signature = the one constant)"},
        {"kind": "skill", "args": f"/st-persona {pname} --new --from-recipe _scripts/{slug}/recipe.json --lang {lang}" + (f" --avatar-file {persona.get('avatar',{}).get('file')}" if persona.get("avatar",{}).get("source") == "file" else ""), "why": "persona from recipe; activation writes BOTH user_avatar and persona_description_lorebook (joint bug #2)"},
        {"kind": "skill", "args": f"/st-persona {pname} --voice --lang {lang}", "why": "voice contract lives in global fields — always re-apply (joint bug #1)"},
        {"kind": "mcp", "args": f"st_save_worldinfo('{pname}', <{rd}/persona-lorebook.json>)", "why": "seed the Novelty Ledger constant so PHI check (7) has a target"},
        {"kind": "mcp", "args": "language contract: enable lang_vi + set openai_max_tokens (vi) or disable lang_vi (en)", "why": "Playbook 5.51 — output language is a preset switch, not a per-message instruction"},
        {"kind": "mcp", "args": f"illustration vars: extension_settings.variables.global.illust_prefix/illust_negative for '{pname}'", "why": "Playbook 5.50 follow-up — FREE-mode /sd needs the persona's identity+LoRA tags in globals"},
        {"kind": "skill", "args": f"/st-arc-plan --from-script _scripts/{slug}/bible.md#ch1 --from-recipe _scripts/{slug}/recipe.json --openers-to-card --scenarios {rd}/sim-scenarios.json --lang {lang}", "why": "Direction ≤120 words + 3 openers into the card + sim gate S1–S8"},
    ]
    if full:
        steps.append({"kind": "agent", "args": f"Agent(model=haiku): /st-setup {cname} --expr", "why": "28 sprites, zero decisions"})
    steps += [
        {"kind": "shell", "args": f"audit-config.py --char {cname} --json", "why": "the ONE audit; exit 0 = green"},
        {"kind": "shell", "args": f"cook.py ledger add --recipe _scripts/{slug}/recipe.json", "why": "campaign ledger row"},
    ]
    return steps


def cmd_plan(args):
    recipe = load_json(Path(args.recipe))
    dispatch = recipe.get("dispatch") or derive_dispatch(recipe)
    print(f"Dispatch plan for '{recipe.get('slug')}' ({len(dispatch)} steps) — DRY RUN ONLY.")
    print("cook.py never executes a write; the skill performs each step in order via")
    print("the Skill tool / mcp__st__* tools / file writes, after Hải reads this list.")
    print()
    for i, step in enumerate(dispatch, 1):
        kind = step.get("kind")
        args_preview = step.get("args", "")
        if kind == "mcp" and len(args_preview) > 80:
            args_preview = args_preview[:77] + "..."
        print(f"{i:2}. [{kind}] {args_preview}")
        if step.get("why"):
            print(f"    why: {step['why']}")
    return 0


# --------------------------------------------------------------------------
# ledger
# --------------------------------------------------------------------------
def load_ledger(path: Path | None = None) -> list:
    # NB: default is resolved at CALL time (`path or LEDGER`), not def time — cmd_selftest
    # reassigns the module-level LEDGER to a temp copy for the duration of its ledger
    # checks, and a def-time-bound default would silently keep pointing at the real file.
    path = path or LEDGER
    if not path.exists():
        return []
    return load_json(path)


def save_ledger(rows: list, path: Path | None = None):
    path = path or LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def novelty_collision(row: dict, rows: list) -> dict | None:
    def norm_set(v):
        return {str(x).lower() for x in (v or [])}

    creature = str(row.get("creature", "")).lower()
    orifice = norm_set(row.get("orifice"))
    partner = norm_set(row.get("partner_config"))
    setting = str(row.get("setting", "")).lower()
    for other in rows:
        if other.get("slug") == row.get("slug"):
            continue
        if (str(other.get("creature", "")).lower() == creature
                and norm_set(other.get("orifice")) == orifice
                and norm_set(other.get("partner_config")) == partner
                and str(other.get("setting", "")).lower() == setting):
            return other
    return None


def cmd_ledger(args):
    if args.ledger_cmd == "list":
        rows = load_ledger()
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    if args.ledger_cmd == "add":
        recipe = load_json(Path(args.recipe))
        row = recipe.get("ledger_row") or {}
        row.setdefault("slug", recipe.get("slug"))
        row.setdefault("date", today())
        rows = load_ledger()
        rows = [r for r in rows if r.get("slug") != row["slug"]]
        rows.append(row)
        save_ledger(rows)
        print(f"Added/updated ledger row for '{row['slug']}' ({len(rows)} total rows)")
        return 0

    if args.ledger_cmd == "novelty":
        recipe = load_json(Path(args.recipe))
        row = recipe.get("ledger_row") or {}
        rows = load_ledger()
        collision = novelty_collision(row, rows)
        if collision:
            print(f"NOVELTY COLLISION with existing row '{collision.get('slug')}': "
                  f"creature={collision.get('creature')!r} orifice={collision.get('orifice')} "
                  f"partner_config={collision.get('partner_config')} setting={collision.get('setting')!r}")
            return 1
        print("OK: no novelty collision")
        return 0

    if args.ledger_cmd == "set-status":
        rows = load_ledger()
        found = False
        for r in rows:
            if r.get("slug") == args.slug:
                r["status"] = args.status
                if args.archive:
                    r["closed"] = args.archive
                found = True
        if not found:
            raise MissingInput(f"no ledger row for slug '{args.slug}'")
        save_ledger(rows)
        print(f"'{args.slug}' status -> {args.status}" + (f" (archive: {args.archive})" if args.archive else ""))
        return 0

    raise CookError(f"unknown ledger subcommand {args.ledger_cmd}")


# --------------------------------------------------------------------------
# close
# --------------------------------------------------------------------------
def cmd_close(args):
    """Archive + filesystem half of `/st-cook --close`. Settings/ST writes are printed as mcp_todo."""
    slug = args.slug
    recipe_path = SCRIPTS_DIR / slug / "recipe.json"
    recipe = load_json(recipe_path)
    status = recipe.get("status")
    persona = recipe.get("persona", {}).get("name", "")
    char = recipe.get("char", {}).get("name", "")

    dry = bool(args.dry_run) or not args.yes
    if args.yes and status != "played":
        print(f"WARNING: recipe.status is {status!r}, not 'played' — closing anyway because --yes was given.")

    def resolve(w: str):
        if w.startswith("settings:"):
            return None
        if w.startswith("identity-baselines/"):
            return BASELINES / w.split("/", 1)[1]
        pth = Path(w)
        return pth if pth.is_absolute() else ST_DATA / w

    # what to archive: recipe.writes[] + the things a cook always produces
    candidates = [resolve(w) for w in recipe.get("writes", [])]
    candidates += [ST_DATA / "characters" / f"{char}.png", ST_DATA / "chats" / char,
                   ST_DATA / "worlds" / f"{char}.json", ST_DATA / "worlds" / f"{persona}.json",
                   ST_DATA / "User Avatars" / f"{persona} (Persona).png",
                   ST_DATA / "thumbnails" / "persona" / f"{persona} (Persona).png",
                   ST_DATA / "thumbnails" / "avatar" / f"{char}.png",
                   BASELINES / f"{char}.txt", BASELINES / f"{persona}.txt"]
    candidates += sorted((ST_DATA / "worlds").glob(f"{persona}.json.bak-*")) + sorted((ST_DATA / "worlds").glob(f"{char}.json.bak-*"))
    seen, targets = set(), []
    for c in candidates:
        if c is None or "secrets.json" in c.name or not c.exists() or c in seen:
            continue
        seen.add(c); targets.append(c)

    backup_dir = BACKUPS_DIR / f"{slug}-{today()}"
    print(f"{'[DRY RUN] ' if dry else ''}close --slug {slug}  (recipe.status={status})")
    print(f"Backup target: {backup_dir}")

    def rel_of(src: Path) -> Path:
        if ST_DATA in src.parents:
            return src.relative_to(ST_DATA)
        if BASELINES in src.parents:
            return Path("identity-baselines") / src.name
        return Path(src.name)

    def tree_size(p: Path) -> int:
        return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

    if not dry:
        backup_dir.mkdir(parents=True, exist_ok=True)
    for src in targets:
        rel, size = rel_of(src), tree_size(src)
        if dry:
            print(f"  would-copy     {rel} ({size}B)"); continue
        dst = backup_dir / rel; dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        if tree_size(dst) != size:
            raise AssertionFailed(f"close: byte-count mismatch copying {src}")
        print(f"  copied-ok      {rel} ({size}B)")

    # settings snapshot (full + the subtrees this campaign touched) and the active preset
    settings_path = ST_DATA / "settings.json"
    if settings_path.exists():
        sj = load_json(settings_path)
        preset = (sj.get("openai_settings") or sj.get("oai_settings") or {}).get("preset_settings_openai") or sj.get("oai_settings", {}).get("preset_settings_openai")
        preset_file = ST_DATA / "OpenAI Settings" / f"{preset}.json" if preset else None
        snap = {"user_avatar": sj.get("user_avatar"), "username": sj.get("username"),
                "power_user": {k: sj.get("power_user", {}).get(k) for k in ("personas", "persona_descriptions", "persona_description_lorebook")},
                "oai_settings.impersonation_prompt": sj.get("oai_settings", {}).get("impersonation_prompt"),
                "GuidedGenerations-Extension": sj.get("extension_settings", {}).get("GuidedGenerations-Extension"),
                "sd.character_prompts": sj.get("extension_settings", {}).get("sd", {}).get("character_prompts"),
                "note.default": sj.get("extension_settings", {}).get("note", {}).get("default")}
        if dry:
            print(f"  would-write    settings.json.full + settings-snapshot.json" + (f" + OpenAI Settings/{preset}.json" if preset_file and preset_file.exists() else ""))
        else:
            shutil.copy2(settings_path, backup_dir / "settings.json.full")
            (backup_dir / "settings-snapshot.json").write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
            if preset_file and preset_file.exists():
                (backup_dir / "OpenAI Settings").mkdir(exist_ok=True); shutil.copy2(preset_file, backup_dir / "OpenAI Settings" / preset_file.name)
            print("  wrote          settings.json.full + settings-snapshot.json")

    # files cook.py owns outright (the card PNG + chats go through st_delete_character; see mcp_todo)
    own_delete = [t for t in targets if not (t == ST_DATA / "characters" / f"{char}.png" or t == ST_DATA / "chats" / char)]
    if dry:
        for t in own_delete: print(f"  would-delete   {rel_of(t)}")
        print(f"  would-move     _scripts/{slug} -> {backup_dir / '_scripts' / slug}")
    else:
        for t in own_delete:
            shutil.rmtree(t) if t.is_dir() else t.unlink(); print(f"  removed        {rel_of(t)}")
        sd = SCRIPTS_DIR / slug
        if sd.exists():
            (backup_dir / "_scripts").mkdir(exist_ok=True); shutil.move(str(sd), str(backup_dir / "_scripts" / slug)); print(f"  moved          _scripts/{slug}")

    av = f'["{persona} (Persona).png"]'
    mcp_todo = {
        "1_persona_switch_away": ["user_avatar -> another persona's avatar", "username -> that persona's display name",
                                  "power_user.persona_description_lorebook -> that persona's lorebook (or '')"],
        "2_voice_reset": ["extension_settings.GuidedGenerations-Extension.promptImpersonate1st -> strip ' [Chapter ' register line, then re-run /st-persona <other> --voice",
                          "oai_settings.impersonation_prompt -> re-applied by that --voice", "extension_settings.note.default -> ''"],
        "3_character_prompts_delete": [f"extension_settings.sd.character_prompts.{char}", f"extension_settings.sd.character_negative_prompts.{char}"],
        "4_delete_character": {"tool": "st_delete_character", "avatar": f"{char}.png", "delete_chats": True},
        "5_persona_keys_delete": [f"power_user.personas.{av}", f"power_user.persona_descriptions.{av}"],
        "6_ledger": f"cook.py ledger set-status --slug {slug} --status closed --archive {backup_dir}",
    }
    print("\nmcp_todo (the SKILL performs these in order; cook.py never edits settings.json or calls ST):")
    print(json.dumps(mcp_todo, indent=2, ensure_ascii=False))
    if dry:
        print("\n[DRY RUN] nothing was copied or deleted. Re-run with --yes to execute.")
    return 0


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------
def cmd_selftest(args):
    import tempfile

    fixture_path = SKILL_ROOT / "scripts" / "fixtures" / "recipe.example.json"
    fixture = load_json(fixture_path)

    with tempfile.TemporaryDirectory(prefix="st-cook-selftest-") as tmp:
        tmp = Path(tmp)
        out_dir = tmp / "rendered"
        temp_ledger = tmp / "ledger.json"
        temp_ledger.write_text("[]", encoding="utf-8")

        # 1. render
        render_ns = argparse.Namespace(recipe=str(fixture_path), only=None, out=str(out_dir))
        rc = cmd_render(render_ns)
        assert rc == 0, "render should succeed on the fixture"
        rendered_files = list(out_dir.glob("*"))
        print(f"selftest: render OK — {len(rendered_files)} files in {out_dir}")

        # 2. validate
        validate_ns = argparse.Namespace(recipe=str(fixture_path))
        rc = cmd_validate(validate_ns)
        assert rc == 0, "validate should succeed on the fixture"
        print("selftest: validate OK")

        # 2b. Vietnamese variant — the fixture is an English demo; swap the anchors and keys
        # to Vietnamese and check the language plumbing end to end.
        vi = json.loads(json.dumps(fixture))
        vi["language"] = "vi"
        vi["char"]["mes_example"] = ("<START>\n{{user}}: *Tôi ghi mẫu vào sổ. Tại nóng thôi.*\n"
                                     "{{char}}: *Cô làm việc như cô làm mọi việc — quỳ bên lưới hút, tay áo ghim gọn.*\n"
                                     "<START>\n{{user}}: \"Tại nóng thôi,\" tôi nói.\n{{char}}: *Cô không rút tay về.*")
        vi["char"]["first_mes"] = "*Tờ biểu mẫu có một dòng cho nó. Dòng đó vẫn trống, vì bể lắng ấm.*"
        for g in vi["lore"]["generic"]:
            if g["id"] == "dominance":
                g["keys"] = ["kiểm soát", "kháng cự", "thói quen"]
            elif g["id"] == "irreversible":
                g["keys"] = ["biến chất", "không thể đảo ngược", "phòng khám"]
        vi_path = tmp / "recipe.vi.json"
        vi_path.write_text(json.dumps(vi, ensure_ascii=False), encoding="utf-8")
        vi_out = tmp / "rendered-vi"
        rc = cmd_render(argparse.Namespace(recipe=str(vi_path), only=None, out=str(vi_out)))
        assert rc == 0, "vi render should succeed"
        lang_state = json.loads((vi_out / "lang.json").read_text(encoding="utf-8"))
        assert lang_state == {"language": "vi", "lang_vi_enabled": True, "openai_max_tokens": 6144}, lang_state
        pdesc = (vi_out / "persona-description.txt").read_text(encoding="utf-8")
        assert "written in Vietnamese" in pdesc and "first person tôi" in pdesc and "own turns only" in pdesc, "voice block not labelled/Vietnamese"
        gg = json.loads((vi_out / "gg.json").read_text(encoding="utf-8"))
        assert "in Vietnamese" in gg["impersonation_prompt"] and "in Vietnamese" in gg["promptImpersonate1st"]
        book = json.loads((vi_out / "card-lorebook.json").read_text(encoding="utf-8"))
        shells = load_json(ASSETS / "lore/generic-mechanics.json")["entries"]
        assert book["entries"]["0"]["key"] == shells[0]["key_vi"], "vi campaign must use the shell's key_vi"
        print("selftest: vi variant OK — lang.json, labelled Vietnamese voice block, GG language line, key_vi")

        bad = json.loads(json.dumps(vi)); bad["char"]["mes_example"] = fixture["char"]["mes_example"]
        bad_path = tmp / "recipe.vi-english-anchor.json"; bad_path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        try:
            cmd_render(argparse.Namespace(recipe=str(bad_path), only=None, out=str(tmp / "rendered-bad")))
            raise SystemExit("selftest FAIL: vi recipe with an English mes_example rendered")
        except AssertionFailed:
            print("selftest: negative test OK — vi + English mes_example fails")

        bare = json.loads(json.dumps(vi))
        bare["lore"]["specific"] = [{"comment": "Cast — Taro", "content": "a dog", "key": ["Taro", "bò"], "constant": False}]
        bare_path = tmp / "recipe.vi-bare-key.json"; bare_path.write_text(json.dumps(bare, ensure_ascii=False), encoding="utf-8")
        try:
            cmd_render(argparse.Namespace(recipe=str(bare_path), only=None, out=str(tmp / "rendered-bare")))
            raise SystemExit("selftest FAIL: vi recipe with a bare monosyllabic key rendered")
        except AssertionFailed:
            print("selftest: negative test OK — bare Vietnamese key 'bò' fails")

        # 3. ledger novelty against a temp ledger copy
        global LEDGER
        real_ledger = LEDGER
        LEDGER = temp_ledger
        try:
            novelty_ns = argparse.Namespace(ledger_cmd="novelty", recipe=str(fixture_path))
            rc = cmd_ledger(novelty_ns)
            assert rc == 0, "novelty check should pass against an empty ledger"
            print("selftest: ledger novelty OK")

            # A DIFFERENT slug with the same creature x orifice x partner_config x
            # setting must collide (novelty_collision skips rows with a matching slug,
            # since a recipe never collides with its own not-yet-played row).
            twin = json.loads(json.dumps(fixture))
            twin["slug"] = "fixture-bland-twin"
            twin["ledger_row"]["slug"] = "fixture-bland-twin"
            twin_path = tmp / "recipe.twin.json"
            twin_path.write_text(json.dumps(twin), encoding="utf-8")

            add_ns = argparse.Namespace(ledger_cmd="add", recipe=str(fixture_path))
            rc = cmd_ledger(add_ns)
            assert rc == 0

            twin_novelty_ns = argparse.Namespace(ledger_cmd="novelty", recipe=str(twin_path))
            rc = cmd_ledger(twin_novelty_ns)
            assert rc == 1, "a twin recipe with the same creature/orifice/partner/setting must collide"
            print("selftest: ledger novelty collision detected correctly (twin slug, same configuration)")
        finally:
            LEDGER = real_ledger

        # 4. negative test — missing binding
        broken = json.loads(json.dumps(fixture))
        removed_key = None
        for k in list(broken["char"]["params"].keys()):
            removed_key = k
            del broken["char"]["params"][k]
            break
        broken_path = tmp / "recipe.broken-binding.json"
        broken_path.write_text(json.dumps(broken), encoding="utf-8")
        try:
            cmd_render(argparse.Namespace(recipe=str(broken_path), only=None, out=str(tmp / "rendered-broken")))
            raise SystemExit(f"selftest FAIL: render did not fail with '{removed_key}' removed")
        except (MissingInput, AssertionFailed):
            print(f"selftest: negative test OK — removing '{removed_key}' makes render fail")

        # 5. negative test — Direction too long
        too_long = json.loads(json.dumps(fixture))
        too_long["direction"]["ch1"]["destination"] = " ".join(["word"] * 150)
        too_long_path = tmp / "recipe.too-long.json"
        too_long_path.write_text(json.dumps(too_long), encoding="utf-8")
        try:
            cmd_render(argparse.Namespace(recipe=str(too_long_path), only=None, out=str(tmp / "rendered-long")))
            raise SystemExit("selftest FAIL: render did not fail on a 150-word Direction")
        except AssertionFailed:
            print("selftest: negative test OK — 150-word Direction destination fails the <=120 check")

    print("\nselftest: ALL PASS")
    return 0


# --------------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cook.py", description="Deterministic half of /st-cook.")
    sub = p.add_subparsers(dest="command", required=True)

    inv = sub.add_parser("inventory", help="read-only inventory of ST bricks on disk")
    inv.add_argument("--json", action="store_true")
    inv.set_defaults(func=cmd_inventory)

    ren = sub.add_parser("render", help="fill templates from a recipe")
    ren.add_argument("--recipe", required=True)
    ren.add_argument("--only", help="comma-separated subset: card,lore,persona-lorebook,persona,gg,baseline,sim,lang")
    ren.add_argument("--out")
    ren.set_defaults(func=cmd_render)

    val = sub.add_parser("validate", help="schema-check a recipe")
    val.add_argument("--recipe", required=True)
    val.set_defaults(func=cmd_validate)

    pln = sub.add_parser("plan", help="print the ordered dispatch list (dry-run only)")
    pln.add_argument("--recipe", required=True)
    pln.add_argument("--dry-run", action="store_true", help="accepted for symmetry; plan never executes anything")
    pln.set_defaults(func=cmd_plan)

    led = sub.add_parser("ledger", help="campaign ledger")
    led_sub = led.add_subparsers(dest="ledger_cmd", required=True)
    led_sub.add_parser("list")
    led_add = led_sub.add_parser("add")
    led_add.add_argument("--recipe", required=True)
    led_nov = led_sub.add_parser("novelty")
    led_nov.add_argument("--recipe", required=True)
    led_set = led_sub.add_parser("set-status")
    led_set.add_argument("--slug", required=True)
    led_set.add_argument("--status", required=True, choices=["cooking", "played", "closed"])
    led_set.add_argument("--archive")
    led.set_defaults(func=cmd_ledger)

    cls = sub.add_parser("close", help="archive + filesystem part of --close (MCP writes are the skill's job)")
    cls.add_argument("--slug", required=True)
    cls.add_argument("--dry-run", action="store_true")
    cls.add_argument("--yes", action="store_true")
    cls.set_defaults(func=cmd_close)

    st = sub.add_parser("selftest", help="render+validate+ledger novelty on the fixture, plus 2 negative tests")
    st.set_defaults(func=cmd_selftest)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args) or 0
    except CookError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return e.exit_code
    except AssertionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
