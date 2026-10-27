<div align="center">

<img src="assets/logo.svg" width="96" alt="Unfaded logo">

# Unfaded

**在自己的 GPU 上修复老家庭照片，并看清每一步改了什么。**

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml/badge.svg)](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/install.md)

</div>

我用固定随机种子在四张公有领域照片上画出划痕，修复步骤把平均 PSNR 从 26.8 dB 提高到 29.0 dB，切图步骤在合成扫描图上找到 12 张照片中的 12 张，平均重叠率（IoU）为 0.95。四张照片中有一张的 PSNR 略微变差。运行 `unfaded bench` 即可复现，方法写在下面的「基准测试」。

![Unfaded 从扫描图中切出四张照片、修复它们并显示每一步的改动](assets/demo.gif)

[在线演示](https://arthur031221.github.io/Unfaded/)使用三张示例扫描图的真实输出。它无法处理你自己的文件，要处理自己的照片请安装工具。

## 修复前后

| | 修复前 | 修复后 |
| --- | --- | --- |
| 有折痕的家庭合影，1891 | ![修复前](assets/creased-before.jpg) | ![修复后](assets/creased-after.jpg) |
| 伐木营地，1926 | ![修复前](assets/camp-before.jpg) | ![修复后](assets/camp-after.jpg) |

两张都是公有领域的扫描图，划痕、折痕和灰尘由 `scripts/make_demo.py` 合成添加。修复后是默认流程：切图、色调、修复、人脸（强度 35%）。第一行中的深色划痕仍然留着。检测器对白色划痕效果不错，对细的深色线条效果差，见「局限」。

模型会编造内容，所以我让工具明确说出来。凡是画出新像素的步骤都标注「由模型生成」，「生成」视图会精确涂出位置，原始文件绝不会被改动。

## 它做什么

Unfaded 是一条很短的流程。每一步都可以关掉，每一步都会报告它改动了照片的多大比例。

| 步骤 | 做什么 | 模型 | 默认 |
| --- | --- | --- | --- |
| 切图 | 从平板扫描图中切出每张照片并摆正。可以手动拖动角点。 | OpenCV，无模型 | 开 |
| 褪色 | 还原色阶并去除偏色。照片已经覆盖 80% 的色调范围时会跳过。 | 无 | 开 |
| 修复 | 找出划痕、折痕和灰尘再填补。如果要填补的面积超过照片的 15% 就跳过。可以自己涂蒙版。 | 旧照片划痕检测器、LaMa | 开 |
| 人脸 | 逐张修复人脸，每张脸有自己的强度滑块。0 保留原来的脸，100 采用 GFPGAN 画出的结果。 | YuNet、GFPGAN v1.4 | 开，35 |
| 上色 | 为黑白照片预测颜色，亮度不会改变。 | DDColor | 关 |
| 放大 | 放大 2 倍或 4 倍，大幅照片会分块处理。 | Real-ESRGAN x4plus | 关 |

每个结果都附一个 `.xmp` 旁注文件，记录源文件的 sha256、每一步使用的模型和设置，以及模型生成像素的步骤。

## 安装

需要 Python 3.10 或更高版本。模型权重共约 1.3 GB，首次使用时下载，并用固定的 sha256 校验。之后不会有任何数据离开你的电脑。

<details>
<summary>Linux 搭配 NVIDIA GPU（已测试）</summary>

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
unfaded models --fetch
```

我在 RTX 5090、torch 2.11、CUDA 12.8 上开发。

</details>

<details>
<summary>没有 GPU 的电脑</summary>

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
unfaded restore scan.jpg --device cpu
```

可以运行但很慢，见下方计时。

</details>

<details>
<summary>macOS 和 Windows（未测试）</summary>

代码里没有平台专属的部分，所以 `pip install -e .` 应该可用，但我没有在这两个系统上跑过。Mac 上可以试 `--device mps`，`auto` 只会选 CUDA 或 CPU。

</details>

更多内容见 [docs/install.md](docs/install.md)。

## 使用

```bash
unfaded restore examples/scans/album-damaged.jpg -o restored --explain
```

这是我制作演示时运行的命令。它在扫描图中找到四张照片，并写出 `album-damaged.unfaded-1.jpg` 到 `-4.jpg`，各附一个旁注文件。在 RTX 5090 上含模型加载共用 12 秒。`--explain` 会显示每一步做了什么：

```
album-damaged.jpg: 4 prints
  wrote restored/album-damaged.unfaded-1.jpg
    fade              skipped   0.01s  the print already uses 92% of the tonal range
    repair       4.0% changed   5.93s
    faces        1.2% changed   1.15s
```

更多选项：

```bash
unfaded restore album/ -o restored/            # 整个文件夹
unfaded restore scan.jpg --colorize --scale 2  # 上色并放大
unfaded restore scan.jpg --face-strength 60    # 更强的人脸修复
unfaded split scan.jpg                         # 只切出照片
unfaded serve                                  # 本地网页界面，位于 127.0.0.1:8765
```

网页界面会显示找到的轮廓、让你修正轮廓、运行流程，然后让你逐步查看结果：前后对比滑块、改动热力图、「生成」视图、蒙版编辑器，以及每张脸各自的强度滑块。它有浅色和深色主题，可在手机上使用，并提供英文、繁体中文、简体中文、日文、韩文、西班牙文、法文、德文和巴西葡萄牙文。完整说明：[docs/usage.md](docs/usage.md)、[docs/configuration.md](docs/configuration.md)。

## 基准测试

`unfaded bench` 会运行下面所有项目，种子为 5。我这次运行的原始输出在 [docs/benchmark.json](docs/benchmark.json)。

**修复。** `examples/photos` 中的四张照片视为干净的参照。每张缩到 1600 像素，画上已知蒙版的划痕、折痕和灰尘，只运行修复步骤，再用干净图像计算 PSNR。

| 照片 | 损坏后 PSNR | 修复后 PSNR | 损坏后 SSIM | 修复后 SSIM |
| --- | --- | --- | --- | --- |
| 伐木营地 | 24.90 | 25.57 | 0.954 | 0.948 |
| King 家族 | 28.22 | 32.53 | 0.971 | 0.984 |
| Knowles 家族 | 26.96 | 26.67 | 0.975 | 0.964 |
| Roy 家族 | 27.01 | 31.12 | 0.969 | 0.981 |
| 平均 | 26.77 | 28.97 | 0.967 | 0.969 |

四张中有三张的 PSNR 变好，SSIM 变好的有两张。在 Knowles 肖像上，检测器把部分纹理当成损坏，填补后反而略差。SSIM 的平均提升只有 0.002。所有数字都是在我自己画的损坏上测得的，比真实的磨损容易，所以请把它当作回归检查，而不是对你照片的保证。

**切图。** 把示例照片四张一组、以随机角度放在三种背景上。12 张全部找到，平均 IoU 0.952，最差 0.931。

**速度。** 每个设备预热后跑一次，除切图外全部步骤开启，强制执行色调还原，放大 2 倍。

| 设备 | 图像大小 | fade | repair | faces | 上色 | 放大 | 总计 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 5090 | 960 x 1200 | 0.07 s | 0.36 s | 0.27 s | 0.08 s | 1.47 s | 2.26 s |
| Ryzen 5 7500F, CPU | 480 x 600 | 0.01 s | 6.86 s | 19.36 s | 2.47 s | 106.42 s | 135.13 s |

CPU 那一行使用较小的图像，因为完整尺寸要等太久，所以两行不能直接比较。

## 局限

- 划痕检测器主要用浅色划痕训练。细的深色线条常被漏掉，前后对照表里能看到。请在蒙版编辑器中自己涂。
- 在有纹理或脏污的区域，检测器会误判，Knowles 肖像就是这样变差的。15% 的保护只能挡住最严重的情况。
- GFPGAN 是画出人脸。强度 100 时，脸可能看起来像另一个人。默认值因此是 35，「生成」视图会显示它动过哪里。
- DDColor 是猜颜色，而且偏暖。请把上色结果当作插图。
- 色调还原会让棕褐色调的照片变成中性灰。
- 切图用的是传统图像处理。白色边框的照片放在白色扫描盖板上可能切错，请拖动角点修正轮廓。
- 在线演示是预先算好的输出回放，只有人脸和上色滑块会有反应。

## 与其他工具比较

Bringing Old Photos Back to Life、GFPGAN、LaMa 和 Real-ESRGAN 是这里真正干活的模型，它们各自是独立的研究项目，有自己的命令行。Unfaded 没有改进其中任何一个。它新增的是组装：一条命令处理整张扫描、对会造成损害的步骤设置跳过规则、逐步的改动视图，以及模型生成内容的记录。

## 项目结构

```
src/unfaded/        流程、每一步一个模块、服务器、基准测试
src/unfaded/web/    界面和 9 个语言文件
demo/               GitHub Pages 演示用的预先输出
examples/           公有领域照片和损坏的扫描图，附来源
docs/               安装、使用、配置、架构
tests/              单元测试、浏览器测试、需要权重的端到端测试
```

设计说明在 [docs/architecture.md](docs/architecture.md)，贡献规则在 [CONTRIBUTING.md](CONTRIBUTING.md)，模型许可证在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可证

MIT。模型权重保留各自的许可证，列在声明文件中。

Assisted by Claude/Codex.
