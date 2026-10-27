<div align="center">

<img src="assets/logo.svg" width="96" alt="Unfaded logo">

# Unfaded

**Alte Familienfotos auf der eigenen GPU restaurieren und sehen, was jeder Schritt verändert hat.**

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml/badge.svg)](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/install.md)

</div>

Auf vier gemeinfreien Fotos, in die ich mit festen Seeds Kratzer gemalt habe, hob der Reparaturschritt den mittleren PSNR von 26,8 dB auf 29,0 dB, und der Splitter fand auf synthetischen Scans 12 von 12 Abzügen mit einer mittleren Überlappung (IoU) von 0,95. Bei einem der vier Fotos wurde der PSNR etwas schlechter. Mit `unfaded bench` lässt sich das nachvollziehen, die Methode steht unter [Benchmark](#benchmark).

![Unfaded schneidet vier Abzüge aus einem Scan, restauriert sie und zeigt, was jeder Schritt verändert hat](assets/demo.gif)

Die [Live-Demo](https://arthur031221.github.io/Unfaded/) zeigt echte Ausgaben von drei Beispielscans. Eigene Dateien kann sie nicht verarbeiten, dafür das Werkzeug installieren.

## Vorher und nachher

| | Vorher | Nachher |
| --- | --- | --- |
| Familienporträt mit Knick, 1891 | ![Vorher](assets/creased-before.jpg) | ![Nachher](assets/creased-after.jpg) |
| Holzfällerlager, 1926 | ![Vorher](assets/camp-before.jpg) | ![Nachher](assets/camp-after.jpg) |

Beide sind gemeinfreie Scans, denen `scripts/make_demo.py` synthetische Kratzer, einen Knick und Staub hinzugefügt hat. Nachher ist die Standardpipeline: Splitten, Tonwerte, Reparatur, Gesichter mit 35 Prozent. Die dunklen Kratzer in der ersten Zeile sind noch da. Der Detektor findet weiße Kratzer gut und dünne dunkle Linien schlecht, siehe [Grenzen](#grenzen).

Modelle erfinden Dinge, deshalb habe ich das Werkzeug dazu gebracht, es zu sagen. Jeder Schritt, der Pixel gezeichnet hat, trägt das Etikett "vom Modell erfunden", die Ansicht Erfunden markiert genau wo, und die Originaldatei wird nie angefasst.

## Was es tut

Unfaded ist eine kurze Pipeline. Jeder Schritt lässt sich abschalten, und jeder Schritt meldet, wie viel vom Abzug er verändert hat.

| Schritt | Was passiert | Modell | Standard |
| --- | --- | --- | --- |
| Splitten | Schneidet jeden Abzug aus einem Flachbettscan aus und richtet ihn gerade. Die Ecken lassen sich von Hand ziehen. | OpenCV, kein Modell | an |
| Verblassen | Stellt die Tonwerte wieder her und entfernt den Farbstich. Wird übersprungen, wenn der Abzug schon 80 Prozent des Tonwertbereichs nutzt. | keins | an |
| Reparatur | Findet Kratzer, Knicke und Staub und füllt sie. Wird übersprungen, wenn mehr als 15 Prozent des Abzugs gefüllt werden müssten. Die Maske kann man selbst malen. | Kratzerdetektor für alte Fotos, LaMa | an |
| Gesichter | Restauriert jedes Gesicht mit eigenem Regler. 0 behält das alte Gesicht, 100 nimmt, was GFPGAN zeichnet. | YuNet, GFPGAN v1.4 | an, 35 |
| Farbe | Sagt die Farbe von Schwarzweißabzügen voraus. Die Helligkeit ändert sich nie. | DDColor | aus |
| Vergrößern | 2x oder 4x, bei großen Abzügen kachelweise. | Real-ESRGAN x4plus | aus |

Jedes Ergebnis bekommt eine `.xmp`-Begleitdatei mit dem sha256 der Quelldatei, jedem Schritt mit Modell und Einstellungen und den Schritten, in denen ein Modell Pixel erzeugt hat.

## Installation

Python 3.10 oder neuer. Die Modellgewichte, insgesamt etwa 1,3 GB, werden bei der ersten Nutzung geladen und gegen einen festen sha256 geprüft. Danach verlässt nichts den Rechner.

<details>
<summary>Linux mit NVIDIA-GPU (getestet)</summary>

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
unfaded models --fetch
```

Ich habe es auf einer RTX 5090 mit torch 2.11 und CUDA 12.8 entwickelt.

</details>

<details>
<summary>Jeder Rechner ohne GPU</summary>

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
unfaded restore scan.jpg --device cpu
```

Es läuft, ist aber langsam, siehe die Zeiten unten.

</details>

<details>
<summary>macOS und Windows (nicht getestet)</summary>

Der Code hat keine plattformspezifischen Teile, `pip install -e .` sollte also funktionieren. Ich habe es auf keinem der beiden Systeme ausgeführt. Auf einem Mac kann man `--device mps` versuchen, `auto` wählt nur CUDA oder die CPU.

</details>

Mehr in [docs/install.md](docs/install.md).

## Benutzung

```bash
unfaded restore examples/scans/album-damaged.jpg -o restored --explain
```

Das ist der Befehl, den ich für die Demo ausgeführt habe. Er fand vier Abzüge im Scan und schrieb `album-damaged.unfaded-1.jpg` bis `-4.jpg`, jeweils mit Begleitdatei. Auf der RTX 5090 dauerte es 12 Sekunden einschließlich Modellladen. `--explain` zeigt, was jeder Schritt getan hat:

```
album-damaged.jpg: 4 prints
  wrote restored/album-damaged.unfaded-1.jpg
    fade              skipped   0.01s  the print already uses 92% of the tonal range
    repair       4.0% changed   5.93s
    faces        1.2% changed   1.15s
```

Weitere Optionen:

```bash
unfaded restore album/ -o restored/            # ein ganzer Ordner
unfaded restore scan.jpg --colorize --scale 2  # Farbe hinzufügen und vergrößern
unfaded restore scan.jpg --face-strength 60    # stärkere Gesichter
unfaded split scan.jpg                         # nur die Abzüge ausschneiden
unfaded serve                                  # lokale Weboberfläche auf 127.0.0.1:8765
```

Die Weboberfläche zeigt die gefundenen Umrisse, lässt sie korrigieren, führt die Pipeline aus und lässt dich dann das Ergebnis Schritt für Schritt durchgehen, mit einem Vorher-nachher-Regler, einer Heatmap der Änderungen, einer Ansicht Erfunden, einem Maskeneditor und einem Stärkeregler pro Gesicht. Sie hat helle und dunkle Themen, funktioniert auf dem Telefon und gibt es auf Englisch, Traditionellem Chinesisch, Vereinfachtem Chinesisch, Japanisch, Koreanisch, Spanisch, Französisch, Deutsch und brasilianischem Portugiesisch. Vollständige Referenz: [docs/usage.md](docs/usage.md), [docs/configuration.md](docs/configuration.md).

## Benchmark

`unfaded bench` führt alles Folgende mit Seed 5 aus. Die Rohausgabe meines Laufs liegt in [docs/benchmark.json](docs/benchmark.json).

**Reparatur.** Die vier Fotos in `examples/photos` gelten als saubere Referenz. Jedes wird auf 1600 Pixel angepasst, mit bekannter Maske werden Kratzer, Knicke und Staub aufgemalt, nur der Reparaturschritt läuft, und der PSNR wird gegen das saubere Bild gemessen.

| Foto | PSNR beschädigt | PSNR repariert | SSIM beschädigt | SSIM repariert |
| --- | --- | --- | --- | --- |
| Holzfällerlager | 24.90 | 25.57 | 0.954 | 0.948 |
| Familie King | 28.22 | 32.53 | 0.971 | 0.984 |
| Familie Knowles | 26.96 | 26.67 | 0.975 | 0.964 |
| Familie Roy | 27.01 | 31.12 | 0.969 | 0.981 |
| Mittel | 26.77 | 28.97 | 0.967 | 0.969 |

Der PSNR verbesserte sich bei drei von vier Fotos und der SSIM bei zwei. Beim Knowles-Porträt markierte der Detektor Teile der Textur als Schaden, und das Füllen machte es etwas schlechter. Der mittlere SSIM-Gewinn beträgt nur 0,002. Alles ist an selbst gemalten Schäden gemessen, die leichter sind als echter Verschleiß, also bitte als Regressionstest lesen und nicht als Versprechen für deine Fotos.

**Splitten.** Die Beispielabzüge liegen zu viert pro Scan auf drei Hintergründen in zufälligen Winkeln. Alle 12 Abzüge wurden gefunden, mittlere IoU 0,952, schlechteste 0,931.

**Geschwindigkeit.** Ein Lauf pro Gerät nach dem Aufwärmen, alle Schritte an außer Splitten, Tonwertwiederherstellung erzwungen, 2x Vergrößerung.

| Gerät | Bildgröße | fade | repair | faces | Farbe | Vergrößern | gesamt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 5090 | 960 x 1200 | 0.07 s | 0.36 s | 0.27 s | 0.08 s | 1.47 s | 2.26 s |
| Ryzen 5 7500F, CPU | 480 x 600 | 0.01 s | 6.86 s | 19.36 s | 2.47 s | 106.42 s | 135.13 s |

Die CPU-Zeile nutzt ein kleineres Bild, weil die volle Größe zu lange dauert, deshalb sind die beiden Zeilen der Größe nach nicht vergleichbar.

## Grenzen

- Der Kratzerdetektor ist vor allem auf helle Kratzer trainiert. Dünne dunkle Linien übersieht er oft, was in der Vorher-nachher-Tabelle zu sehen ist. Male sie im Maskeneditor.
- Auf texturierten oder schmutzigen Flächen liefert der Detektor Fehlalarme, so wurde das Knowles-Porträt schlechter. Die 15-Prozent-Sperre stoppt nur die schlimmsten Fälle.
- GFPGAN zeichnet Gesichter. Bei Stärke 100 kann ein Gesicht wie eine andere Person aussehen. Der Standard ist deshalb 35, und die Ansicht Erfunden zeigt, wo es gewirkt hat.
- DDColor rät die Farbe und neigt zu einem warmen Stich. Behandle kolorierte Ausgaben als Illustration.
- Die Tonwertwiederherstellung macht Sepiaabzüge neutral grau.
- Der Splitter nutzt klassische Bildverarbeitung. Abzüge mit weißem Rand auf einem weißen Scannerdeckel können falsch geschnitten werden. Korrigiere den Umriss durch Ziehen der Ecken.
- Die Live-Demo spielt vorberechnete Ausgaben ab. Nur die Regler für Gesichter und Farbe reagieren.

## Vergleich mit anderen Werkzeugen

Bringing Old Photos Back to Life, GFPGAN, LaMa und Real-ESRGAN sind die Modelle, die hier die Arbeit machen, jedes ist ein eigenes Forschungsrepository mit eigener Kommandozeile. Unfaded verbessert keines davon. Neu ist die Zusammenstellung: ein Befehl für einen ganzen Scan, eine Überspringregel für Schritte, die schaden würden, eine Änderungsansicht pro Schritt und ein Protokoll dessen, was die Modelle erfunden haben.

## Projektstruktur

```
src/unfaded/        Pipeline, ein Modul pro Schritt, Server, Benchmark
src/unfaded/web/    Oberfläche und 9 Sprachdateien
demo/               vorberechnete Ausgaben für die GitHub-Pages-Demo
examples/           gemeinfreie Fotos und beschädigte Scans, mit Quellen
docs/               Installation, Benutzung, Konfiguration, Architektur
tests/              Unit-Tests, Browsertest, Ende-zu-Ende-Tests, die die Gewichte brauchen
```

Designnotizen stehen in [docs/architecture.md](docs/architecture.md), Beitragsregeln in [CONTRIBUTING.md](CONTRIBUTING.md) und Modelllizenzen in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Lizenz

MIT. Die Modellgewichte behalten ihre eigenen Lizenzen, die in der Hinweisdatei aufgeführt sind.

Assisted by Claude/Codex.
