"""
src/script/generate_script.py
Input: topic/niche -> Output: video script broken into scenes
Uses a stronger model directly (not the rotation pool) since this is low-volume (1 call/video).

FIX vs previous version:
- Old prompt just asked for "a script about X, punchy, no filler" with zero
  structural direction -> model defaulted to Wikipedia-summary tone every
  time (generic setup -> generic complication -> generic sad ending). That's
  exactly the "cringe" you flagged on the Medusa script.
- New prompt assigns each scene a STORYTELLING ROLE (hook / escalation /
  climax / payoff) instead of just "a sentence about the topic", and gives
  explicit craft rules (concrete detail over abstract adjectives, vary
  sentence rhythm, land on irony/twist/gut-punch not a flat statement).
- Added a banned-phrase list of the exact cliches that make short-form
  scripts feel AI-generic ("was once", "little did she know", etc).
- generationConfig now sets temperature/topP explicitly - previous version
  ran on Gemini's flat default, which biases toward the safest/most generic
  phrasing. Higher temperature is what actually unlocks distinct voice.
- Added a self-check retry: after generating, the output is scanned for
  banned phrases; if any slipped through, we regenerate once with the
  specific offending phrases called out, instead of accepting first-try
  output unconditionally.
"""
import json
import os
import re
import time
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
SCRIPT_MODEL = "gemini-3.5-flash-lite"

MAX_SELF_CHECK_RETRIES = 2

BANNED_PHRASES = [
    "was once", "little did she know", "little did he know", "little did they know",
    "sealed her fate", "sealed his fate", "sealed their fate", "would forever",
    "eternal doom", "heartbreaking, eternal", "but here's the twist", "you won't believe",
    "in the blink of an eye", "and then everything changed", "her final reflection",
    "his final breath sealed", "forever changed the course of", "the rest is history",
    "curse of the gods", "or so they thought",
]

STORY_CRAFT_RULES = """
STORYTELLING RULES (grounded in how short-form narrative actually works,
not surface-level punchiness):

- IN MEDIAS RES: open mid-action or mid-consequence, never with backstory
  or scene-setting. "Medusa was once beautiful" is backstory - a stronger
  hook drops the viewer into a moment where something is already happening
  or already wrong, and lets context fill in as it goes.
- SHOW, DON'T TELL: replace abstract adjectives ("stunning", "terrifying",
  "tragic") with one concrete, physical, sensory detail (an object, a
  number, a specific action) that lets the viewer draw the conclusion
  themselves. Telling the viewer how to feel is the single biggest
  giveaway of generated writing.
- THE SHIFT: somewhere before the final scene, one specific beat must
  disrupt the viewer's expectation - not just "the stakes get bigger" but
  a genuine turn (an irony, a reversal, a detail that recontextualizes
  what came before).
- THE PAYOFF: the last scene must deliver on the hook's implicit promise
  with something specific and satisfying - an irony, a twist, a sharp
  unresolved question. It must NOT be a flat emotional summary
  ("and she was sad/cursed/doomed forever").
- Vary sentence rhythm scene to scene - don't repeat the same
  subject-verb-object shape across every line.
- Never narrate the audience's expected reaction ("shockingly," "tragically,"
  "unbelievably"). Let the concrete detail do that work instead.
"""


def _scene_roles(num_scenes: int) -> list:
    """Assigns each scene an explicit narrative role instead of treating
    every scene the same way. First = hook (in medias res), last = payoff,
    second-to-last = the shift, everything between = escalation."""
    if num_scenes <= 1:
        return ["Hook and payoff in one - in medias res opening that also lands a twist."]
    if num_scenes == 2:
        return [
            "HOOK: open in medias res, mid-action or mid-consequence.",
            "PAYOFF: land the twist/irony that recontextualizes scene 1.",
        ]
    roles = ["HOOK: open in medias res, mid-action or mid-consequence - no backstory."]
    for _ in range(num_scenes - 3):
        roles.append("ESCALATION: one concrete complication, show don't tell - a specific detail, not a bigger adjective.")
    roles.append("THE SHIFT: a specific beat that disrupts the viewer's expectation - a reversal or recontextualization.")
    roles.append("PAYOFF: land it - irony, twist, or sharp unresolved question. Not a flat emotional summary.")
    return roles


def _banned_phrase_hits(scenes):
    hits = []
    for scene in scenes:
        text = scene.get("narration", "").lower()
        for phrase in BANNED_PHRASES:
            if phrase in text:
                hits.append(phrase)
    return hits


def _build_prompt(topic: str, num_scenes: int, retry_feedback: str = "") -> str:
    roles = _scene_roles(num_scenes)
    roles_block = "\n".join(f"Scene {i + 1} role: {role}" for i, role in enumerate(roles))
    prompt = (
        f"Write a short-form video script about '{topic}' for an 18-second Short/Reel, "
        f"split into exactly {num_scenes} scenes.\n\n"
        f"{STORY_CRAFT_RULES}\n"
        f"SCENE-BY-SCENE ROLES (each scene must fulfill its specific job, not just "
        f"restate the topic):\n{roles_block}\n\n"
        f"FORMAT RULES:\n"
        f"- Each scene's narration is ONE sentence, under 12 words, readable aloud in ~4 seconds.\n"
        f"- No filler words, no narrator throat-clearing.\n"
        f"- For each scene also give a highly detailed visual description for an AI image "
        f"generator, as comma-separated descriptive tags, no art-style tags.\n"
        f"- If the narration names a specific character/entity, the visual MUST include their "
        f"exact name and distinct visual traits (e.g. 'Thor, muscular norse god with red beard "
        f"and hammer').\n\n"
        f"Never use any of these exact phrases or close variants of them: "
        f"{', '.join(BANNED_PHRASES)}.\n\n"
        f"Return ONLY valid JSON: a list of {num_scenes} objects with keys 'narration' and 'visual'."
    )
    if retry_feedback:
        prompt += (
            f"\n\nYour previous attempt used these banned/cliche phrases: {retry_feedback}. "
            f"Rewrite from scratch avoiding them entirely - do not just swap synonyms, "
            f"restructure the sentence."
        )
    return prompt


def call_gemini(prompt, model=SCRIPT_MODEL, retries=3):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    for attempt in range(retries):
        try:
            resp = requests.post(
                url,
                params={"key": GEMINI_KEY},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 1.05,
                        "topP": 0.95,
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            print(f"API Error {resp.status_code}: {resp.text}")
            if resp.status_code in [429, 500, 503] and attempt < retries - 1:
                print(f"Retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
            else:
                raise e


def _parse_scenes(raw: str):
    cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(cleaned)


def generate_script(topic: str, num_scenes: int = 4):
    prompt = _build_prompt(topic, num_scenes)
    raw = call_gemini(prompt)
    scenes = _parse_scenes(raw)

    for attempt in range(MAX_SELF_CHECK_RETRIES):
        hits = _banned_phrase_hits(scenes)
        if not hits:
            break
        print(f"self-check: found cliche phrases {hits}, regenerating (attempt {attempt + 1})")
        prompt = _build_prompt(topic, num_scenes, retry_feedback=", ".join(sorted(set(hits))))
        raw = call_gemini(prompt)
        scenes = _parse_scenes(raw)
    else:
        remaining = _banned_phrase_hits(scenes)
        if remaining:
            print(f"warning: cliche phrases still present after retries: {remaining}")

    return scenes


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "amazing space facts"
    scenes = generate_script(topic)
    with open("data/script.json", "w") as f:
        json.dump(scenes, f, indent=2)
    print(f"Generated {len(scenes)} scenes -> data/script.json")