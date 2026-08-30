#!/usr/bin/env python3
"""st-sim.py — reproduce SillyTavern's OpenRouter request outside the browser.

Deterministic, read-only re-implementation of ST's Chat Completion assembly path
(`public/scripts/openai.js` :: prepareOpenAIMessages -> populateChatCompletion ->
populationInjectionPrompts / populateChatHistory / populateDialogueExamples), so
that narrator-contract tests can be run against hypothetical player behaviour
without touching the UI.

Subcommands
  build     assemble the request body for the active persona/preset + a character
  run       build + append a scenario's player turns + POST (non-stream) to OpenRouter
  from-log  extract the last `Chat Completion request: {` object from container logs
  diff      compare a `build` body against a `from-log` body

Scope / known limitations (say it out loud, don't pretend):
  * World Info: ONLY `constant` (blue-lightbulb), non-disabled entries are included.
    Keyword/recursion/timed-effect activation and the WI token budget are NOT simulated.
  * Token budget: the context budget is NOT enforced. Chat history is never truncated;
    the printed token count is a rough char-based estimate, not a real tokenizer.
  * Not simulated: groups, tool calling, media inlining, vectors/summary extensions,
    `continue`/`impersonate`/`quiet` generation types, logit bias, swipes.

Stdlib only (plus `node` shelled out for the JS-object-literal -> JSON step).
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import difflib
import glob
import json
import os
import re
import struct
import subprocess
import sys
import urllib.error
import urllib.request

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

DATA_ROOT = "/home/haint/Projects/home-server/sillytavern/data/default-user"
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS_PATH = os.path.join(SKILL_ROOT, "data", "sim-scenarios.json")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_HEADERS = {
    # src/constants.js :: OPENROUTER_HEADERS
    "HTTP-Referer": "https://sillytavern.app",
    "X-Title": "SillyTavern",
}

CONTAINER = "home-sillytavern"

# world_info_position (world-info.js)
WI_BEFORE, WI_AFTER, WI_EM_TOP, WI_EM_BOTTOM, WI_AT_DEPTH = 0, 1, 2, 3, 4
DEFAULT_WI_DEPTH = 4

# persona_description_positions (power-user.js)
PERSONA_IN_PROMPT, PERSONA_NONE, PERSONA_AT_DEPTH = 0, 9, 4

# extension_prompt_types (script.js)
EPT_NONE, EPT_IN_PROMPT, EPT_IN_CHAT, EPT_BEFORE_PROMPT = -1, 0, 1, 2

ROLE_BY_NUM = {0: "system", 1: "user", 2: "assistant"}

# character_names_behavior (openai.js)
NAMES_NONE, NAMES_DEFAULT, NAMES_CONTENT, NAMES_COMPLETION = -1, 0, 1, 2

PROMPT_ORDER_DUMMY_ID = 100001  # setupChatCompletionPromptManager :: promptOrder.dummyId


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def est_tokens(text: str) -> int:
    """Rough token estimate. NOT a real tokenizer — only for orientation.

    The divisor is calibrated against a real OpenRouter `usage.prompt_tokens`
    reading for this model + this prose style; expect a few percent of error.
    """
    if not text:
        return 0
    return max(1, int(len(text) / 4.4))


def est_tokens_messages(messages) -> int:
    return sum(est_tokens(m.get("content") or "") + 4 for m in messages)


def die(msg):
    print("error: " + msg, file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Character card (PNG tEXt chunks)
# --------------------------------------------------------------------------- #

def read_png_text_chunks(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        die("not a PNG: " + path)
    out = {}
    i = 8
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        ctype = data[i + 4:i + 8].decode("latin-1")
        body = data[i + 8:i + 8 + length]
        if ctype == "tEXt":
            key, _, val = body.partition(b"\x00")
            out[key.decode("latin-1")] = val
        i += 12 + length
        if ctype == "IEND":
            break
    return out


def load_character(name):
    """Load a character card. ST reads `ccv3` in preference to `chara`."""
    path = os.path.join(DATA_ROOT, "characters", name + ".png")
    if not os.path.exists(path):
        cands = sorted(
            os.path.basename(p)[:-4]
            for p in glob.glob(os.path.join(DATA_ROOT, "characters", "*.png"))
        )
        die("character card not found: %s (have: %s)" % (path, ", ".join(cands)))
    chunks = read_png_text_chunks(path)
    raw = chunks.get("ccv3") or chunks.get("chara")
    if not raw:
        die("card has no chara/ccv3 tEXt chunk: " + path)
    card = json.loads(base64.b64decode(raw).decode("utf-8"))
    data = card.get("data") or card
    return {
        "file": os.path.basename(path)[:-4],
        "spec": card.get("spec"),
        "name": data.get("name") or name,
        "description": data.get("description") or "",
        "personality": data.get("personality") or "",
        "scenario": data.get("scenario") or "",
        "first_mes": data.get("first_mes") or "",
        "mes_example": data.get("mes_example") or "",
        "system_prompt": data.get("system_prompt") or "",
        "post_history_instructions": data.get("post_history_instructions") or "",
        "alternate_greetings": data.get("alternate_greetings") or [],
        "world": ((data.get("extensions") or {}).get("world")) or "",
        "depth_prompt": (data.get("extensions") or {}).get("depth_prompt") or {},
    }


# --------------------------------------------------------------------------- #
# Macros — substituteParams (macros.js). Only the subset that the ST data here
# actually uses is meaningful; the rest are defensive.
# --------------------------------------------------------------------------- #

def substitute_params(text, env):
    if not text:
        return text or ""
    now = _dt.datetime.now()
    table = {
        "char": env.get("name2", ""),
        "bot": env.get("name2", ""),
        "user": env.get("name1", ""),
        "persona": env.get("persona", ""),
        "description": env.get("description", ""),
        "personality": env.get("personality", ""),
        "scenario": env.get("scenario", ""),
        "mesExamples": env.get("mes_examples", ""),
        "mesExamplesRaw": env.get("mes_examples", ""),
        "charPrompt": env.get("system_prompt", ""),
        "charJailbreak": env.get("post_history_instructions", ""),
        "charVersion": env.get("char_version", ""),
        "model": env.get("model", ""),
        "original": env.get("original", ""),
        "group": env.get("group", ""),
        "newline": "\n",
        "trim": "",
        "noop": "",
        "time": now.strftime("%H:%M"),
        "date": now.strftime("%Y-%m-%d"),
    }

    def repl(m):
        key = m.group(1).strip()
        low = key.lower()
        for k, v in table.items():
            if k.lower() == low:
                return v if v is not None else ""
        return m.group(0)  # leave unknown macros untouched

    out = re.sub(r"\{\{([^{}]*)\}\}", repl, text)
    out = out.replace("<USER>", env.get("name1", "")).replace("<BOT>", env.get("name2", ""))
    return out


def base_chat_replace(value, env):
    """script.js :: baseChatReplace — substitute + strip CR (collapse_newlines off here)."""
    if not value:
        return ""
    v = substitute_params(value, env)
    if env.get("collapse_newlines"):
        v = re.sub(r"\n+", "\n", v)
    return v.replace("\r", "")


# --------------------------------------------------------------------------- #
# World Info
# --------------------------------------------------------------------------- #

def load_world(name):
    path = os.path.join(DATA_ROOT, "worlds", name + ".json")
    if not os.path.exists(path):
        return []
    d = _read_json(path)
    entries = []
    for uid, e in (d.get("entries") or {}).items():
        e = dict(e)
        e["uid"] = e.get("uid", uid)
        e["world"] = name
        entries.append(e)
    return entries


def collect_world_info(settings, card, persona_lorebook):
    """world-info.js :: getSortedEntries + the prompt-building switch in checkWorldInfo.

    Only `constant`, non-disabled entries. Keyword activation is out of scope.
    Ordering replicates: sortFn = (a,b) => b.order - a.order  (descending, stable),
    then each bucket is built with `unshift`, i.e. the final joined string is the
    REVERSE of that descending sort.
    """
    wi = (settings.get("world_info_settings") or {}).get("world_info") or {}
    global_select = wi.get("globalSelect") or []
    char_lore_cfg = wi.get("charLore") or []
    strategy = int((settings.get("world_info_settings") or {}).get("world_info_character_strategy", 0))

    global_lore = []
    for w in global_select:
        global_lore += load_world(w)

    # getCharacterLore: card world + extraBooks, skipping books already active elsewhere
    worlds_to_search = []
    if card["world"]:
        worlds_to_search.append(card["world"])
    for entry in char_lore_cfg:
        if entry.get("name") == card["file"]:
            for b in entry.get("extraBooks") or []:
                if b not in worlds_to_search:
                    worlds_to_search.append(b)
    character_lore = []
    for w in worlds_to_search:
        if w in global_select or w == persona_lorebook:
            continue
        character_lore += load_world(w)

    persona_lore = []
    if persona_lorebook and persona_lorebook not in global_select:
        persona_lore = load_world(persona_lorebook)

    def srt(seq):
        return sorted(seq, key=lambda e: -int(e.get("order", 100) or 0))

    if strategy == 1:      # character_first
        entries = srt(character_lore) + srt(global_lore)
    elif strategy == 2:    # global_first
        entries = srt(global_lore) + srt(character_lore)
    else:                  # evenly
        entries = srt(global_lore + character_lore)

    # chat lore first, then persona lore, then the rest
    entries = srt(persona_lore) + entries

    activated = [e for e in entries if e.get("constant") and not e.get("disable")]
    activated = sorted(activated, key=lambda e: -int(e.get("order", 100) or 0))

    before, after, depth_buckets = [], [], []
    for e in activated:
        content = (e.get("content") or "").strip()
        if not content:
            continue
        pos = int(e.get("position", 0) or 0)
        if pos == WI_BEFORE:
            before.insert(0, content)
        elif pos == WI_AFTER:
            after.insert(0, content)
        elif pos == WI_AT_DEPTH:
            depth = e.get("depth")
            depth = DEFAULT_WI_DEPTH if depth is None else int(depth)
            role = int(e.get("role") or 0)
            hit = next((b for b in depth_buckets if b["depth"] == depth and b["role"] == role), None)
            if hit:
                hit["entries"].insert(0, content)
            else:
                depth_buckets.append({"depth": depth, "role": role, "entries": [content]})
        # EMTop/EMBottom/ANTop/ANBottom/outlet: not simulated (no such entries here)

    return {
        "before": "\n".join(before) if before else "",
        "after": "\n".join(after) if after else "",
        "depth": depth_buckets,
        "used_books": {
            "global": global_select,
            "character": worlds_to_search,
            "persona": persona_lorebook or None,
        },
        "constant_count": len(activated),
    }


# --------------------------------------------------------------------------- #
# Dialogue examples
# --------------------------------------------------------------------------- #

def parse_mes_examples(examples_str):
    """script.js :: parseMesExamples (main_api === 'openai' -> blockHeading '<START>\\n')."""
    if not examples_str or examples_str == "<START>":
        return []
    if not examples_str.startswith("<START>"):
        examples_str = "<START>\n" + examples_str.strip()
    blocks = re.split(r"<START>", examples_str, flags=re.I)[1:]
    return ["<START>\n" + b.strip() + "\n" for b in blocks]


def parse_example_into_individual(block, name1, name2):
    """openai.js :: parseExampleIntoIndividual (non-group)."""
    result = []
    lines = block.split("\n")
    cur = []
    in_user = in_bot = False

    def add(name, system_name):
        text = "\n".join(cur).replace(name + ":", "", 1).strip()
        result.append({"role": "system", "content": text, "name": system_name})
        cur.clear()

    for line in lines[1:]:  # skip the "{Example Dialogue:}" heading line
        if line.startswith(name1 + ":"):
            if in_bot:
                add(name2, "example_assistant")
            in_user, in_bot = True, False
        elif line.startswith(name2 + ":"):
            if in_user:
                add(name1, "example_user")
            in_user, in_bot = False, True
        cur.append(line)
    if in_user:
        add(name1, "example_user")
    elif in_bot:
        add(name2, "example_assistant")
    return result


def set_openai_message_examples(blocks, name1, name2):
    out = []
    for item in blocks:
        replaced = re.sub(r"<START>", "{Example Dialogue:}", item, count=1, flags=re.I).replace("\r", "")
        out.append(parse_example_into_individual(replaced, name1, name2))
    return out


# --------------------------------------------------------------------------- #
# Chat metadata (Author's Note lives per-chat)
# --------------------------------------------------------------------------- #

def newest_chat_file(char_file):
    files = sorted(
        glob.glob(os.path.join(DATA_ROOT, "chats", char_file, "*.jsonl")),
        key=os.path.getmtime,
        reverse=True,
    )
    return files[0] if files else None


def load_chat(char_file):
    path = newest_chat_file(char_file)
    if not path:
        return {}, []
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        return {}, []
    meta = rows[0].get("chat_metadata") or {}
    return meta, rows[1:]


# --------------------------------------------------------------------------- #
# The builder
# --------------------------------------------------------------------------- #

class Builder:
    def __init__(self, char_name=None, persona=None):
        self.settings = _read_json(os.path.join(DATA_ROOT, "settings.json"))
        self.oai = self.settings["oai_settings"]
        self.pu = self.settings["power_user"]
        self.ext = self.settings.get("extension_settings") or {}

        preset_name = self.oai.get("preset_settings_openai") or "Default"
        preset_path = os.path.join(DATA_ROOT, "OpenAI Settings", preset_name + ".json")
        if not os.path.exists(preset_path):
            die("preset not found: " + preset_path)
        self.preset_name = preset_name
        self.preset = _read_json(preset_path)

        # Active character: fall back to settings.active_character (an avatar filename)
        if not char_name:
            act = self.settings.get("active_character") or ""
            char_name = act[:-4] if act.endswith(".png") else act
        if not char_name:
            die("no character given and settings.active_character is empty")
        self.card = load_character(char_name)

        # Active persona (override with --persona: an avatar filename or a persona name)
        personas = self.pu.get("personas") or {}
        self.user_avatar = self.settings.get("user_avatar") or ""
        if persona:
            hit = None
            for avatar, pname in personas.items():
                if persona in (avatar, avatar[:-4] if avatar.endswith(".png") else avatar, pname):
                    hit = avatar
                    break
            if not hit:
                die("unknown persona %r (have: %s)"
                    % (persona, ", ".join(sorted(set(personas.values())))))
            self.user_avatar = hit
        self.name1 = personas.get(self.user_avatar) or self.settings.get("username") or "User"
        self.name2 = self.card["name"]

        pdesc = (self.pu.get("persona_descriptions") or {}).get(self.user_avatar) or {}
        self.persona_description = pdesc.get("description")
        if self.persona_description is None:
            self.persona_description = self.pu.get("persona_description") or ""
        self.persona_position = pdesc.get("position", self.pu.get("persona_description_position", 0))
        self.persona_depth = pdesc.get("depth", self.pu.get("persona_description_depth", 2))
        self.persona_role = pdesc.get("role", self.pu.get("persona_description_role", 0))
        # ST injects from the GLOBAL field (world-info.js getPersonaLorebook); the descriptor's
        # `lorebook` is only copied into it by the UI dropdown. Mirror ST, warn on mismatch.
        self.persona_lorebook = self.pu.get("persona_description_lorebook") or ""
        if (pdesc.get("lorebook") or "") != self.persona_lorebook:
            print(f"WARNING: persona_description_lorebook={self.persona_lorebook!r} but the active persona's descriptor says {pdesc.get('lorebook')!r} — ST uses the global one", file=sys.stderr)

        self.chat_meta, self.chat_rows = load_chat(self.card["file"])

        self.env = {
            "name1": self.name1,
            "name2": self.name2,
            "model": self.oai.get("openrouter_model") or "",
            "collapse_newlines": bool(self.pu.get("collapse_newlines")),
        }
        self.env["persona"] = base_chat_replace(self.persona_description, self.env)

        # Card fields (getCharacterCardFields); chat_metadata may override 3 of them
        self.description = base_chat_replace(self.card["description"].strip(), self.env)
        self.personality = base_chat_replace(self.card["personality"].strip(), self.env)
        scenario_src = self.chat_meta.get("scenario") or self.card["scenario"]
        self.scenario = base_chat_replace(scenario_src.strip(), self.env)
        mes_example_src = self.chat_meta.get("mes_example") or self.card["mes_example"]
        self.mes_examples = base_chat_replace(mes_example_src.strip(), self.env)
        sys_src = self.chat_meta.get("system_prompt") or self.card["system_prompt"]
        self.system_override = (
            base_chat_replace(sys_src.strip(), self.env)
            if self.pu.get("prefer_character_prompt") else ""
        )
        self.jailbreak_override = (
            base_chat_replace(self.card["post_history_instructions"].strip(), self.env)
            if self.pu.get("prefer_character_jailbreak") else ""
        )
        self.char_depth_prompt = base_chat_replace(
            (self.card["depth_prompt"].get("prompt") or "").strip(), self.env)

        self.wi = collect_world_info(self.settings, self.card, self.persona_lorebook)

    # -- greeting ---------------------------------------------------------- #

    def greetings(self):
        out = []
        if self.card["first_mes"].strip():
            out.append(("card.first_mes", self.card["first_mes"]))
        for i, g in enumerate(self.card["alternate_greetings"]):
            if (g or "").strip():
                out.append(("card.alternate_greetings[%d]" % i, g))
        if not out:
            # The card carries no greeting (arc openers are pasted into the chat
            # itself). Fall back to the first non-user message of the newest chat
            # so `build` stays comparable with a real `from-log` capture.
            for row in self.chat_rows:
                if not row.get("is_user") and not row.get("is_system") and (row.get("mes") or "").strip():
                    out.append(("chat.first_message (card greeting is empty)", row["mes"]))
                    break
        return out

    # -- extension prompts (in-chat injections) ---------------------------- #

    def extension_prompts_in_chat(self):
        """Mirror of script.js `extension_prompts` for IN_CHAT entries.

        getExtensionPrompt() sorts the KEYS with a plain `.sort()`, so the ASCII
        order of the keys decides the order inside one injected message:
          '2_floating_prompt' < 'DEPTH_PROMPT' < 'PERSONA_DESCRIPTION' < 'customDepthWI_*'
        """
        eps = {}

        # Author's Note (authors-note.js). interval 1 => always inserted.
        note_cfg = (self.ext.get("note") or {})
        note_text = self.chat_meta.get("note_prompt", note_cfg.get("default", "")) or ""
        note_interval = self.chat_meta.get("note_interval", note_cfg.get("defaultInterval", 1))
        note_position = self.chat_meta.get("note_position", note_cfg.get("defaultPosition", 1))
        note_depth = self.chat_meta.get("note_depth", note_cfg.get("defaultDepth", 4))
        note_role = self.chat_meta.get("note_role", note_cfg.get("defaultRole", 0))
        if note_text.strip() and note_interval == 1 and note_position == EPT_IN_CHAT:
            eps["2_floating_prompt"] = {
                "value": note_text, "depth": int(note_depth), "role": int(note_role)}

        # Character depth prompt (script.js ~4426)
        if self.char_depth_prompt.strip():
            dp = self.card["depth_prompt"]
            depth = dp.get("depth")
            depth = 4 if depth is None else int(depth)
            role = dp.get("role", "system")
            role_n = {"system": 0, "user": 1, "assistant": 2}.get(role, role if isinstance(role, int) else 0)
            eps["DEPTH_PROMPT"] = {"value": self.char_depth_prompt, "depth": depth, "role": int(role_n)}

        # Persona description at depth (script.js :: addPersonaDescriptionExtensionPrompt)
        if self.persona_description and int(self.persona_position) == PERSONA_AT_DEPTH:
            eps["PERSONA_DESCRIPTION"] = {
                "value": self.persona_description,
                "depth": int(self.persona_depth),
                "role": int(self.persona_role),
            }

        # World Info at-depth buckets (script.js ~4612)
        for bucket in self.wi["depth"]:
            key = "customDepthWI_%s_%s" % (bucket["depth"], bucket["role"])
            eps[key] = {
                "value": "\n".join(bucket["entries"]),
                "depth": int(bucket["depth"]),
                "role": int(bucket["role"]),
            }

        # macro pass (getExtensionPrompt substitutes at the end)
        for v in eps.values():
            v["value"] = substitute_params(v["value"], self.env)
        return eps

    # -- prompt collection ------------------------------------------------- #

    def prompt_collection(self):
        """PromptManager.getPromptCollection: prompt_order (enabled only) -> ordered list.

        Disabled prompts are dropped entirely (except `main`, kept as an empty
        placeholder), which is what makes the final indices shift.
        """
        by_id = {p["identifier"]: p for p in self.preset.get("prompts", [])}
        orders = self.preset.get("prompt_order") or []
        order = None
        for o in orders:
            if str(o.get("character_id")) == str(PROMPT_ORDER_DUMMY_ID):
                order = o.get("order")
                break
        if order is None and orders:
            order = orders[-1].get("order")
        if not order:
            die("preset has no usable prompt_order")

        collection = []
        for entry in order:
            ident = entry["identifier"]
            p = by_id.get(ident)
            if not p:
                continue
            if entry.get("enabled"):
                collection.append(dict(p))
            elif ident == "main":
                q = dict(p)
                q["content"] = ""
                collection.append(q)
        return collection, {e["identifier"]: bool(e.get("enabled")) for e in order}

    # -- main assembly ----------------------------------------------------- #

    def build(self, opener_index=0, player_turns=None):
        player_turns = player_turns or []
        collection, enabled = self.prompt_collection()
        index_of = {p["identifier"]: i for i, p in enumerate(collection)}

        wi_format = self.oai.get("wi_format") or "{0}"

        def fmt_wi(value):
            if not value:
                return ""
            if not wi_format.strip():
                return value
            return wi_format.replace("{0}", value)

        scenario_fmt = self.oai.get("scenario_format") or ""
        personality_fmt = self.oai.get("personality_format") or ""
        env = dict(self.env)
        env.update({
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "mes_examples": self.mes_examples,
            "system_prompt": self.system_override,
            "post_history_instructions": self.jailbreak_override,
        })
        scenario_text = substitute_params(scenario_fmt, env) if (self.scenario and scenario_fmt) else self.scenario
        personality_text = (substitute_params(personality_fmt, env)
                            if (self.personality and personality_fmt) else self.personality)

        # Marker content (preparePromptsForChatCompletion)
        marker_content = {
            "worldInfoBefore": fmt_wi(self.wi["before"]),
            "worldInfoAfter": fmt_wi(self.wi["after"]),
            "charDescription": self.description,
            "charPersonality": personality_text,
            "scenario": scenario_text,
            # personaDescription only becomes a relative prompt when position == IN_PROMPT
            "personaDescription": (self.persona_description
                                   if int(self.persona_position) == PERSONA_IN_PROMPT else ""),
        }

        # sparse slots, one per collection index (ChatCompletion.messages.collection)
        slots = [None] * len(collection)
        labels = [None] * len(collection)

        def put(ident, messages):
            i = index_of.get(ident)
            if i is None:
                return
            slots[i] = messages
            labels[i] = ident

        for ident, content in marker_content.items():
            if ident in index_of:
                put(ident, [{"role": "system", "content": content}] if content else [])

        # main / nsfw / jailbreak — content from the preset, overridden by the card
        for ident in ("main", "nsfw", "jailbreak"):
            if ident not in index_of:
                continue
            p = collection[index_of[ident]]
            content = p.get("content") or ""
            if ident == "main" and self.system_override and p.get("forbid_overrides") is not True \
                    and enabled.get("main", True):
                content = substitute_params(self.system_override, dict(env, original=p.get("content") or ""))
            elif ident == "jailbreak" and self.jailbreak_override and p.get("forbid_overrides") is not True \
                    and enabled.get("jailbreak", True):
                content = substitute_params(self.jailbreak_override, dict(env, original=p.get("content") or ""))
            else:
                content = substitute_params(content, env)
            role = p.get("role") or "system"
            put(ident, [{"role": role, "content": content}] if content else [])

        # any other enabled, non-marker preset prompt keeps its slot
        for i, p in enumerate(collection):
            if slots[i] is not None or labels[i] is not None:
                continue
            ident = p["identifier"]
            if ident in ("chatHistory", "dialogueExamples"):
                continue
            if p.get("marker"):
                slots[i], labels[i] = [], ident
                continue
            content = substitute_params(p.get("content") or "", env)
            slots[i], labels[i] = ([{"role": p.get("role") or "system", "content": content}] if content else []), ident

        # ---- dialogue examples ---- #
        example_msgs = []
        if "dialogueExamples" in index_of:
            blocks = parse_mes_examples(self.mes_examples)
            parsed = set_openai_message_examples(blocks, self.name1, self.name2)
            new_example_chat = substitute_params(self.oai.get("new_example_chat_prompt")
                                                 or self.preset.get("new_example_chat_prompt")
                                                 or "[Example Chat]", env)
            for dialogue in parsed:
                if not dialogue:
                    continue
                example_msgs.append({"role": "system", "content": new_example_chat})
                for m in dialogue:
                    if not m["content"]:
                        continue
                    msg = {"role": m["role"], "content": m["content"]}
                    if m.get("name"):
                        msg["name"] = m["name"]
                    example_msgs.append(msg)
            put("dialogueExamples", example_msgs)

        # ---- chat history ---- #
        greets = self.greetings()
        greeting_src, greeting_text = (None, "")
        if greets:
            if opener_index >= len(greets):
                die("--opener-index %d out of range (have %d greeting(s))" % (opener_index, len(greets)))
            greeting_src, greeting_text = greets[opener_index]
            greeting_text = base_chat_replace(greeting_text, self.env)

        chat = []  # chronological, ST `chat[]` shape after coreChat filtering
        if greeting_text:
            chat.append({"role": "assistant", "content": greeting_text, "name": self.name2})
        for turn in player_turns:
            turn = substitute_params(turn, env)
            if turn == "":
                # send_if_empty is '' -> ST appends NO user message for an empty send.
                continue
            chat.append({"role": "user", "content": turn, "name": self.name1})

        history = self.assemble_history(chat)
        put("chatHistory", history)

        # ---- flatten in slot order ---- #
        messages = []
        outline = []
        for i, group in enumerate(slots):
            if not group:
                continue
            for m in group:
                if not m.get("content"):
                    continue
                messages.append(m)
                outline.append(labels[i] or collection[i]["identifier"])

        meta = {
            "character": self.card["name"],
            "card_file": self.card["file"],
            "persona": self.name1,
            "persona_avatar": self.user_avatar,
            "preset": self.preset_name,
            "model": self.oai.get("openrouter_model"),
            "greeting_source": greeting_src,
            "lorebooks": self.wi["used_books"],
            "constant_wi_entries": self.wi["constant_count"],
            "outline": outline,
            "player_turns_appended": len([t for t in player_turns if t != ""]),
            "player_turns_given": len(player_turns),
        }
        return self.make_body(messages), meta

    def assemble_history(self, chat):
        """populationInjectionPrompts + populateChatHistory, minus token budgeting."""
        # setOpenAIMessages: the array is built newest-first
        messages = list(reversed([dict(m) for m in chat]))

        # names_behavior — NONE/DEFAULT/COMPLETION do not touch content for 1-on-1 chats
        names_behavior = int(self.oai.get("names_behavior", 0))
        if names_behavior == NAMES_CONTENT:
            for m in messages:
                if m.get("name"):
                    m["content"] = "%s: %s" % (m["name"], m["content"])

        eps = self.extension_prompts_in_chat()
        max_depth = max([v["depth"] for v in eps.values()] or [0])

        total_inserted = 0
        for i in range(0, max_depth + 1):
            role_messages = []
            for role_name, role_num in (("system", 0), ("user", 1), ("assistant", 2)):
                parts = []
                for key in sorted(eps.keys()):          # <-- plain ASCII key sort
                    p = eps[key]
                    if p["depth"] == i and p["role"] == role_num and p["value"].strip():
                        parts.append(p["value"].strip())
                if parts:
                    role_messages.append({"role": role_name, "content": "\n".join(parts)})
            if role_messages:
                idx = i + total_inserted
                messages[idx:idx] = role_messages
                total_inserted += len(role_messages)

        messages.reverse()

        out = []
        new_chat = substitute_params(self.oai.get("new_chat_prompt") or "[Start a new Chat]", self.env)
        if new_chat:
            out.append({"role": "system", "content": new_chat})
        for m in messages:
            msg = {"role": m["role"], "content": m["content"]}
            if names_behavior == NAMES_COMPLETION and m.get("name"):
                msg["name"] = m["name"]
            out.append(msg)
        return out

    def make_body(self, messages):
        """Mirror the final OpenRouter body that ST's server sends.

        Reference: src/endpoints/backends/chat-completions.js (OPENROUTER branch)
        plus the generic params; verified against a live `Chat Completion request:`
        log block.
        """
        o = self.oai
        body = {
            "messages": messages,
            "model": o.get("openrouter_model"),
            "temperature": o.get("temp_openai"),
            "max_tokens": o.get("openai_max_tokens"),
            "stream": False,
            "presence_penalty": o.get("pres_pen_openai"),
            "frequency_penalty": o.get("freq_pen_openai"),
            "top_p": o.get("top_p_openai"),
            "top_k": o.get("top_k_openai", self.preset.get("top_k", 0)),
            "transforms": ["middle-out"] if o.get("openrouter_middleout") == "on" else [],
            "plugins": [],
            "reasoning": {"exclude": not bool(o.get("show_thoughts"))},
            "min_p": o.get("min_p_openai", self.preset.get("min_p", 0)),
            "top_a": o.get("top_a_openai", self.preset.get("top_a", 0)),
            "repetition_penalty": o.get("repetition_penalty_openai", self.preset.get("repetition_penalty", 1)),
        }
        providers = o.get("openrouter_providers") or []
        if providers:
            body["provider"] = {
                "allow_fallbacks": bool(o.get("openrouter_allow_fallbacks", True)),
                "order": list(providers),
            }
        quants = o.get("openrouter_quantizations") or []
        if quants:
            body.setdefault("provider", {})["quantizations"] = list(quants)
        if o.get("openrouter_use_fallback"):
            body["route"] = "fallback"
        effort = o.get("reasoning_effort")
        if effort and effort not in ("auto",):
            body["reasoning"]["effort"] = effort
        return body


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #

def load_scenarios():
    if not os.path.exists(SCENARIOS_PATH):
        die("scenario file missing: " + SCENARIOS_PATH)
    return {s["id"]: s for s in _read_json(SCENARIOS_PATH)["scenarios"]}


# --------------------------------------------------------------------------- #
# Outline printing
# --------------------------------------------------------------------------- #

def print_outline(body, meta=None, stream=sys.stdout):
    msgs = body["messages"]
    w = stream.write
    if meta:
        w("char=%s  persona=%s  preset=%s  model=%s\n"
          % (meta["character"], meta["persona"], meta["preset"], meta["model"]))
        w("greeting=%s  lorebooks=%s  constant WI entries=%d\n"
          % (meta.get("greeting_source"), json.dumps(meta["lorebooks"]), meta["constant_wi_entries"]))
    labels = (meta or {}).get("outline") or [""] * len(msgs)
    for i, m in enumerate(msgs):
        c = (m.get("content") or "").replace("\n", "\\n")
        label = labels[i] if i < len(labels) else ""
        w("%3d %-9s %-18s %6d  %s\n" % (i, m["role"], label[:18], len(m.get("content") or ""), c[:80]))
    w("messages=%d  est_tokens~%d  (budget %s ctx - %s reply)\n"
      % (len(msgs), est_tokens_messages(msgs),
         (meta or {}).get("max_context", "?"), body.get("max_tokens")))


# --------------------------------------------------------------------------- #
# from-log
# --------------------------------------------------------------------------- #

LOG_MARKER = "Chat Completion request: {"


def extract_last_log_block(text):
    """Return the LAST `Chat Completion request: {...}` JS object literal.

    The literal is multi-line, single-quoted, uses `+` string concatenation and
    may contain `[Object]` / `[Array]` elisions from util.inspect. We find the
    matching top-level `}` by brace counting outside of string literals.
    """
    start = text.rfind(LOG_MARKER)
    if start < 0:
        return None
    i = text.index("{", start)
    depth = 0
    quote = None
    esc = False
    j = i
    n = len(text)
    while j < n:
        ch = text[j]
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = None
        else:
            if ch in "'\"`":
                quote = ch
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    return text[i:j + 1]
        j += 1
    return None


def js_literal_to_json(literal):
    """Evaluate the JS object literal with node and emit JSON."""
    script = (
        "const fs=require('fs');"
        "let src=fs.readFileSync(process.argv[1],'utf8');"
        "src=src.replace(/\\bundefined\\b/g,'null');"
        "src=src.replace(/'\\[Object\\]'|\\[Object\\]/g,'\"<elided:Object>\"');"
        "src=src.replace(/'\\[Array\\]'|\\[Array\\]/g,'\"<elided:Array>\"');"
        "src=src.replace(/\\.\\.\\. \\d+ more items?/g,'\"<elided:more>\"');"
        "const o=eval('('+src+')');"
        "process.stdout.write(JSON.stringify(o));"
    )
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(literal)
        tmp = fh.name
    try:
        proc = subprocess.run(["node", "-e", script, tmp], capture_output=True, text=True)
        if proc.returncode != 0:
            die("node failed to parse the log literal:\n" + proc.stderr.strip()[:2000])
        return json.loads(proc.stdout)
    finally:
        os.unlink(tmp)


def cmd_from_log(args):
    cmd = ["podman", "logs", "--since", args.since, CONTAINER]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    literal = extract_last_log_block(text)
    if not literal:
        die("no '%s' block found in the last %s of %s logs" % (LOG_MARKER, args.since, CONTAINER))
    body = js_literal_to_json(literal)
    body = {k: v for k, v in body.items() if v is not None}
    out = args.out or "/tmp/st-sim-fromlog.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=1)
    print("wrote %s (%d messages)" % (out, len(body.get("messages") or [])))
    print_outline(body)
    return 0


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #

def norm(text):
    """Normalise for text diffing: collapse whitespace runs, strip."""
    return re.sub(r"[ \t]+", " ", (text or "").replace("\r", "")).strip()


def segment(body, new_chat_prompt):
    """Split a request into header / chat-history / tail using the new-chat marker."""
    msgs = body.get("messages") or []
    nc = None
    for i, m in enumerate(msgs):
        if norm(m.get("content")) == norm(new_chat_prompt):
            nc = i
            break
    if nc is None:
        return msgs, [], []
    header = msgs[:nc]
    rest = msgs[nc + 1:]
    tail = []
    while rest and rest[-1]["role"] == "system":
        tail.insert(0, rest.pop())
    return header, rest, tail


def cmd_diff(args):
    a = _read_json(args.a)
    b = _read_json(args.b)
    settings = _read_json(os.path.join(DATA_ROOT, "settings.json"))
    new_chat = settings["oai_settings"].get("new_chat_prompt") or "[Start a new Chat]"

    ah, ahist, atail = segment(a, new_chat)
    bh, bhist, btail = segment(b, new_chat)

    print("== message counts ==")
    print("  A(%s): total=%d header=%d history=%d tail=%d"
          % (os.path.basename(args.a), len(a["messages"]), len(ah), len(ahist), len(atail)))
    print("  B(%s): total=%d header=%d history=%d tail=%d"
          % (os.path.basename(args.b), len(b["messages"]), len(bh), len(bhist), len(btail)))

    mismatches = 0

    def compare_block(tag, xs, ys):
        nonlocal mismatches
        print("\n== %s ==" % tag)
        if len(xs) != len(ys):
            print("  MISMATCH count: A=%d B=%d" % (len(xs), len(ys)))
            mismatches += 1
        for i in range(max(len(xs), len(ys))):
            x = xs[i] if i < len(xs) else None
            y = ys[i] if i < len(ys) else None
            if x is None or y is None:
                side = "A" if y is None else "B"
                other = x or y
                print("  [%d] present only in %s: %s %r"
                      % (i, "A" if y is None else "B", other["role"], norm(other["content"])[:70]))
                mismatches += 1
                continue
            if x["role"] != y["role"]:
                print("  [%d] MISMATCH role: A=%s B=%s" % (i, x["role"], y["role"]))
                mismatches += 1
            if x.get("name") != y.get("name"):
                print("  [%d] MISMATCH name: A=%r B=%r" % (i, x.get("name"), y.get("name")))
                mismatches += 1
            nx, ny = norm(x["content"]), norm(y["content"])
            if nx == ny:
                print("  [%d] %-9s OK  (%d chars)" % (i, x["role"], len(nx)))
            else:
                mismatches += 1
                sm = difflib.SequenceMatcher(None, nx, ny)
                print("  [%d] %-9s DIFF ratio=%.3f  A=%d chars B=%d chars"
                      % (i, x["role"], sm.ratio(), len(nx), len(ny)))
                dl = list(difflib.unified_diff(
                    nx.splitlines(), ny.splitlines(), "A", "B", lineterm="", n=1))
                for line in dl[:args.context]:
                    print("      " + line[:200])
                if len(dl) > args.context:
                    print("      ... %d more diff lines" % (len(dl) - args.context))

    compare_block("header (ordered prompts + dialogue examples)", ah, bh)
    compare_block("tail (post-history control prompts)", atail, btail)

    print("\n== chat history ==")
    print("  A=%d messages, B=%d messages (content beyond the greeting is expected to differ)"
          % (len(ahist), len(bhist)))
    # The greeting is the first NON-system history message: at-depth injections can
    # land in front of it when the history is shorter than the injection depth.
    ga = next((m for m in ahist if m["role"] != "system"), None)
    gb = next((m for m in bhist if m["role"] != "system"), None)
    if ga and gb:
        nx, ny = norm(ga["content"]), norm(gb["content"])
        if nx == ny:
            print("  greeting: OK (identical, %s, %d chars)" % (ga["role"], len(nx)))
        else:
            print("  greeting: DIFF ratio=%.3f (A=%s/%d chars B=%s/%d chars)"
                  % (difflib.SequenceMatcher(None, nx, ny).ratio(),
                     ga["role"], len(nx), gb["role"], len(ny)))
    else:
        print("  greeting: not comparable (A=%s B=%s)" % (bool(ga), bool(gb)))
    for tag, hist in (("A", ahist), ("B", bhist)):
        inj = [(i - len(hist), len(m["content"])) for i, m in enumerate(hist) if m["role"] == "system"]
        print("  %s in-history system injections (offset from end, chars): %s" % (tag, inj))

    print("\n== body params ==")
    keys = sorted((set(a) | set(b)) - {"messages"})
    for k in keys:
        if k == "messages":
            continue
        va, vb = a.get(k, "<absent>"), b.get(k, "<absent>")
        flag = "OK  " if va == vb else "DIFF"
        if va != vb:
            mismatches += 1
        print("  %s %-22s A=%s  B=%s" % (flag, k, json.dumps(va)[:60], json.dumps(vb)[:60]))

    print("\n%d mismatch group(s)." % mismatches)
    return 0


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #

def read_api_key():
    path = os.path.join(DATA_ROOT, "secrets.json")
    secrets = _read_json(path)
    entry = secrets.get("api_key_openrouter")
    if isinstance(entry, list):
        active = [e for e in entry if e.get("active")] or entry
        if not active:
            die("no openrouter key in secrets.json")
        return active[0]["value"]
    if isinstance(entry, str) and entry:
        return entry
    die("no api_key_openrouter in secrets.json")


def post_openrouter(body, key, timeout=300):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(OPENROUTER_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    for k, v in OPENROUTER_HEADERS.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:1000]
        die("OpenRouter HTTP %s: %s" % (e.code, detail))
    except urllib.error.URLError as e:
        die("OpenRouter request failed: %s" % (e.reason,))


def cmd_run(args):
    scenarios = load_scenarios()
    if args.scenario not in scenarios:
        die("unknown scenario %r (have: %s)" % (args.scenario, ", ".join(sorted(scenarios))))
    sc = scenarios[args.scenario]
    b = Builder(args.char, args.persona)
    body, meta = b.build(opener_index=args.opener_index, player_turns=sc["player_turns"])
    meta["max_context"] = b.oai.get("openai_max_context")

    outline = ["%s|%s|%d" % (m["role"], (meta["outline"][i] if i < len(meta["outline"]) else ""),
                             len(m.get("content") or ""))
               for i, m in enumerate(body["messages"])]
    print("scenario=%s (%s) rule_focus=%s" % (sc["id"], sc["name"], ",".join(sc["rule_focus"])))
    print_outline(body, meta)

    key = read_api_key()
    outdir = args.out or os.path.join("/tmp", "st-sim-runs")
    os.makedirs(outdir, exist_ok=True)

    for n in range(args.n):
        resp = post_openrouter(body, key)
        choice = (resp.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        record = {
            "scenario": {k: sc[k] for k in ("id", "name", "rule_focus", "player_turns", "notes")},
            "request_outline": {
                "character": meta["character"],
                "persona": meta["persona"],
                "preset": meta["preset"],
                "model": body["model"],
                "greeting_source": meta["greeting_source"],
                "messages": outline,
                "est_tokens": est_tokens_messages(body["messages"]),
            },
            "response": {
                "provider": resp.get("provider"),
                "finish_reason": choice.get("finish_reason") or choice.get("native_finish_reason"),
                "usage": resp.get("usage"),
                "content": content,
            },
        }
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(outdir, "%s-%s-%02d.json" % (sc["id"], stamp, n + 1))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=1)
        print("[%d/%d] provider=%s finish_reason=%s chars=%d usage=%s -> %s"
              % (n + 1, args.n, resp.get("provider"), record["response"]["finish_reason"],
                 len(content), json.dumps(resp.get("usage")), path))
    return 0


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def cmd_build(args):
    turns = []
    if args.scenario:
        scenarios = load_scenarios()
        if args.scenario not in scenarios:
            die("unknown scenario %r (have: %s)" % (args.scenario, ", ".join(sorted(scenarios))))
        turns = scenarios[args.scenario]["player_turns"]
    b = Builder(args.char, args.persona)
    body, meta = b.build(opener_index=args.opener_index, player_turns=turns)
    meta["max_context"] = b.oai.get("openai_max_context")
    print_outline(body, meta)
    out = args.out or "/tmp/st-sim-build.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=1)
    print("wrote " + out)
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="st-sim.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="assemble the request body ST would send")
    p.add_argument("--char", help="character card name (default: settings.active_character)")
    p.add_argument("--persona", help="persona name or avatar file (default: the active persona)")
    p.add_argument("--opener-index", type=int, default=0,
                   help="which greeting to use: 0=first_mes, 1..=alternate_greetings")
    p.add_argument("--scenario", help="also append this scenario's player turns")
    p.add_argument("--out", help="write the request body JSON here (default /tmp/st-sim-build.json)")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("run", help="build + POST non-stream to OpenRouter")
    p.add_argument("--scenario", required=True)
    p.add_argument("--char")
    p.add_argument("--persona", help="persona name or avatar file (default: the active persona)")
    p.add_argument("--opener-index", type=int, default=0)
    p.add_argument("--n", type=int, default=1, help="generations per scenario")
    p.add_argument("--out", help="output directory (default /tmp/st-sim-runs)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("from-log", help="extract the last real request from container logs")
    p.add_argument("--since", default="30m", help="podman logs --since value (default 30m)")
    p.add_argument("--out", help="write JSON here (default /tmp/st-sim-fromlog.json)")
    p.set_defaults(func=cmd_from_log)

    p = sub.add_parser("diff", help="compare two request bodies")
    p.add_argument("--a", required=True, help="usually the `build` output")
    p.add_argument("--b", required=True, help="usually the `from-log` output")
    p.add_argument("--context", type=int, default=12, help="max diff lines to print per message")
    p.set_defaults(func=cmd_diff)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
