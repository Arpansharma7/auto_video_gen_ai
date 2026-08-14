# run_pipeline.ps1 - runs the full video pipeline directly, no Hermes overhead
param([string]$Topic)

python src\script\generate_script.py "$Topic"
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: script generation"; exit 1 }

python src\visuals\generate_images.py
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: image generation"; exit 1 }

python src\audio\generate_voiceover.py
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: voiceover generation"; exit 1 }

python src\captions\generate_captions.py
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: caption generation"; exit 1 }

python src\assemble\assemble_video.py
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: assembly"; exit 1 }

python src\assemble\add_music.py "$Topic"
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: music"; exit 1 }

python upload_youtube.py
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: youtube upload"; exit 1 }

Write-Host "Pipeline complete. Video uploaded to YouTube."