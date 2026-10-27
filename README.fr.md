<div align="center">

<img src="assets/logo.svg" width="96" alt="Unfaded logo">

# Unfaded

**Restaurez de vieilles photos de famille sur votre propre GPU et voyez ce que chaque étape a changé.**

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml/badge.svg)](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/install.md)

</div>

Sur quatre photos du domaine public où j'ai dessiné des rayures avec des graines fixes, l'étape de réparation a fait passer le PSNR moyen de 26,8 dB à 29,0 dB, et le découpeur a trouvé 12 tirages sur 12 dans des scans synthétiques, avec un recouvrement moyen (IoU) de 0,95. Le PSNR d'une des quatre photos s'est un peu dégradé. On le reproduit avec `unfaded bench`, la méthode est dans [Benchmark](#benchmark).

![Unfaded découpe quatre tirages d'un scan, les restaure et montre ce que chaque étape a changé](assets/demo.gif)

La [démo en ligne](https://arthur031221.github.io/Unfaded/) montre le vrai résultat de trois scans d'exemple. Elle ne peut pas traiter vos fichiers, installez l'outil pour cela.

## Avant et après

| | Avant | Après |
| --- | --- | --- |
| Portrait de famille avec pli, 1891 | ![Avant](assets/creased-before.jpg) | ![Après](assets/creased-after.jpg) |
| Camp de bûcherons, 1926 | ![Avant](assets/camp-before.jpg) | ![Après](assets/camp-after.jpg) |

Les deux sont des scans du domaine public auxquels `scripts/make_demo.py` a ajouté des rayures, un pli et de la poussière synthétiques. Après correspond au pipeline par défaut : découpe, tonalité, réparation, visages à 35 pour cent. Les rayures sombres de la première ligne sont toujours là. Le détecteur trouve bien les rayures blanches et mal les lignes sombres fines, voir [Limites](#limites).

Les modèles inventent des choses, alors j'ai fait en sorte que l'outil le dise. Chaque étape qui a dessiné des pixels porte la mention « inventé par le modèle », la vue Inventé peint exactement où, et le fichier original n'est jamais touché.

## Ce que ça fait

Unfaded est un court pipeline. Chaque étape peut être désactivée et chacune indique quelle part du tirage elle a modifiée.

| Étape | Ce qui se passe | Modèle | Par défaut |
| --- | --- | --- | --- |
| Découpe | Découpe chaque tirage d'un scan à plat et le redresse. Les coins peuvent être déplacés à la main. | OpenCV, sans modèle | activée |
| Fané | Restaure les niveaux et retire la dominante de couleur. Ignorée si le tirage couvre déjà 80 pour cent de la plage tonale. | aucun | activée |
| Réparation | Trouve rayures, plis et poussière, puis les comble. Ignorée si plus de 15 pour cent du tirage devrait être comblé. Vous pouvez peindre le masque vous-même. | Détecteur de rayures de vieilles photos, LaMa | activée |
| Visages | Restaure chaque visage avec son propre curseur. 0 garde l'ancien visage, 100 utilise ce que dessine GFPGAN. | YuNet, GFPGAN v1.4 | activée, 35 |
| Couleur | Prédit la couleur des tirages en noir et blanc. La luminosité n'est jamais modifiée. | DDColor | désactivée |
| Agrandissement | 2x ou 4x, par tuiles pour les grands tirages. | Real-ESRGAN x4plus | désactivée |

Chaque résultat reçoit un fichier annexe `.xmp` avec le sha256 du fichier source, chaque étape avec son modèle et ses réglages, et les étapes où un modèle a généré des pixels.

## Installation

Python 3.10 ou plus récent. Les poids des modèles, environ 1,3 Go au total, sont téléchargés à la première utilisation et vérifiés avec un sha256 fixé. Ensuite, rien ne quitte votre machine.

<details>
<summary>Linux avec un GPU NVIDIA (testé)</summary>

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
unfaded models --fetch
```

Je l'ai développé sur une RTX 5090 avec torch 2.11 et CUDA 12.8.

</details>

<details>
<summary>Toute machine sans GPU</summary>

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
unfaded restore scan.jpg --device cpu
```

Ça marche mais c'est lent, voir les temps plus bas.

</details>

<details>
<summary>macOS et Windows (non testé)</summary>

Le code n'a aucune partie propre à une plateforme, donc `pip install -e .` devrait fonctionner. Je ne l'ai lancé sur aucun des deux systèmes. Sur un Mac, vous pouvez essayer `--device mps`, `auto` ne choisit que CUDA ou le CPU.

</details>

Plus de détails dans [docs/install.md](docs/install.md).

## Utilisation

```bash
unfaded restore examples/scans/album-damaged.jpg -o restored --explain
```

C'est la commande que j'ai lancée pour la démo. Elle a trouvé quatre tirages dans le scan et écrit `album-damaged.unfaded-1.jpg` jusqu'à `-4.jpg`, chacun avec son fichier annexe. Sur la RTX 5090, elle a pris 12 secondes, chargement des modèles compris. `--explain` montre ce que chaque étape a fait :

```
album-damaged.jpg: 4 prints
  wrote restored/album-damaged.unfaded-1.jpg
    fade              skipped   0.01s  the print already uses 92% of the tonal range
    repair       4.0% changed   5.93s
    faces        1.2% changed   1.15s
```

Plus d'options :

```bash
unfaded restore album/ -o restored/            # un dossier entier
unfaded restore scan.jpg --colorize --scale 2  # ajouter la couleur et agrandir
unfaded restore scan.jpg --face-strength 60    # visages plus marqués
unfaded split scan.jpg                         # seulement découper les tirages
unfaded serve                                  # interface web locale sur 127.0.0.1:8765
```

L'interface web montre les contours trouvés, vous laisse les corriger, lance le pipeline, puis vous laisse parcourir le résultat étape par étape avec un curseur avant et après, une carte de chaleur des changements, une vue Inventé, un éditeur de masque et un curseur de force par visage. Elle a des thèmes clair et sombre, fonctionne sur un téléphone et existe en anglais, chinois traditionnel, chinois simplifié, japonais, coréen, espagnol, français, allemand et portugais du Brésil. Référence complète : [docs/usage.md](docs/usage.md), [docs/configuration.md](docs/configuration.md).

## Benchmark

`unfaded bench` exécute tout ce qui suit, avec la graine 5. La sortie brute de mon exécution est dans [docs/benchmark.json](docs/benchmark.json).

**Réparation.** Les quatre photos de `examples/photos` servent de référence propre. Chacune est ajustée à 1600 pixels, on y dessine rayures, plis et poussière avec un masque connu, seule l'étape de réparation s'exécute, et le PSNR est mesuré par rapport à l'image propre.

| Photo | PSNR abîmée | PSNR réparée | SSIM abîmée | SSIM réparée |
| --- | --- | --- | --- | --- |
| Camp de bûcherons | 24.90 | 25.57 | 0.954 | 0.948 |
| Famille King | 28.22 | 32.53 | 0.971 | 0.984 |
| Famille Knowles | 26.96 | 26.67 | 0.975 | 0.964 |
| Famille Roy | 27.01 | 31.12 | 0.969 | 0.981 |
| Moyenne | 26.77 | 28.97 | 0.967 | 0.969 |

Le PSNR s'est amélioré sur trois photos sur quatre et le SSIM sur deux. Sur le portrait Knowles, le détecteur a marqué une partie de la texture comme dégât et le comblement l'a un peu dégradé. Le gain moyen de SSIM n'est que de 0,002. Tout est mesuré sur des dégâts que j'ai dessinés moi-même, plus faciles que l'usure réelle, donc lisez cela comme un test de régression et non comme une promesse sur vos photos.

**Découpe.** Les tirages d'exemple sont placés par quatre par scan sur trois fonds, avec des angles aléatoires. Les 12 tirages ont été trouvés, IoU moyen 0,952, pire cas 0,931.

**Vitesse.** Une exécution par appareil après préchauffage, toutes les étapes activées sauf la découpe, récupération de tonalité forcée, agrandissement 2x.

| Appareil | Taille de l'image | fade | repair | faces | couleur | agrandissement | total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 5090 | 960 x 1200 | 0.07 s | 0.36 s | 0.27 s | 0.08 s | 1.47 s | 2.26 s |
| Ryzen 5 7500F, CPU | 480 x 600 | 0.01 s | 6.86 s | 19.36 s | 2.47 s | 106.42 s | 135.13 s |

La ligne CPU utilise une image plus petite parce que la taille réelle prend trop de temps, donc les deux lignes ne sont pas comparables par la taille.

## Limites

- Le détecteur de rayures est surtout entraîné sur des rayures claires. Les lignes sombres fines sont souvent manquées, ce qui se voit dans le tableau avant et après. Peignez-les dans l'éditeur de masque.
- Sur les zones texturées ou sales, le détecteur donne des faux positifs, c'est ainsi que le portrait Knowles s'est dégradé. La garde de 15 pour cent n'arrête que les pires cas.
- GFPGAN dessine des visages. À la force 100, un visage peut ressembler à une autre personne. La valeur par défaut est donc 35, et la vue Inventé montre où il a agi.
- DDColor devine la couleur et tire vers une dominante chaude. Traitez la sortie colorisée comme une illustration.
- La récupération de tonalité rend les tirages sépia gris neutre.
- Le découpeur utilise du traitement d'image classique. Des tirages à bord blanc sur un couvercle de scanner blanc peuvent être mal découpés. Corrigez le contour en déplaçant les coins.
- La démo en ligne rejoue des résultats précalculés. Seuls les curseurs de visage et de couleur réagissent.

## Comparaison avec d'autres outils

Bringing Old Photos Back to Life, GFPGAN, LaMa et Real-ESRGAN sont les modèles qui font le travail ici, chacun est un dépôt de recherche séparé avec sa propre ligne de commande. Unfaded n'en améliore aucun. Il apporte l'assemblage : une commande pour un scan entier, une règle pour ignorer les étapes qui feraient du tort, une vue des changements par étape et une trace de ce que les modèles ont inventé.

## Structure du projet

```
src/unfaded/        pipeline, un module par étape, serveur, benchmark
src/unfaded/web/    interface et 9 fichiers de langue
demo/               sorties précalculées pour la démo GitHub Pages
examples/           photos du domaine public et scans abîmés, avec sources
docs/               installation, usage, configuration, architecture
tests/              tests unitaires, test navigateur, tests de bout en bout qui nécessitent les poids
```

Les notes de conception sont dans [docs/architecture.md](docs/architecture.md), les règles de contribution dans [CONTRIBUTING.md](CONTRIBUTING.md) et les licences des modèles dans [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Licence

MIT. Les poids des modèles gardent leurs propres licences, listées dans le fichier d'avis.

Assisted by Claude/Codex.
