<div align="center">

<img src="assets/logo.svg" width="96" alt="Unfaded logo">

# Unfaded

**오래된 가족 사진을 내 GPU에서 복원하고, 각 단계가 무엇을 바꿨는지 확인하세요.**

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml/badge.svg)](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/install.md)

</div>

퍼블릭 도메인 사진 4장에 고정 시드로 흠집을 그려 넣었을 때, 복원 단계는 평균 PSNR을 26.8 dB에서 29.0 dB로 높였고, 분할 단계는 합성 스캔에서 12장 중 12장을 찾았으며 평균 겹침 비율(IoU)은 0.95였습니다. 4장 중 1장은 PSNR이 약간 나빠졌습니다. `unfaded bench`로 재현할 수 있고, 방법은 "벤치마크"에 있습니다.

![Unfaded가 스캔에서 사진 4장을 잘라 복원하고 각 단계의 변경을 보여 주는 모습](assets/demo.gif)

[라이브 데모](https://arthur031221.github.io/Unfaded/)는 예제 스캔 3장의 실제 출력입니다. 내 파일은 처리할 수 없으니, 그러려면 도구를 설치하세요.

## 복원 전과 후

| | 복원 전 | 복원 후 |
| --- | --- | --- |
| 접힌 자국이 있는 가족 초상, 1891 | ![복원 전](assets/creased-before.jpg) | ![복원 후](assets/creased-after.jpg) |
| 벌목 캠프, 1926 | ![복원 전](assets/camp-before.jpg) | ![복원 후](assets/camp-after.jpg) |

둘 다 퍼블릭 도메인 스캔이며, 흠집, 접힌 자국, 먼지는 `scripts/make_demo.py`로 합성해 넣었습니다. 복원 후는 기본 파이프라인(분할, 톤, 복원, 강도 35%의 얼굴)입니다. 첫 줄의 어두운 흠집은 그대로 남아 있습니다. 검출기는 흰 흠집은 잘 찾고 가는 어두운 선은 잘 못 찾습니다. "한계"를 보세요.

모델은 지어내기 때문에 도구가 그 사실을 직접 말하도록 만들었습니다. 픽셀을 그린 단계에는 "모델이 생성함"이라고 표시하고, "생성" 보기는 그 위치를 정확히 칠하며, 원본 파일은 절대 건드리지 않습니다.

## 하는 일

Unfaded는 짧은 파이프라인입니다. 각 단계는 끌 수 있고, 사진의 얼마만큼을 바꿨는지 보고합니다.

| 단계 | 내용 | 모델 | 기본값 |
| --- | --- | --- | --- |
| 분할 | 플랫베드 스캔에서 사진을 한 장씩 잘라 똑바로 세웁니다. 모서리는 손으로 끌 수 있습니다. | OpenCV, 모델 없음 | 켬 |
| 바램 | 명암을 복원하고 색 치우침을 없앱니다. 사진이 이미 톤 범위의 80%를 쓰고 있으면 건너뜁니다. | 없음 | 켬 |
| 복원 | 흠집, 접힌 자국, 먼지를 찾아 채웁니다. 사진의 15%보다 많이 채워야 하면 건너뜁니다. 마스크를 직접 칠할 수 있습니다. | 오래된 사진 흠집 검출기, LaMa | 켬 |
| 얼굴 | 얼굴마다 자기 슬라이더로 복원합니다. 0은 원래 얼굴을 유지하고 100은 GFPGAN이 그린 얼굴을 씁니다. | YuNet, GFPGAN v1.4 | 켬, 35 |
| 채색 | 흑백 사진의 색을 예측합니다. 밝기는 바꾸지 않습니다. | DDColor | 끔 |
| 확대 | 2배 또는 4배이며, 큰 사진은 타일로 나눠 처리합니다. | Real-ESRGAN x4plus | 끔 |

결과마다 `.xmp` 사이드카가 붙어, 원본 파일의 sha256, 각 단계의 모델과 설정, 모델이 픽셀을 생성한 단계가 기록됩니다.

## 설치

Python 3.10 이상이 필요합니다. 모델 가중치는 합계 약 1.3 GB이며 처음 사용할 때 내려받고 고정된 sha256으로 검증합니다. 그 뒤로는 데이터가 내 컴퓨터 밖으로 나가지 않습니다.

<details>
<summary>NVIDIA GPU가 있는 Linux(테스트함)</summary>

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
unfaded models --fetch
```

RTX 5090, torch 2.11, CUDA 12.8에서 개발했습니다.

</details>

<details>
<summary>GPU가 없는 컴퓨터</summary>

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
unfaded restore scan.jpg --device cpu
```

동작하지만 느립니다. 아래 시간을 보세요.

</details>

<details>
<summary>macOS와 Windows(테스트 안 함)</summary>

코드에 플랫폼별 부분이 없으므로 `pip install -e .`가 동작해야 하지만, 두 시스템 모두에서 실행해 보지 않았습니다. Mac에서는 `--device mps`를 시도할 수 있습니다. `auto`는 CUDA 또는 CPU만 고릅니다.

</details>

자세한 내용은 [docs/install.md](docs/install.md)를 보세요.

## 사용법

```bash
unfaded restore examples/scans/album-damaged.jpg -o restored --explain
```

데모를 만들 때 실행한 명령입니다. 스캔에서 사진 4장을 찾아 `album-damaged.unfaded-1.jpg`부터 `-4.jpg`까지 각각 사이드카와 함께 썼습니다. RTX 5090에서 모델 로딩을 포함해 12초가 걸렸습니다. `--explain`은 각 단계가 한 일을 보여 줍니다.

```
album-damaged.jpg: 4 prints
  wrote restored/album-damaged.unfaded-1.jpg
    fade              skipped   0.01s  the print already uses 92% of the tonal range
    repair       4.0% changed   5.93s
    faces        1.2% changed   1.15s
```

그 밖의 옵션:

```bash
unfaded restore album/ -o restored/            # 폴더 전체
unfaded restore scan.jpg --colorize --scale 2  # 채색하고 확대
unfaded restore scan.jpg --face-strength 60    # 더 강한 얼굴 복원
unfaded split scan.jpg                         # 사진만 잘라내기
unfaded serve                                  # 127.0.0.1:8765의 로컬 웹 인터페이스
```

웹 인터페이스는 찾은 윤곽을 보여 주고 고칠 수 있게 하며, 파이프라인을 실행한 뒤 결과를 단계별로 살펴보게 해 줍니다. 복원 전후 슬라이더, 변경 히트맵, "생성" 보기, 마스크 편집기, 얼굴별 강도 슬라이더가 있습니다. 라이트와 다크 테마가 있고 휴대폰에서도 쓸 수 있으며, 영어, 번체 중국어, 간체 중국어, 일본어, 한국어, 스페인어, 프랑스어, 독일어, 브라질 포르투갈어를 지원합니다. 전체 설명: [docs/usage.md](docs/usage.md), [docs/configuration.md](docs/configuration.md).

## 벤치마크

`unfaded bench`는 아래 모든 것을 시드 5로 실행합니다. 제가 실행한 원본 출력은 [docs/benchmark.json](docs/benchmark.json)에 있습니다.

**복원.** `examples/photos`의 사진 4장을 깨끗한 기준으로 봅니다. 각각 1600픽셀에 맞추고, 알려진 마스크로 흠집, 접힌 자국, 먼지를 그린 뒤 복원 단계만 실행하고, 깨끗한 이미지와 비교해 PSNR을 잽니다.

| 사진 | 손상 후 PSNR | 복원 후 PSNR | 손상 후 SSIM | 복원 후 SSIM |
| --- | --- | --- | --- | --- |
| 벌목 캠프 | 24.90 | 25.57 | 0.954 | 0.948 |
| King 가족 | 28.22 | 32.53 | 0.971 | 0.984 |
| Knowles 가족 | 26.96 | 26.67 | 0.975 | 0.964 |
| Roy 가족 | 27.01 | 31.12 | 0.969 | 0.981 |
| 평균 | 26.77 | 28.97 | 0.967 | 0.969 |

PSNR은 4장 중 3장에서, SSIM은 2장에서 좋아졌습니다. Knowles 초상에서는 검출기가 질감 일부를 손상으로 표시했고 채우기 때문에 약간 나빠졌습니다. SSIM의 평균 향상은 0.002뿐입니다. 모든 수치는 제가 직접 그린 손상에서 잰 것이라 실제 마모보다 쉽습니다. 회귀 검사로 읽어 주세요. 여러분의 사진에 대한 약속은 아닙니다.

**분할.** 예제 사진을 스캔 한 장에 4장씩, 무작위 각도로 3가지 배경에 놓았습니다. 12장 모두 찾았고 평균 IoU는 0.952, 최악은 0.931이었습니다.

**속도.** 장치마다 예열 뒤 한 번 실행했고, 분할을 뺀 모든 단계를 켜고 톤 복원을 강제하고 2배 확대했습니다.

| 장치 | 이미지 크기 | fade | repair | faces | 채색 | 확대 | 합계 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 5090 | 960 x 1200 | 0.07 s | 0.36 s | 0.27 s | 0.08 s | 1.47 s | 2.26 s |
| Ryzen 5 7500F, CPU | 480 x 600 | 0.01 s | 6.86 s | 19.36 s | 2.47 s | 106.42 s | 135.13 s |

CPU 행은 전체 크기로는 너무 오래 걸려서 더 작은 이미지를 썼으므로, 두 행은 크기 면에서 비교할 수 없습니다.

## 한계

- 흠집 검출기는 주로 밝은 흠집으로 학습되었습니다. 가는 어두운 선은 자주 놓치며, 복원 전후 표에서 볼 수 있습니다. 마스크 편집기에서 직접 칠하세요.
- 질감이 있거나 더러운 영역에서는 검출기가 오탐을 냅니다. Knowles 초상이 나빠진 이유입니다. 15% 보호 장치는 최악의 경우만 막습니다.
- GFPGAN은 얼굴을 그립니다. 강도 100에서는 다른 사람처럼 보일 수 있습니다. 그래서 기본값이 35이고, "생성" 보기가 어디에 작용했는지 보여 줍니다.
- DDColor는 색을 추측하며 따뜻한 쪽으로 치우치는 경향이 있습니다. 채색 결과는 일러스트로 다루세요.
- 톤 복원은 세피아 사진을 무채색 회색으로 만듭니다.
- 분할은 고전적인 이미지 처리입니다. 흰 테두리 사진을 흰 스캐너 덮개에 놓으면 잘못 자를 수 있습니다. 모서리를 끌어 윤곽을 고치세요.
- 라이브 데모는 미리 계산한 출력의 재생입니다. 얼굴과 채색 슬라이더만 반응합니다.

## 다른 도구와 비교

Bringing Old Photos Back to Life, GFPGAN, LaMa, Real-ESRGAN이 여기서 실제로 일하는 모델이며, 각각 자체 명령줄이 있는 별개의 연구 저장소입니다. Unfaded는 그중 어느 것도 개선하지 않았습니다. 더한 것은 조립입니다. 스캔 전체를 한 명령으로 처리하고, 해가 되는 단계를 건너뛰는 규칙, 단계별 변경 보기, 모델이 지어낸 내용의 기록입니다.

## 프로젝트 구조

```
src/unfaded/        파이프라인, 단계별 모듈, 서버, 벤치마크
src/unfaded/web/    인터페이스와 로캘 파일 9개
demo/               GitHub Pages 데모용 미리 계산한 출력
examples/           퍼블릭 도메인 사진과 손상된 스캔, 출처 포함
docs/               설치, 사용법, 설정, 아키텍처
tests/              단위 테스트, 브라우저 테스트, 가중치가 필요한 종단 간 테스트
```

설계 노트는 [docs/architecture.md](docs/architecture.md), 기여 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md), 모델 라이선스는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 있습니다.

## 라이선스

MIT입니다. 모델 가중치는 각자의 라이선스를 유지하며, 고지 파일에 나열되어 있습니다.

Assisted by Claude/Codex.
