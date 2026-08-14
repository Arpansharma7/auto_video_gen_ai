"""
src/visuals/generate_images.py
Input: data/script.json -> Output: one image per scene using local Fooocus API
Requires: pip install gradio_client
Fooocus must be running in background (python entry_with_update.py --always-low-vram --listen)

FIX vs previous version:
- seed was hardcoded to the string "0" on every single call. With SDXL at
  "Speed" performance (low step count), seed dominates composition/pose/
  lighting far more than prompt text does - so every scene started from the
  exact same initial noise and landed on near-identical framing regardless
  of what the prompt said. That's why every image looked the same.
- Now a fresh random seed is generated per scene (still passed as a string,
  since that's what the Fooocus API expects), so composition actually
  varies scene to scene while the prompt still controls subject/content.
- Seed used is logged and written back into script.json per scene, so a
  specific image can be regenerated/reproduced later if you want that exact
  composition again.
"""
import json
import os
import time
import shutil
import glob
import random
from gradio_client import Client

FOOOCUS_URL = "http://127.0.0.1:7865/"

client = Client(FOOOCUS_URL)


def build_payload(prompt: str, seed: str):
    return [
        False, # 1 generate_image_grid_for_each_batch
        prompt, # 2 parameter_12 (Prompt)
        "", # 3 negative_prompt
        ["Fooocus V2", "Fooocus Masterpiece", "SAI Cinematic"], # 4 selected_styles (Cinematic & Masterpiece)
        "Speed", # 5 performance
        "832×1216", # 6 aspect_ratios (vertical 9:16)
        1, # 7 image_number
        "png", # 8 output_format
        seed, # 9 seed - randomized per scene, was hardcoded "0"
        False, # 10 read_wildcards_in_order
        2.0, # 11 image_sharpness
        4.0, # 12 guidance_scale
        "juggernautXL_v8Rundiffusion.safetensors", # 13 base_model
        "None", # 14 refiner
        0.5, # 15 refiner_switch
        True, "sd_xl_offset_example-lora_1.0.safetensors", 0.1, # 16-18 lora 1 (ENABLED as per your UI)
        False, "None", 0.0, # 19-21 lora 2
        False, "None", 0.0, # 22-24 lora 3
        False, "None", 0.0, # 25-27 lora 4
        False, "None", 0.0, # 28-30 lora 5
        False, "", # 31-32 input_image, parameter_212
        "Vary (Subtle)", # 33 upscale_or_variation
        None, # 34 image
        [], # 35 outpaint_direction
        None, # 36 image
        "", # 37 inpaint_additional_prompt
        None, # 38 mask_upload
        False, # 39 disable_preview
        False, # 40 disable_intermediate_results
        False, # 41 disable_seed_increment
        False, # 42 black_out_nsfw
        1.5, # 43 positive_adm
        1.5, # 44 negative_adm
        0.5, # 45 adm_end
        4.0, # 46 cfg_mimicking
        1, # 47 clip_skip
        "dpmpp_2m_sde_gpu", # 48 sampler
        "karras", # 49 scheduler
        "Default (model)", # 50 vae
        -1, -1, -1, -1, -1, -1, # 51-56 overwrites
        False, False, # 57-58 mixing
        False, False, # 59-60 debug, skip
        1, 255, # 61-62 canny
        "joint", # 63 refiner_swap
        0.25, # 64 softness
        False, 0.0, 0.0, 0.0, 0.0, # 65-69 controlnet 1
        False, # 70 debug_inpaint
        False, # 71 disable_initial
        "v2.5", # 72 inpaint_engine
        0.6, 0.3, # 73-74 inpaint_strength, field
        False, False, 0, # 75-77 masking
        False, False, "fooocus", # 78-80 metadata
        None, 0.5, 0.5, "Image", # 81-84 img prompt 1
        None, 0.5, 0.5, "Image", # 85-88 img prompt 2
        None, 0.5, 0.5, "Image", # 89-92 img prompt 3
        None, 0.5, 0.5, "Image", # 93-96 img prompt 4
        False, 0, False, # 97-99 grounding dino
        None, # 100 use_with_enhance_skips_image_generation
        False, "Vary (Subtle)", "First", "Original", # 101-104 enhance 1 setup
        False, "", "", "", "u2net", "full", "vit_b", 0.4, 0.3, 4, False, "v2.5", 0.6, 0.3, 0, False, # 105-120 enhance 1
        False, "", "", "", "u2net", "full", "vit_b", 0.4, 0.3, 4, False, "v2.5", 0.6, 0.3, 0, False, # 121-136 enhance 2
        False, "", "", "", "u2net", "full", "vit_b", 0.4, 0.3, 4, False, "v2.5", 0.6, 0.3, 0, False  # 137-152 enhance 3
    ]


def generate_image(prompt: str, out_path: str):
    seed = str(random.randint(0, 2**32 - 1))
    payload = build_payload(prompt, seed)

    outputs_dir = os.path.join("Fooocus", "outputs")
    existing_files = set(glob.glob(os.path.join(outputs_dir, "**", "*.png"), recursive=True))

    # Trigger generation (fn_index=67)
    client.predict(*payload, fn_index=67)

    # Fetch result (fn_index=68)
    # Gradio 4 throws a deserialization error on Gallery dicts, so we catch and ignore it.
    try:
        client.predict(fn_index=68)
    except Exception as e:
        print(f"Expected Gradio serialization error ignored: {e}")

    # Wait for the new image to appear on disk
    for _ in range(60):  # wait up to 60 seconds
        time.sleep(1)
        current_files = set(glob.glob(os.path.join(outputs_dir, "**", "*.png"), recursive=True))
        new_files = current_files - existing_files
        if new_files:
            time.sleep(0.5)  # ensure file is fully written
            new_image_path = list(new_files)[0]
            shutil.copy(new_image_path, out_path)
            return seed

    raise Exception("Timed out waiting for Fooocus image output.")


def generate_all(script_path="data/script.json", out_dir="data/images", limit=None):
    os.makedirs(out_dir, exist_ok=True)
    with open(script_path) as f:
        scenes = json.load(f)

    target_scenes = scenes[:limit] if limit else scenes
    for i, scene in enumerate(target_scenes):
        out_path = os.path.join(out_dir, f"scene_{i:02d}.png")
        try:
            seed = generate_image(scene["visual"], out_path)
            scene["image"] = out_path
            scene["seed"] = seed
            print(f"scene {i}: -> {out_path} (seed {seed})")
        except Exception as e:
            print(f"scene {i} FAILED: {e}")
            scene["image"] = None
        time.sleep(1)

    with open(script_path, "w") as f:
        json.dump(scenes, f, indent=2)


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    generate_all(limit=limit)