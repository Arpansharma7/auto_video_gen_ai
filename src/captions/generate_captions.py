"""
src/captions/generate_captions.py
Input: data/audio/meta.json + data/script.json -> Output: data/captions/full_captions.ass + data/captions/timings.json
Rewritten for absolute stability: no-gap chunks, better duration handling.
"""
import json
import os
import re
from faster_whisper import WhisperModel

WORDS_PER_CHUNK = 3  # Increased from 2 to 3 for better readability and less flashing
WHISPER_MODEL_SIZE = "small"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
    return _model

def fmt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

HEADER = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat ExtraBold,85,&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,80,80,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def _clean_word(word: str) -> str:
    return re.sub(r'[^\w\']', '', word).upper()

def generate_all(script_path="data/script.json", audio_meta_path="data/audio/meta.json", out_dir="data/captions"):
    os.makedirs(out_dir, exist_ok=True)
    
    with open(script_path) as f:
        scenes = json.load(f)
    with open(audio_meta_path) as f:
        meta = json.load(f)
        
    audio_path = meta["full_audio"]
    
    # 1. Transcribe and extract raw words
    model = _get_model()
    segments, _ = model.transcribe(audio_path, word_timestamps=True)
    
    raw_words = []
    for seg in segments:
        for w in seg.words:
            cleaned = _clean_word(w.word)
            if cleaned:
                raw_words.append({
                    "text": cleaned,
                    "start": float(w.start),
                    "end": float(w.end)
                })
                
    if not raw_words:
        print("Warning: Whisper detected no words.")
        with open(os.path.join(out_dir, "full_captions.ass"), "w", encoding="utf-8") as f:
            f.write(HEADER)
        return

    # 2. Build seamless no-gap chunks
    chunks = []
    for i in range(0, len(raw_words), WORDS_PER_CHUNK):
        chunk_words = raw_words[i:i + WORDS_PER_CHUNK]
        
        start = chunk_words[0]["start"]
        end = chunk_words[-1]["end"]
        
        # Seamless transition: NO GAPS between chunks to prevent blinking
        if i + WORDS_PER_CHUNK < len(raw_words):
            next_start = raw_words[i + WORDS_PER_CHUNK]["start"]
            
            # If TTS has a pause, keep text on screen until next word starts
            if end < next_start:
                end = next_start
            # If words overlap, clamp to next start
            else:
                end = next_start
                
        # Ensure minimum duration to prevent rapid flashing
        if end - start < 0.3:
            end = start + 0.3
            
        text = " ".join(w["text"] for w in chunk_words)
        chunks.append({"start": start, "end": end, "text": text})

    # 3. Generate ASS file (smoother pop animation)
    ass_path = os.path.join(out_dir, "full_captions.ass")
    events = []
    for chunk in chunks:
        # Slightly longer fade for smoother visual flow
        pop = r"{\fad(50,30)}"
        events.append(f"Dialogue: 0,{fmt_time(chunk['start'])},{fmt_time(chunk['end'])},Default,,0,0,0,,{pop}{chunk['text']}")
        
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(HEADER)
        f.write("\n".join(events))

    # 4. Calculate Scene Timings (for image crossfades)
    scene_timings = [0.0]
    current_word_idx = 0
    
    for i, scene in enumerate(scenes):
        scene_word_count = len(scene["narration"].split())
        next_scene_start_idx = current_word_idx + scene_word_count
        
        if i < len(scenes) - 1:
            if next_scene_start_idx < len(raw_words):
                start_time = raw_words[next_scene_start_idx]["start"]
                scene_timings.append(start_time)
            else:
                scene_timings.append(raw_words[-1]["end"])
                
        current_word_idx = next_scene_start_idx
        
    timings_path = os.path.join(out_dir, "timings.json")
    with open(timings_path, "w") as f:
        json.dump(scene_timings, f, indent=2)
        
    print(f"Captions -> {ass_path}")
    print(f"Scene Timings -> {timings_path}")

if __name__ == "__main__":
    generate_all()