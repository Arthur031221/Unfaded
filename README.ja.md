<div align="center">

<img src="assets/logo.svg" width="96" alt="Unfaded logo">

# Unfaded

**古い家族写真を自分の GPU で修復し、各ステップが何を変えたかを確かめられます。**

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml/badge.svg)](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/install.md)

</div>

パブリックドメインの写真 4 枚に固定シードで傷を描き込んだところ、修復ステップで平均 PSNR が 26.8 dB から 31.0 dB に上がり、分割ステップは合成スキャン上の 12 枚中 12 枚を見つけて平均の重なり（IoU）は 0.95 でした。4 枚すべてで PSNR が改善しました。`unfaded bench` で再現でき、方法は「ベンチマーク」にあります。

![Unfaded がスキャンから 4 枚の写真を切り出して修復し、各ステップの変更を表示する様子](assets/demo.gif)

[ライブデモ](https://arthur031221.github.io/Unfaded/)は 3 枚のサンプルスキャンの実際の出力です。自分のファイルは処理できないので、その場合はツールをインストールしてください。

## 修復前と修復後

| | 修復前 | 修復後 |
| --- | --- | --- |
| 折り目のある家族の肖像、1891 年 | ![修復前](assets/creased-before.jpg) | ![修復後](assets/creased-after.jpg) |
| 伐採キャンプ、1926 年 | ![修復前](assets/camp-before.jpg) | ![修復後](assets/camp-after.jpg) |

どちらもパブリックドメインのスキャンで、傷、折り目、ほこりは `scripts/make_demo.py` で合成して加えました。修復後は既定のパイプライン（分割、トーン、修復、強さ 35% の顔）です。検出器は反転した画像でももう一度動かして暗い傷を見つけますが、細い暗い線は一部見逃します。「制限」を見てください。

モデルは作り話をするので、ツール側でそれをはっきり示すようにしました。ピクセルを描いたステップには「モデルが生成」と表示し、「生成」ビューで場所を正確に塗り、元のファイルには一切触れません。

## できること

Unfaded は短いパイプラインです。各ステップは個別にオフにでき、写真のどれだけを変えたかを報告します。

| ステップ | 内容 | モデル | 既定 |
| --- | --- | --- | --- |
| 分割 | フラットベッドのスキャンから写真を 1 枚ずつ切り出して傾きを直します。角は手でドラッグできます。 | OpenCV、モデルなし | オン |
| 色あせ | 階調を戻し、色かぶりを除きます。写真がすでに階調の 80% に広がっている場合はスキップします。 | なし | オン |
| 修復 | 傷、折り目、ほこりを見つけて埋めます。写真の 15% を超えて埋める場合はスキップします。マスクは自分で塗れます。 | 古い写真の傷検出器、LaMa | オン |
| 顔 | 顔ごとに専用のスライダーで修復します。0 は元の顔のまま、100 は GFPGAN が描いた顔です。 | YuNet、GFPGAN v1.4 | オン、35 |
| 着色 | 白黒写真の色を予測します。明度は変えません。 | DDColor | オフ |
| 拡大 | 2 倍または 4 倍で、大きな写真はタイル処理します。 | Real-ESRGAN x4plus | オフ |

結果にはそれぞれ `.xmp` サイドカーが付き、元ファイルの sha256、各ステップのモデルと設定、モデルがピクセルを生成したステップが記録されます。

## インストール

Python 3.10 以上が必要です。モデルの重みは合計約 1.3 GB で、初回使用時にダウンロードし、固定した sha256 で検証します。その後、データがマシンの外に出ることはありません。

<details>
<summary>NVIDIA GPU 搭載の Linux（テスト済み）</summary>

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
unfaded models --fetch
```

RTX 5090、torch 2.11、CUDA 12.8 で開発しました。

クローンしたくない場合は、`pip install -e .` の代わりにリリースページの wheel をインストールします。

```bash
pip install https://github.com/Arthur031221/Unfaded/releases/download/v0.2.1/unfaded-0.2.1-py3-none-any.whl
```

</details>

<details>
<summary>GPU のないマシン</summary>

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
unfaded restore scan.jpg --device cpu
```

動きますが遅いです。下のタイミングを見てください。

</details>

<details>
<summary>macOS と Windows（未テスト）</summary>

コードにプラットフォーム固有の部分はないので、`pip install -e .` で動くはずですが、どちらの環境でも実行していません。Mac では `--device mps` を試せます。`auto` が選ぶのは CUDA か CPU だけです。

</details>

詳しくは [docs/install.md](docs/install.md) を見てください。

## 使い方

```bash
unfaded restore examples/scans/album-damaged.jpg -o restored --explain
```

これはデモ用に実行したコマンドです。スキャンから 4 枚の写真を見つけ、`album-damaged.unfaded-1.jpg` から `-4.jpg` までを、それぞれサイドカー付きで書き出しました。RTX 5090 ではモデルの読み込みを含めて 12 秒でした。`--explain` は各ステップの内容を表示します。

```
album-damaged.jpg: 4 prints
  wrote restored/album-damaged.unfaded-1.jpg
    fade              skipped   0.01s  the print already uses 92% of the tonal range
    repair       4.0% changed   5.93s
    faces        1.2% changed   1.15s
```

その他のオプション:

```bash
unfaded restore album/ -o restored/            # フォルダ全体
unfaded restore scan.jpg --colorize --scale 2  # 着色して拡大
unfaded restore scan.jpg --face-strength 60    # 顔をより強く
unfaded split scan.jpg                         # 写真の切り出しだけ
unfaded serve                                  # 127.0.0.1:8765 のローカル Web インターフェース
```

Web インターフェースは、見つけた輪郭を表示して修正でき、パイプラインを実行し、結果をステップごとに見られます。修復前後のスライダー、変更のヒートマップ、「生成」ビュー、マスクエディタ、顔ごとの強さスライダーがあります。ライトとダークのテーマがあり、スマートフォンでも使え、英語、繁体字中国語、簡体字中国語、日本語、韓国語、スペイン語、フランス語、ドイツ語、ブラジルポルトガル語に対応します。詳細: [docs/usage.md](docs/usage.md)、[docs/configuration.md](docs/configuration.md)。

## ベンチマーク

`unfaded bench` は以下のすべてをシード 5 で実行します。私の実行結果の生データは [docs/benchmark.json](docs/benchmark.json) にあります。

**修復。** `examples/photos` の 4 枚をきれいな基準として扱います。それぞれ 1600 ピクセルに収め、既知のマスクで傷、折り目、ほこりを描き、修復ステップだけを実行して、きれいな画像に対する PSNR を測ります。

| 写真 | 損傷後 PSNR | 修復後 PSNR | 損傷後 SSIM | 修復後 SSIM |
| --- | --- | --- | --- | --- |
| 伐採キャンプ | 24.90 | 25.65 | 0.954 | 0.943 |
| King 家 | 28.22 | 38.88 | 0.971 | 0.988 |
| Knowles 家 | 26.96 | 27.98 | 0.975 | 0.965 |
| Roy 家 | 27.01 | 31.68 | 0.969 | 0.982 |
| 平均 | 26.77 | 31.05 | 0.967 | 0.970 |

PSNR は 4 枚すべてで、SSIM は 2 枚で改善しました。伐木キャンプと Knowles の写真では検出器がテクスチャの一部を損傷と判断し、埋めた結果 SSIM がわずかに下がりました。SSIM の平均の改善は 0.003 だけです。暗い傷は、検出器を反転画像で動かし、スコアを半分にして見つけています。この重みは同じシードで選びました。シード 11 と 23 では、以前の 1 回だけの検出器に対する平均 PSNR の向上は 0.9 dB と 0.2 dB でした。数字はすべて私が描いた損傷で測っており、実際の劣化より簡単なので、回帰テストとして読んでください。あなたの写真への保証ではありません。

**分割。** サンプルの写真を 1 スキャンに 4 枚ずつ、ランダムな角度で 3 種類の背景に置きました。12 枚すべてを見つけ、平均 IoU は 0.952、最悪は 0.931 でした。

**速度。** デバイスごとにウォームアップ後 1 回実行し、分割以外の全ステップをオン、トーン回復を強制、2 倍拡大にしています。

| デバイス | 画像サイズ | fade | repair | faces | 着色 | 拡大 | 合計 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 5090 | 960 x 1200 | 0.07 s | 0.40 s | 0.22 s | 0.06 s | 1.51 s | 2.26 s |
| Ryzen 5 7500F, CPU | 480 x 600 | 0.02 s | 9.26 s | 12.32 s | 1.87 s | 81.80 s | 105.27 s |

CPU の行は、フルサイズだと時間がかかりすぎるので小さい画像を使っています。そのため 2 行はサイズ面で比較できません。既定でオフの拡大を除くと、CPU は約 22 秒です。

## 制限

- 傷検出器は主に明るい傷で学習されています。暗い傷は反転画像でスコアを半分にして見つけているため、細い暗い線は明るい傷よりまだ見逃しやすいです。マスクエディタで自分で塗ってください。
- テクスチャのある場所や汚れた場所では検出器が誤検出します。伐木キャンプと Knowles の写真で SSIM が下がったのはそのためです。15% のガードで防げるのは最悪のケースだけです。
- GFPGAN は顔を描きます。強さ 100 では別人のように見えることがあります。そのため既定は 35 で、「生成」ビューが作用した場所を示します。
- DDColor は色を推測し、暖色に偏りがちです。着色した出力はイラストとして扱ってください。
- トーンの回復で、セピア色の写真は無彩色のグレーになります。
- 分割は古典的な画像処理です。白い縁の写真を白いスキャナーカバーに置くと、誤って切ることがあります。角をドラッグして輪郭を直してください。
- ライブデモは事前に計算した出力の再生です。反応するのは顔と着色のスライダーだけです。

## 他のツールとの比較

Bringing Old Photos Back to Life、GFPGAN、LaMa、Real-ESRGAN が実際に働くモデルで、それぞれ独立した研究リポジトリで専用のコマンドラインがあります。Unfaded はそのどれも改良していません。追加したのは組み立てです。スキャン全体を 1 つのコマンドで処理すること、害になるステップのスキップ規則、ステップごとの変更ビュー、モデルが生成した内容の記録です。

## プロジェクト構成

```
src/unfaded/        パイプライン、ステップごとのモジュール、サーバー、ベンチマーク
src/unfaded/web/    インターフェースと 9 つのロケールファイル
demo/               GitHub Pages デモ用の事前計算した出力
examples/           パブリックドメインの写真と損傷したスキャン、出典付き
docs/               インストール、使い方、設定、アーキテクチャ
tests/              単体テスト、ブラウザテスト、重みが必要なエンドツーエンドテスト
```

設計メモは [docs/architecture.md](docs/architecture.md)、貢献ルールは [CONTRIBUTING.md](CONTRIBUTING.md)、モデルのライセンスは [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) にあります。

## ライセンス

MIT です。モデルの重みはそれぞれのライセンスを保ち、通知ファイルに載せています。

Assisted by Claude/Codex.
