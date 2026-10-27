<div align="center">

<img src="assets/logo.svg" width="96" alt="Unfaded logo">

# Unfaded

**Restaura fotos familiares antiguas en tu propia GPU y mira qué cambió cada paso.**

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml/badge.svg)](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/install.md)

</div>

En cuatro fotos de dominio público con arañazos que dibujé con semillas fijas, el paso de reparación subió el PSNR medio de 26,8 dB a 31,0 dB, y el separador encontró 12 de 12 copias en escaneos sintéticos con un solapamiento medio (IoU) de 0,95. El PSNR mejoró en las cuatro fotos. Se reproduce con `unfaded bench`, y el método está en [Benchmark](#benchmark).

![Unfaded recorta cuatro copias de un escaneo, las restaura y muestra lo que cambió cada paso](assets/demo.gif)

La [demo en vivo](https://arthur031221.github.io/Unfaded/) usa el resultado real de tres escaneos de ejemplo. No puede procesar tus archivos, para eso instala la herramienta.

## Antes y después

| | Antes | Después |
| --- | --- | --- |
| Retrato familiar con pliegue, 1891 | ![Antes](assets/creased-before.jpg) | ![Después](assets/creased-after.jpg) |
| Campamento maderero, 1926 | ![Antes](assets/camp-before.jpg) | ![Después](assets/camp-after.jpg) |

Los dos son escaneos de dominio público a los que `scripts/make_demo.py` añadió arañazos, un pliegue y polvo sintéticos. Después es el flujo por defecto: separar, tono, reparar y caras al 35 por ciento. El detector también se ejecuta sobre la imagen invertida, así encuentra los arañazos oscuros, pero aún se le escapan algunas líneas finas oscuras, mira [Límites](#límites).

Los modelos se inventan cosas, así que hice que la herramienta lo diga. Cada paso que dibujó píxeles lleva la etiqueta "inventado por el modelo", la vista Inventado marca exactamente dónde, y el archivo original nunca se toca.

## Qué hace

Unfaded es un flujo corto. Cada paso se puede apagar y cada paso informa de cuánto de la foto cambió.

| Paso | Qué ocurre | Modelo | Por defecto |
| --- | --- | --- | --- |
| Separar | Recorta cada copia de un escaneo plano y la endereza. Las esquinas se pueden arrastrar a mano. | OpenCV, sin modelo | sí |
| Desvaído | Restaura los niveles y quita la dominante de color. Se omite si la copia ya ocupa el 80 por ciento del rango tonal. | ninguno | sí |
| Reparar | Busca arañazos, pliegues y polvo, y los rellena. Se omite si habría que rellenar más del 15 por ciento de la copia. Puedes pintar la máscara tú. | Detector de arañazos de fotos antiguas, LaMa | sí |
| Caras | Restaura cada cara con su propio control deslizante. 0 conserva la cara vieja, 100 usa lo que dibuja GFPGAN. | YuNet, GFPGAN v1.4 | sí, 35 |
| Color | Predice el color de las copias en blanco y negro. La luminosidad nunca cambia. | DDColor | no |
| Ampliar | 2x o 4x, por teselas en copias grandes. | Real-ESRGAN x4plus | no |

Cada resultado recibe un archivo auxiliar `.xmp` con el sha256 del archivo de origen, cada paso con su modelo y sus ajustes, y los pasos en los que un modelo generó píxeles.

## Instalación

Python 3.10 o superior. Los pesos de los modelos, unos 1,3 GB en total, se descargan en el primer uso y se comprueban con un sha256 fijo. Después nada sale de tu máquina.

<details>
<summary>Linux con una GPU NVIDIA (probado)</summary>

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
unfaded models --fetch
```

Lo desarrollé en una RTX 5090 con torch 2.11 y CUDA 12.8.

Para no clonar el repositorio, instala el wheel de la página de la versión en lugar de `pip install -e .`:

```bash
pip install https://github.com/Arthur031221/Unfaded/releases/download/v0.2.1/unfaded-0.2.1-py3-none-any.whl
```

</details>

<details>
<summary>Cualquier máquina sin GPU</summary>

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
unfaded restore scan.jpg --device cpu
```

Funciona pero es lento, mira los tiempos más abajo.

</details>

<details>
<summary>macOS y Windows (sin probar)</summary>

El código no tiene partes específicas de plataforma, así que `pip install -e .` debería funcionar. No lo he ejecutado en ninguno de los dos sistemas. En un Mac puedes probar `--device mps`, `auto` solo elige CUDA o la CPU.

</details>

Más en [docs/install.md](docs/install.md).

## Uso

```bash
unfaded restore examples/scans/album-damaged.jpg -o restored --explain
```

Este es el comando que ejecuté para la demo. Encontró cuatro copias en el escaneo y escribió `album-damaged.unfaded-1.jpg` hasta `-4.jpg`, cada una con su archivo auxiliar. En la RTX 5090 tardó 12 segundos, con la carga de modelos incluida. `--explain` muestra lo que hizo cada paso:

```
album-damaged.jpg: 4 prints
  wrote restored/album-damaged.unfaded-1.jpg
    fade              skipped   0.01s  the print already uses 92% of the tonal range
    repair       4.0% changed   5.93s
    faces        1.2% changed   1.15s
```

Más opciones:

```bash
unfaded restore album/ -o restored/            # una carpeta entera
unfaded restore scan.jpg --colorize --scale 2  # añadir color y ampliar
unfaded restore scan.jpg --face-strength 60    # caras más fuertes
unfaded split scan.jpg                         # solo recortar las copias
unfaded serve                                  # interfaz web local en 127.0.0.1:8765
```

La interfaz web muestra los contornos que encontró, te deja corregirlos, ejecuta el flujo y luego te deja recorrer el resultado paso a paso con un control deslizante de antes y después, un mapa de calor de lo que cambió, una vista Inventado, un editor de máscara y un control de fuerza por cara. Tiene temas claro y oscuro, funciona en el móvil y viene en inglés, chino tradicional, chino simplificado, japonés, coreano, español, francés, alemán y portugués de Brasil. Referencia completa: [docs/usage.md](docs/usage.md), [docs/configuration.md](docs/configuration.md).

## Benchmark

`unfaded bench` ejecuta todo lo de abajo, con la semilla 5. La salida original de mi ejecución está en [docs/benchmark.json](docs/benchmark.json).

**Reparación.** Las cuatro fotos de `examples/photos` se tratan como referencia limpia. Cada una se ajusta a 1600 píxeles, se le dibujan arañazos, pliegues y polvo con una máscara conocida, solo se ejecuta el paso de reparación y se mide el PSNR contra la imagen limpia.

| Foto | PSNR dañada | PSNR reparada | SSIM dañada | SSIM reparada |
| --- | --- | --- | --- | --- |
| Campamento maderero | 24.90 | 25.65 | 0.954 | 0.943 |
| Familia King | 28.22 | 38.88 | 0.971 | 0.988 |
| Familia Knowles | 26.96 | 27.98 | 0.975 | 0.965 |
| Familia Roy | 27.01 | 31.68 | 0.969 | 0.982 |
| Media | 26.77 | 31.05 | 0.967 | 0.970 |

El PSNR mejoró en las cuatro fotos y el SSIM en dos. En las fotos del campamento y de Knowles el detector marcó parte de la textura como daño y el relleno bajó un poco el SSIM. La mejora media del SSIM es de solo 0,003. Los arañazos oscuros se encuentran ejecutando el detector sobre la imagen invertida con sus puntuaciones a la mitad. Elegí ese peso con esta misma semilla. Con las semillas 11 y 23 la mejora media del PSNR sobre el detector anterior de una sola pasada fue de 0,9 dB y 0,2 dB. Todo se mide sobre daño que dibujé yo, que es más fácil que el desgaste real, así que léelo como una prueba de regresión y no como una promesa sobre tus fotos.

**Separar.** Las copias de ejemplo se colocan de cuatro en cuatro por escaneo, sobre tres fondos y con ángulos aleatorios. Se encontraron las 12 copias, IoU medio 0,952, el peor 0,931.

**Velocidad.** Una ejecución por dispositivo tras calentar, con todos los pasos activos salvo separar, recuperación de tono forzada y ampliación 2x.

| Dispositivo | Tamaño de imagen | fade | repair | faces | color | ampliar | total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 5090 | 960 x 1200 | 0.07 s | 0.40 s | 0.22 s | 0.06 s | 1.51 s | 2.26 s |
| Ryzen 5 7500F, CPU | 480 x 600 | 0.02 s | 9.26 s | 12.32 s | 1.87 s | 81.80 s | 105.27 s |

La fila de la CPU usa una imagen más pequeña porque el tamaño completo tarda demasiado, así que las dos filas no se pueden comparar por tamaño. Sin la ampliación, que está desactivada por defecto, la CPU tarda unos 22 segundos.

## Límites

- El detector de arañazos está entrenado sobre todo con arañazos claros. Los arañazos oscuros se encuentran ejecutándolo sobre la imagen invertida con la mitad de peso, así que las líneas finas oscuras se le escapan más que las claras. Píntalas en el editor de máscara.
- En zonas con textura o suciedad el detector da falsos positivos, así bajó el SSIM en las fotos del campamento y de Knowles. La protección del 15 por ciento solo frena los peores casos.
- GFPGAN dibuja caras. Con fuerza 100 una cara puede parecer otra persona. Por eso el valor por defecto es 35, y la vista Inventado muestra dónde actuó.
- DDColor adivina el color y tiende a una dominante cálida. Trata la salida coloreada como una ilustración.
- La recuperación de tono deja las copias en sepia en gris neutro.
- El separador usa procesamiento de imagen clásico. Las copias con borde blanco sobre una tapa de escáner blanca pueden recortarse mal. Corrige el contorno arrastrando las esquinas.
- La demo en vivo es una reproducción de resultados precalculados. Solo reaccionan los controles de caras y de color.

## Comparación con otras herramientas

Bringing Old Photos Back to Life, GFPGAN, LaMa y Real-ESRGAN son los modelos que hacen el trabajo aquí, cada uno es un repositorio de investigación aparte con su propia línea de comandos. Unfaded no mejora ninguno. Lo que añade es el montaje: un comando para un escaneo entero, una regla para omitir pasos que harían daño, una vista de cambios por paso y un registro de lo que inventaron los modelos.

## Estructura del proyecto

```
src/unfaded/        flujo, un módulo por paso, servidor, benchmark
src/unfaded/web/    interfaz y 9 archivos de idioma
demo/               resultados precalculados para la demo de GitHub Pages
examples/           fotos de dominio público y escaneos dañados, con fuentes
docs/               instalación, uso, configuración, arquitectura
tests/              pruebas unitarias, de navegador y de extremo a extremo que necesitan los pesos
```

Las notas de diseño están en [docs/architecture.md](docs/architecture.md), las reglas de contribución en [CONTRIBUTING.md](CONTRIBUTING.md) y las licencias de los modelos en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Licencia

MIT. Los pesos de los modelos conservan sus propias licencias, indicadas en el archivo de avisos.

Assisted by Claude/Codex.
