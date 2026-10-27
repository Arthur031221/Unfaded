<div align="center">

<img src="assets/logo.svg" width="96" alt="Unfaded logo">

# Unfaded

**在自己的 GPU 上修復老家庭照片，並看清楚每一步改了什麼。**

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml/badge.svg)](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/install.md)

</div>

我用固定亂數種子在四張公有領域照片上畫出刮痕，修復步驟把平均 PSNR 從 26.8 dB 提高到 31.0 dB，切圖步驟在合成掃描圖上找到 12 個照片中的 12 個，平均重疊率（IoU）為 0.95。四張照片的 PSNR 都有提高。執行 `unfaded bench` 就能重現，方法寫在下面的「基準測試」。

![Unfaded 從掃描圖切出四張照片、修復它們並顯示每一步的改動](assets/demo.gif)

[線上展示](https://arthur031221.github.io/Unfaded/)使用三張範例掃描圖的真實輸出。它無法處理你自己的檔案，要處理自己的照片請安裝工具。

## 修復前後

| | 修復前 | 修復後 |
| --- | --- | --- |
| 有摺痕的家庭合照，1891 | ![修復前](assets/creased-before.jpg) | ![修復後](assets/creased-after.jpg) |
| 伐木營地，1926 | ![修復前](assets/camp-before.jpg) | ![修復後](assets/camp-after.jpg) |

兩張都是公有領域的掃描圖，刮痕、摺痕與灰塵是 `scripts/make_demo.py` 合成加上去的。修復後是預設流程：切圖、色調、修復、人臉（強度 35%）。偵測器也會在反相影像上再跑一次，深色刮痕就是這樣找到的，但仍會漏掉一些細的深色線條，見「限制」。

模型會編造內容，所以我讓工具明講。凡是畫出新像素的步驟都標示「由模型生成」，「生成」檢視會精確塗出位置，原始檔案絕不會被改動。

## 它做什麼

Unfaded 是一條很短的流程。每一步都可以關掉，每一步都會回報它改了照片的多少比例。

| 步驟 | 做什麼 | 模型 | 預設 |
| --- | --- | --- | --- |
| 切圖 | 從平板掃描圖中切出每張照片並拉正。可以手動拖曳角點。 | OpenCV，無模型 | 開 |
| 褪色 | 還原色階並移除偏色。照片已涵蓋 80% 色調範圍時會跳過。 | 無 | 開 |
| 修復 | 找出刮痕、摺痕與灰塵再填補。若要填補的面積超過照片 15% 就跳過。可以自己塗遮罩。 | 舊照片刮痕偵測器、LaMa | 開 |
| 人臉 | 逐張修復人臉，每張臉有自己的強度滑桿。0 保留原本的臉，100 採用 GFPGAN 畫出的結果。 | YuNet、GFPGAN v1.4 | 開，35 |
| 上色 | 為黑白照片預測顏色，亮度不會改變。 | DDColor | 關 |
| 放大 | 放大 2 倍或 4 倍，大張照片會分塊處理。 | Real-ESRGAN x4plus | 關 |

每個結果都附一個 `.xmp` 側檔，記錄來源檔案的 sha256、每一步使用的模型與設定，以及模型生成像素的步驟。

## 安裝

需要 Python 3.10 以上。模型權重共約 1.3 GB，第一次使用時下載，並以固定的 sha256 驗證。之後不會有任何資料離開你的電腦。

<details>
<summary>Linux 搭配 NVIDIA GPU（已測試）</summary>

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
unfaded models --fetch
```

我在 RTX 5090、torch 2.11、CUDA 12.8 上開發。

</details>

<details>
<summary>沒有 GPU 的電腦</summary>

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
unfaded restore scan.jpg --device cpu
```

可以執行但很慢，請見下方計時。

</details>

<details>
<summary>macOS 與 Windows（未測試）</summary>

程式碼沒有平台專屬的部分，所以 `pip install -e .` 應該能用，但我沒有在這兩個系統上跑過。Mac 可以試 `--device mps`，`auto` 只會選 CUDA 或 CPU。

</details>

更多內容見 [docs/install.md](docs/install.md)。

## 使用

```bash
unfaded restore examples/scans/album-damaged.jpg -o restored --explain
```

這是我製作展示時執行的指令。它在掃描圖中找到四張照片，並寫出 `album-damaged.unfaded-1.jpg` 到 `-4.jpg`，各附一個側檔。在 RTX 5090 上含載入模型共花 12 秒。`--explain` 會顯示每一步做了什麼：

```
album-damaged.jpg: 4 prints
  wrote restored/album-damaged.unfaded-1.jpg
    fade              skipped   0.01s  the print already uses 92% of the tonal range
    repair       4.0% changed   5.93s
    faces        1.2% changed   1.15s
```

更多選項：

```bash
unfaded restore album/ -o restored/            # 整個資料夾
unfaded restore scan.jpg --colorize --scale 2  # 上色並放大
unfaded restore scan.jpg --face-strength 60    # 更強的人臉修復
unfaded split scan.jpg                         # 只切出照片
unfaded serve                                  # 本機網頁介面，位於 127.0.0.1:8765
```

網頁介面會顯示找到的輪廓、讓你修正輪廓、執行流程，接著讓你逐步檢視結果：前後對比滑桿、改動熱度圖、「生成」檢視、遮罩編輯器，以及每張臉各自的強度滑桿。它有淺色與深色主題、可在手機上使用，並提供英文、繁體中文、簡體中文、日文、韓文、西班牙文、法文、德文與巴西葡萄牙文。完整說明：[docs/usage.md](docs/usage.md)、[docs/configuration.md](docs/configuration.md)。

## 基準測試

`unfaded bench` 會執行以下所有項目，種子為 5。我這次執行的原始輸出在 [docs/benchmark.json](docs/benchmark.json)。

**修復。** `examples/photos` 中的四張照片視為乾淨的參考。每張縮到 1600 像素，畫上已知遮罩的刮痕、摺痕與灰塵，只執行修復步驟，再以乾淨影像計算 PSNR。

| 照片 | 損壞後 PSNR | 修復後 PSNR | 損壞後 SSIM | 修復後 SSIM |
| --- | --- | --- | --- | --- |
| 伐木營地 | 24.90 | 25.65 | 0.954 | 0.943 |
| King 家族 | 28.22 | 38.88 | 0.971 | 0.988 |
| Knowles 家族 | 26.96 | 27.98 | 0.975 | 0.965 |
| Roy 家族 | 27.01 | 31.68 | 0.969 | 0.982 |
| 平均 | 26.77 | 31.05 | 0.967 | 0.970 |

四張照片的 PSNR 都變好，SSIM 變好的有兩張。在伐木營地和 Knowles 的照片上，偵測器把部分紋理當成損壞，填補後 SSIM 略為下降。SSIM 的平均提升只有 0.003。深色刮痕是把偵測器跑在反相影像上、分數打五折找到的。這個權重是我用同一個種子挑的，在種子 11 和 23 上，平均 PSNR 比先前只跑一次的偵測器多 0.9 dB 和 0.2 dB。所有數字都是在我自己畫的損壞上量到的，比真實的磨損容易，所以請把它當成回歸檢查，而不是對你照片的保證。

**切圖。** 把範例照片四張一組、以隨機角度放在三種背景上。12 張全部找到，平均 IoU 0.952，最差 0.931。

**速度。** 每個裝置暖機後跑一次，除了切圖之外全部步驟開啟，色調還原強制執行，放大 2 倍。

| 裝置 | 影像大小 | fade | repair | faces | 上色 | 放大 | 總計 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 5090 | 960 x 1200 | 0.07 s | 0.40 s | 0.22 s | 0.06 s | 1.51 s | 2.26 s |
| Ryzen 5 7500F, CPU | 480 x 600 | 0.02 s | 9.26 s | 12.32 s | 1.87 s | 81.80 s | 105.27 s |

CPU 那一列使用較小的影像，因為完整尺寸要等太久，所以兩列不能直接比較。不放大（預設就是關閉）的話，CPU 約 22 秒。

## 限制

- 刮痕偵測器主要用淺色刮痕訓練。深色刮痕是把它跑在反相影像上、分數打五折才找到的，所以細的深色線條還是比淺色的更常被漏掉。請在遮罩編輯器中自己塗。
- 在有紋理或髒污的區域，偵測器會誤判，伐木營地和 Knowles 的照片就是這樣讓 SSIM 下降的。15% 的保護只擋得住最嚴重的情況。
- GFPGAN 是畫出人臉。強度 100 時，臉可能看起來像另一個人。預設值因此是 35，「生成」檢視會顯示它動過哪裡。
- DDColor 是猜顏色，而且偏暖。請把上色結果當成插圖。
- 色調還原會讓褐色調的照片變成中性灰。
- 切圖用的是傳統影像處理。白色邊框的照片放在白色掃描蓋板上可能切錯，請拖曳角點修正輪廓。
- 線上展示是預先算好的輸出重播，只有人臉與上色滑桿會有反應。

## 與其他工具比較

Bringing Old Photos Back to Life、GFPGAN、LaMa 與 Real-ESRGAN 是這裡真正幹活的模型，它們各自是獨立的研究專案，有自己的指令列。Unfaded 沒有改進其中任何一個。它新增的是組裝：一個指令處理整張掃描、對會造成傷害的步驟設定跳過規則、逐步的改動檢視，以及模型生成內容的紀錄。

## 專案結構

```
src/unfaded/        流程、每一步一個模組、伺服器、基準測試
src/unfaded/web/    介面與 9 個語言檔
demo/               GitHub Pages 展示用的預先輸出
examples/           公有領域照片與損壞掃描圖，附來源
docs/               安裝、使用、設定、架構
tests/              單元測試、瀏覽器測試、需要權重的端對端測試
```

設計說明在 [docs/architecture.md](docs/architecture.md)，貢獻規則在 [CONTRIBUTING.md](CONTRIBUTING.md)，模型授權在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 授權

MIT。模型權重保留各自的授權，列在聲明檔中。

Assisted by Claude/Codex.
