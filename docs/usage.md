# Usage

## Command line

```bash
unfaded restore scan.jpg                 # split, tone, repair, faces
unfaded restore album/ -o restored/      # a whole folder
unfaded restore scan.jpg --colorize --scale 2 --explain
unfaded split scan.jpg                   # only cut the scan into prints
unfaded serve                            # local web interface on http://127.0.0.1:8765
unfaded bench                            # quality and timing on synthetic damage
unfaded models --fetch                   # download all weights now
```

For every input `unfaded restore` writes `name.unfaded.jpg` (or `name.unfaded-1.jpg`, `-2.jpg` when a scan holds several prints) and a `.xmp` sidecar next to it, or into `-o`. The original is never opened for writing.

| Option | Meaning |
| --- | --- |
| `-o, --output DIR` | Where results go. Default: next to each input. |
| `--format jpg\|png` | Output format. |
| `--face-strength 0..100` | How far each face moves from the original toward the GFPGAN output. Default 35. |
| `--colorize` | Add the DDColor step. It only acts on black and white prints. |
| `--color-strength 0..100` | Blend of the predicted colour. |
| `--scale 1\|2\|4` | Real-ESRGAN upscale. 1 means off. `--enable upscale` alone means 2. |
| `--skip STEP` | Turn off split, fade, repair or faces. Repeatable. |
| `--enable STEP` | Turn on color or upscale. Repeatable. |
| `--force-fade` | Run tone recovery even when the print already uses most of the tonal range. |
| `--device` | `auto`, `cuda`, `cpu` or `mps`. |
| `--explain` | Print how much each step changed and how long it took. |

## What the steps do and when they stay out of the way

1. **split** finds prints on a flatbed scan and straightens them. If the whole image is one print, nothing is cut.
2. **fade** stretches levels and removes a colour cast. It is skipped when the print already uses 80 percent or more of the tonal range, unless `--force-fade` is given. Black and white prints stay neutral grey.
3. **repair** detects scratches, creases and dust, then fills the mask with LaMa. If the mask would cover more than 15 percent of the print, the step is skipped and says so, because a mask that large is almost always a false detection on texture.
4. **faces** restores each detected face with GFPGAN and blends it back by the strength you chose.
5. **color** (optional) predicts colour for grayscale prints. Lightness is never changed.
6. **upscale** (optional) enlarges by 2 or 4. The output is capped at 120 megapixels.

## Web interface

`unfaded serve` starts a server that only accepts requests from its own origin. Open the address it prints.

1. Drop a scan. Detected outlines appear on the scan. Drag a corner to fix one, add or delete outlines, rotate a print by quarter turns.
2. Pick steps and strengths, then press **Restore**.
3. Use the step chips under the result to see any single step. The slider compares before and after. **What changed** paints where the step moved pixels. **Invented** paints what a model generated rather than recovered.
4. **Edit damage mask** lets you paint the damage yourself. Your mask replaces the detector for that print on the next run.
5. Faces each have their own strength slider. Download one print or a zip with sidecars.

The language switcher offers English, Traditional Chinese, Simplified Chinese, Japanese, Korean, Spanish, French, German and Brazilian Portuguese. The theme follows the system and can be toggled.

## Sidecar files

The `.xmp` next to each result records the Unfaded version, the sha256 of the source scan, every step with its model and parameters, and which steps produced pixels that a model generated. It is a plain XMP packet, so Lightroom, digiKam and exiftool can read it.

## Python

```python
from unfaded import imaging
from unfaded.pipeline import Options, Pipeline

pipe = Pipeline("auto")
run = pipe.run(imaging.load_rgb("scan.jpg"), Options(steps=("split", "fade", "repair", "faces"), face_strength=35))
for photo in run.photos:
    imaging.save(f"print-{photo.index + 1}.jpg", photo.final)
    for step in photo.steps:
        print(step.name, step.model, f"{step.changed_percent:.1f}% changed", step.note)
```
