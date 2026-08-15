# Auto Video Gen AI

Auto Video Gen AI is an end-to-end pipeline that converts a topic into a complete short-form vertical video using AI-generated scripts, visuals, voiceovers, captions, and background music.

The system is designed for TikTok, Instagram Reels, YouTube Shorts, and other 9:16 video platforms.

## Features

- AI-generated storytelling scripts using Gemini
- Scene-by-scene image generation
- Automatic voiceover generation
- Animated subtitle generation
- FFmpeg-based video assembly
- Background music mixing
- Fully automated pipeline
- Vertical 9:16 output format

## Pipeline

```text
Topic
  │
  ▼
Script Generation
  │
  ▼
Image Generation
  │
  ▼
Voiceover Generation
  │
  ▼
Caption Generation
  │
  ▼
Video Assembly
  │
  ▼
Music Mixing
  │
  ▼
Final MP4 Video
```

## Project Structure

```text
src/
├── script/
│   └── generate_script.py
├── visuals/
│   └── generate_images.py
├── audio/
│   └── generate_voiceover.py
├── captions/
│   └── generate_captions.py
└── assemble/
    ├── assemble_video.py
    └── add_music.py

assets/
requirements.txt
limiter.py
upload_youtube.py
```

## Workflow

### 1. Script Generation

Creates a structured short-form narrative from a topic using Gemini.

Output:

```text
data/script.json
```

### 2. Image Generation

Generates scene visuals using a local Fooocus instance.

Output:

```text
data/images/
```

### 3. Voiceover Generation

Creates narration audio using TTS.

Output:

```text
data/audio/
```

### 4. Caption Generation

Creates animated ASS subtitles synchronized with narration.

Output:

```text
data/captions/
```

### 5. Video Assembly

Combines images, narration, transitions, and subtitles using FFmpeg.

Output:

```text
data/output/
```

### 6. Music Mixing

Adds background music and balances audio levels.

Output:

```text
Final MP4 video
```

## Installation

Clone the repository:

```bash
git clone https://github.com/Arpansharma7/auto_video_gen_ai.git
```

Create a virtual environment

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
HF_TOKEN=your_huggingface_token
```

## Requirements

- Python 3.10+
- FFmpeg
- Google Gemini API Key
- Fooocus 
- Hugging Face Access Token
- espeak-ng (for TTS)


## Future Improvements

- Automatic YouTube upload
- Multi-language support
- Multiple voice options
- Multiple video styles
- Batch video generation
- Web dashboard

## Author

Arpan Sharma

LinkedIn: https://www.linkedin.com/in/arpan-sharma-aiml/

