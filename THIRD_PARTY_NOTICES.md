# Third party notices

Unfaded is MIT licensed. It does not ship any model weights. The weights listed below are downloaded
on demand from the sources named in `src/unfaded/models.py`, each pinned by sha256. Each model keeps its
own license, which applies to the weights you download.

Network definitions that were copied or adapted into `src/unfaded/vendor` keep their original license text
next to the code.

| Component | Used for | License | Source |
| --- | --- | --- | --- |
| Bringing Old Photos Back to Life | scratch and crease detector (network and weights) | MIT | microsoft/Bringing-Old-Photos-Back-to-Life |
| LaMa (big-lama, TorchScript export) | inpainting of the damage mask | Apache-2.0 | advimman/lama |
| YuNet | face detection and five landmarks | MIT | opencv/opencv_zoo |
| GFPGAN v1.4 | face restoration | Apache-2.0 | TencentARC/GFPGAN |
| DDColor (paper tiny) | colorization | Apache-2.0 | piddnad/DDColor |
| Real-ESRGAN x4plus | upscaling | BSD-3-Clause | xinntao/Real-ESRGAN |
| BasicSR (building blocks used by GFPGAN and Real-ESRGAN) | helper layers in `vendor/arch_util.py` | Apache-2.0 | XPixelGroup/BasicSR |

The example photos in `examples/photos` are public domain or carry no known restrictions. Their sources are in
`examples/SOURCES.md`.
