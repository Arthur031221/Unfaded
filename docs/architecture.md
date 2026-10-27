# Architecture

Unfaded is a short pipeline of independent steps. Each step takes an RGB `uint8` array and returns a `StepResult` that carries the image, a per pixel change map and, when a model drew pixels, an invented map. The command line, the web server and the benchmark all call the same `Pipeline.run`.

```
scan > split > fade > repair > faces > color > upscale > result + XMP sidecar
       |              |         |       |        |
       per print   scratch    YuNet  DDColor  Real-ESRGAN
                   detector   GFPGAN (chroma
                   + LaMa     per face only)
```

## Modules

| Module | Role |
| --- | --- |
| `pipeline.py` | `Options`, `Pipeline.run`, the step functions, a memo cache keyed by a hash of the pixels and the settings. |
| `split.py` | Classical print detection: background estimate in Lab, colour distance plus a Sobel edge cue for white borders, connected components, `minAreaRect`, perspective warp. |
| `fade.py` | Percentile levels, cast removal, saturation recovery. No model. |
| `scratch.py` | The Microsoft old photo detector (a UNet) run at two scales, thresholded into a damage mask. |
| `inpaint.py` | LaMa (TorchScript) on windows around each damaged region, so a large print never needs a full size pass. |
| `faces.py` | YuNet finds faces and five landmarks. Each face is aligned to the 512 pixel GFPGAN template, restored, mixed with the original crop by the strength and pasted back through a feathered ellipse. |
| `colorize.py` | DDColor predicts chroma at 512 pixels. Only the a and b channels are taken, so lightness stays the scan's. |
| `upscale.py` | Real-ESRGAN x4plus with overlapping, feathered tiles, resized to 2x when asked. |
| `changes.py` | Lab colour difference between a step's input and output, a heat overlay, a changed percentage. |
| `provenance.py` | The XMP sidecar with the source hash, the steps and the model generated list. |
| `models.py` | Registry of weights with size, license, source and sha256. Downloads to a `.part` file, verifies, then renames. |
| `vendor/` | Network definitions copied in so the install does not depend on basicsr, gfpgan, facexlib or realesrgan. Each folder keeps its license. |
| `server.py` | FastAPI app, in memory sessions, a progress endpoint and image routes. |
| `web/` | Vanilla JavaScript interface, nine locale files, no build step. |
| `bench.py`, `synth.py` | Synthetic scans and damage with fixed seeds, quality metrics, timing. |

## Decisions

**Why classical splitting.** A flatbed scan has a flat, bright background. A background model plus edge cues finds prints quickly, runs anywhere, and the failure modes are visible, so the interface lets the user drag corners. A learned detector would add a download and hide its mistakes.

**Why the pipeline skips things.** Every model step can make a print worse. Tone recovery is skipped on prints that already use most of the range. Repair is skipped when the detector marks more than 15 percent of the print, because that means it is reading texture as damage. Colour is only applied to grayscale prints. Each skip is reported with a code and a note instead of being silent.

**Honest change maps.** A step's output is compared with its own input in Lab space, so the heat view shows what that step did and nothing else. Steps that draw pixels (repair, faces, color, upscale) also return an invented weight. The face weight follows the strength slider and the feathered pasting mask.

**Original untouched.** Output is always a new file. A sidecar stores the sha256 of the scan, so a restored copy can be traced back to the exact file it came from.

**Weights.** Nothing is shipped. Every file has a pinned sha256 that is checked at download and again the first time a cached file is used, and is remembered until the file changes. Plain checkpoints load with `torch.load(..., weights_only=True)`. The LaMa file is TorchScript, which can hold code, so for that one the checksum is the only protection.

**Memoisation.** The web interface runs the same print many times while sliders move. `Pipeline` keeps up to 48 step results keyed by a digest of the input pixels and the step settings, so changing the face strength does not rerun the scratch detector.

## Web interface and demo

The interface talks to one of two backends in `web/backend.js`. `LiveBackend` calls the local server. `DemoBackend` reads `demo/index.json` and the images next to it, which `scripts/make_demo.py` renders with the real pipeline. The GitHub Pages site is the same interface with the demo backend, so it shows genuine output but cannot process new files. In demo mode the face slider cross fades between the repaired print and a full strength render, which is the same linear blend the pipeline applies, up to JPEG rounding.

## Benchmark method

`unfaded bench` takes the bundled clean photos, fits each to 1600 pixels, draws a known mask of scratches, creases and dust with a fixed seed, runs only the repair step and compares with the clean image using PSNR and SSIM, over the whole print and over the damaged region. The split score composes the example prints onto three scan backgrounds at random angles and measures the intersection over union of each found quad against the true corners. Timing runs every step once to warm up, clears the cache, then runs again.
