---
name: hermes-video-pipeline
description: Generate short-form 9:16 videos from a topic via the Hermes automated pipeline - script, images, voiceover, captions, assembly, music
---

# Hermes Video Pipeline

Local automated 9:16 short video pipeline, root at `d:/01_DEV/02_projects/09_video_gen/`. Orchestrated end-to-end by `run_pipeline.ps1` — a single run takes 15+ minutes and covers all 6 stages. Never drive this pipeline stage-by-stage from the agent; that is what burns tokens.

## Workflow

When given a topic:

1. Launch the orchestrator once:
   ```
   pwsh -File run_pipeline.ps1 -Topic "<topic>"
   ```
2. Block until it exits. Do not poll `data/images/`, `data/audio/`, `data/captions/`, or `data/output/` mid-run. Do not tail logs in a loop. Do not run any individual stage script while the orchestrator is active.
3. On exit:
   - **Exit 0** → report the final file path under `D:\04_downloads\outs\<topic>_<timestamp>.mp4` to the user. STOP. Never auto-upload.
   - **Non-zero** → read only the last ~30 lines of output/stderr, identify the failing stage, report the exact error. STOP. Do not retry, do not re-run earlier stages, do not re-run the full orchestrator.

## Token discipline (hard rules)

- One tool call to launch the pipeline. No pre-flight checks (`.env`, file existence, Fooocus/Gemini reachability) unless a run has actually failed.
- Never watch/poll status in a loop — the orchestrator blocks and returns; just wait on it.
- Never re-open `script.json` or scan output folders "just to confirm" — only inspect on failure, and only the specific stage that failed.
- On failure, if the user asks for a fix-and-continue, re-run only that one stage's script directly (see reference below), not the whole pipeline.
- Never auto-upload. Stop after reporting the output path.

## Stage reference (touch individually only on failure)

1. **Script** — `src/script/generate_script.py`, `gemini-3.5-flash` via `limiter.py` (rate limit + model fallback) → `data/script.json`
2. **Images** — `src/visuals/generate_images.py`, local Fooocus API (`:7865`), `gradio_client` `fn_index=67`; polls `Fooocus/outputs/` for new PNGs (fn_index=68 gallery deserialization is broken on Gradio 4, so the API response itself is ignored) → `data/images/`. Styles: `Fooocus V2`, `Fooocus Photograph`, no hardcoded prompt prefix/suffix. Model: `juggernautXL_v8Rundiffusion.safetensors`, 832x1216.
3. **Voiceover** — `src/audio/generate_voiceover.py`, Kokoro TTS, voice `am_puck`, requires `espeak-ng` on PATH → `data/audio/` (24kHz WAV)
4. **Captions** — `src/captions/generate_captions.py`, 3-word chunks, pop/scale `\fad(80,80)\t(...)` animation, timed via ffprobe → `data/captions/` (.ass)
5. **Assembly** — `src/assemble/assemble_video.py`, FFmpeg `zoompan` Ken Burns (pre-scaled `2160:3840` to avoid pixelation), captions burned in, 0.5s `xfade`/`acrossfade` crossfades between scenes → `data/output/`
6. **Music** — `src/assemble/add_music.py`, random track + random start offset from `data/music/`, `amix`, `MUSIC_VOLUME=0.14`, `VOICE_BOOST=2.0` → `D:\04_downloads\outs\<topic>_<timestamp>.mp4`

`data/script.json` is the shared state contract across all stages (narration, visual, image, audio, caption per scene).

## Failure handling

- Gemini 429 quota → STOP, tell the user, do not proceed on stale `script.json`.
- Fooocus unreachable → confirm it's running headless on `:7865` (`python entry_with_update.py --always-low-vram --listen`); no filesystem poll is possible without it.
- Voiceover fails → check `espeak-ng` is installed system-wide (separate from the `kokoro` pip package).
- "No music tracks found" → tell the user to add `.mp3`/`.wav` files to `data/music/`.
- `data/` must exist at project root before any run.