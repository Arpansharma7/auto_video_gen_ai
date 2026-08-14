"""
src/assemble/assemble_video.py
Input: data/script.json + data/audio/meta.json + data/captions/timings.json
Output: data/output/final_video.mp4
Requires ffmpeg installed and on PATH.

Features:
- Single continuous audio track (no more inconsistent TTS pacing).
- Images are crossfaded based on exact Whisper scene timings.
- Synthesized whoosh SFX layered on every image cut.
- Subtitles burned in.
"""
import json
import subprocess
import os

FADE_DURATION = 0.5
SFX_PATH = "assets/whoosh.wav"

def ensure_transition_sfx(path: str = SFX_PATH) -> str:
    """Generate a short filtered-noise whoosh/impact once and reuse it."""
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "anoisesrc=color=pink:duration=0.4:sample_rate=48000",
        "-af", "highpass=f=300,lowpass=f=6000,"
               "afade=t=in:d=0.04,afade=t=out:st=0.22:d=0.18,volume=0.45",
        path,
    ], check=True)
    return path

def assemble(script_path="data/script.json", audio_meta_path="data/audio/meta.json", timings_path="data/captions/timings.json", out_dir="data/output"):
    os.makedirs(out_dir, exist_ok=True)
    
    with open(script_path) as f:
        scenes = json.load(f)
    with open(audio_meta_path) as f:
        meta = json.load(f)
    with open(timings_path) as f:
        scene_timings = json.load(f)
        
    audio_path = meta["full_audio"]
    ass_path = os.path.join("data", "captions", "full_captions.ass").replace("\\", "/")
    caption_escaped = ass_path.replace(":", "\\:")
    
    # Build inputs array: [img0, img1, img2, img3, full_audio, whoosh1, whoosh2, whoosh3]
    inputs = []
    valid_scenes = [s for s in scenes if s.get("image")]
    
    for scene in valid_scenes:
        inputs.extend(["-loop", "1", "-i", scene["image"]])
        
    inputs.extend(["-i", audio_path])
    
    sfx_path = ensure_transition_sfx()
    num_transitions = len(valid_scenes) - 1
    for _ in range(num_transitions):
        inputs.extend(["-i", sfx_path])
        
    filter_complex = ""
    
    # 1. Scale and crop all images
    for i in range(len(valid_scenes)):
        filter_complex += f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v{i}];"
        
    # 2. Chain video xfades based on scene timings
    current_v = "v0"
    transition_offsets = []
    for i in range(1, len(valid_scenes)):
        offset = scene_timings[i] - FADE_DURATION
        transition_offsets.append(offset)
        out_v = f"x{i}"
        filter_complex += f"[{current_v}][v{i}]xfade=transition=fade:duration={FADE_DURATION}:offset={offset}[{out_v}];"
        current_v = out_v
        
    # 3. Add subtitles to the final video stream
    filter_complex += f"[{current_v}]subtitles='{caption_escaped}'[vout];"
    
    # 4. Process audio: delay whooshes and mix them into the main audio track
    audio_idx = len(valid_scenes)
    sfx_input_start = audio_idx + 1
    
    sfx_labels = []
    for idx, t_offset in enumerate(transition_offsets):
        sfx_idx = sfx_input_start + idx
        delay_ms = max(0, int(t_offset * 1000))
        label = f"sfx{idx}"
        filter_complex += f"[{sfx_idx}:a]adelay={delay_ms}:all=1[{label}];"
        sfx_labels.append(f"[{label}]")
        
    mix_inputs = f"[{audio_idx}:a]" + "".join(sfx_labels)
    filter_complex += f"{mix_inputs}amix=inputs={1 + len(sfx_labels)}:normalize=0[aout]"
    
    final_path = os.path.join(out_dir, "final_video.mp4")
    
    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        "-shortest",
        final_path
    ], check=True)
    
    print(f"Final video -> {final_path}")
    return final_path

if __name__ == "__main__":
    assemble()