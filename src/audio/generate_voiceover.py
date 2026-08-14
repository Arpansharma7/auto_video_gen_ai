"""
src/audio/generate_voiceover.py
Input: data/script.json -> Output: data/audio/full_audio.wav + data/audio/meta.json
Generates a single, continuous TTS track for the entire script.
"""
import json
import os
from kokoro import KPipeline
import soundfile as sf

VOICE = "am_puck" 
LANG_CODE = "a"     

pipeline = KPipeline(lang_code=LANG_CODE)

def generate_all(script_path="data/script.json", out_dir="data/audio"):
    os.makedirs(out_dir, exist_ok=True)
    with open(script_path) as f:
        scenes = json.load(f)

    # Combine all narrations into one string
    full_narration = " ".join(scene["narration"] for scene in scenes)
    out_path = os.path.join(out_dir, "full_audio.wav")
    
    # Generate the full audio
    generator = pipeline(full_narration, voice=VOICE)
    for _, _, audio in generator:
        sf.write(out_path, audio, 24000)
        break  # single-segment output

    # Save metadata for the next steps
    meta = {
        "full_audio": out_path,
        "full_narration": full_narration
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
        
    print(f"Full voiceover -> {out_path}")

if __name__ == "__main__":
    generate_all()