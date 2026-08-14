"""
src/assemble/add_music.py
Input: data/output/final_video.mp4 (already has voice + SFX baked in) + a random
track from data/music/
Output: ./to_upload/video.mp4 + ./to_upload/metadata.json

FIX vs previous version (product-dev pass):
- Replaced the flat "VOICE_BOOST=2.0 to fight amix's normalization" hack with
  real EBU R128 loudness normalization (loudnorm) on the voice track. That
  hack had no relationship to how loud the voiceover actually was scene to
  scene - loudnorm gives consistent perceived loudness on every export
  regardless of topic/TTS run.
- Replaced the flat music volume with real sidechain compression: music now
  automatically ducks under the voice while it's talking and comes back up
  in the gaps, instead of sitting at one constant low level the whole time.
  This is the single biggest audible tell of an actually-mixed track vs
  "music playing underneath."
- Music now fades in/out at the very start/end instead of hard-cutting in
  and out at its assigned volume.
- pick_random_track / intro-skip offset / metadata generation are unchanged -
  those were already solid and aren't related to the mix itself.
"""
import subprocess
import random
import os
import glob
import json
import requests
from dotenv import load_dotenv
import re  

load_dotenv()


MUSIC_DIR = "data/music"
MUSIC_VOLUME = 0.18        # fixed music level under voice — no ducking, just balanced from the start
VOICE_LOUDNESS_I = -16     # standard broadcast loudness target (not -6, which was too hot/clipping-prone)
MUSIC_FADE_SEC = 1.0
FINAL_OUTPUT_DIR = r"./to_upload"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
SCRIPT_MODEL = "Gemini 1.5 Flash"



def get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def pick_random_track(music_dir=MUSIC_DIR):
    tracks = glob.glob(os.path.join(music_dir, "*.mp3")) + glob.glob(os.path.join(music_dir, "*.wav"))
    if not tracks:
        raise FileNotFoundError(f"No music tracks found in {music_dir}. Add .mp3/.wav files there.")
    return random.choice(tracks)



def generate_youtube_metadata(topic: str):
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
    SCRIPT_MODEL = "gemini-3.1-flash-lite"  # Make sure this is the exact model name

    if not GEMINI_KEY:
        print("ERROR: GEMINI_API_KEY is not set in your .env file!")
        return {"title": topic, "description": "", "tags": []}

    print(f"Generating YouTube metadata for: {topic} using model {SCRIPT_MODEL}")
    prompt = (
        f"Create YouTube metadata for a short video about '{topic}'. "
        f"Return ONLY valid JSON with keys 'title', 'description', and 'tags' (list of strings). "
        f"The title should be catchy and under 60 characters. "
        f"The description should be brief and engaging. "
        f"Tags should be 5-10 relevant SEO keywords."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{SCRIPT_MODEL}:generateContent"

    raw = None
    try:
        resp = requests.post(
            url,
            params={"key": GEMINI_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        
        json_start = raw.find('{')
        json_end = raw.rfind('}')
        
        if json_start != -1 and json_end != -1:
            cleaned = raw[json_start:json_end+1]
            metadata = json.loads(cleaned)
            print("Successfully generated metadata!")
            return {
                "title": metadata.get("title", topic),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", [])
            }
        else:
            raise ValueError("No JSON object found in Gemini response.")
            
    except Exception as e:
        print(f"\n!!! Failed to generate metadata: {e}")
        if raw is not None:
            print(f"Raw response was: {raw}")
        elif 'resp' in locals():
            # THIS WILL PRINT THE EXACT ERROR FROM GEMINI
            print(f"API Response Text: {resp.text}") 
        return {
            "title": topic,
            "description": "",
            "tags": []
        }


def add_music(video_path="data/output/final_video.mp4", topic: str = "video"):
    os.makedirs(FINAL_OUTPUT_DIR, exist_ok=True)

    out_path = os.path.join(FINAL_OUTPUT_DIR, "video.mp4")

    metadata = generate_youtube_metadata(topic)
    metadata_path = os.path.join(FINAL_OUTPUT_DIR, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved -> {metadata_path}")

    track = pick_random_track()
    video_duration = get_duration(video_path)
    track_duration = get_duration(track)
    print(f"Using track: {track}")

    min_start = 10
    max_start = max(min_start, track_duration - video_duration - 5)
    start_offset = random.uniform(min_start, max_start) if max_start > min_start else 0
    print(f"Music start offset: {start_offset:.1f}s")

    fade_out_start = max(0.0, video_duration - MUSIC_FADE_SEC)

    filter_complex = (
        f"[0:a]loudnorm=I={VOICE_LOUDNESS_I}:TP=-1.5:LRA=11[voice];"
        f"[1:a]volume={MUSIC_VOLUME},afade=t=in:d={MUSIC_FADE_SEC},"
        f"afade=t=out:st={fade_out_start}:d={MUSIC_FADE_SEC}[music];"
        f"[voice][music]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
    )

    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-ss", str(start_offset), "-stream_loop", "-1", "-i", track,
        "-t", str(video_duration),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        out_path,
    ], check=True)

    print(f"Final video with music -> {out_path}")
    return out_path


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "video"
    add_music(topic=topic)