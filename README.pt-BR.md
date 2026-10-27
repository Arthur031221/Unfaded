<div align="center">

<img src="assets/logo.svg" width="96" alt="Unfaded logo">

# Unfaded

**Restaure fotos antigas de família na sua própria GPU e veja o que cada etapa mudou.**

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml/badge.svg)](https://github.com/Arthur031221/Unfaded/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](docs/install.md)

</div>

Em quatro fotos de domínio público com arranhões que desenhei com sementes fixas, a etapa de reparo elevou o PSNR médio de 26,8 dB para 31,0 dB, e o separador achou 12 de 12 cópias em scans sintéticos, com sobreposição média (IoU) de 0,95. O PSNR melhorou nas quatro fotos. Dá para reproduzir com `unfaded bench`, e o método está em [Benchmark](#benchmark).

![Unfaded recorta quatro cópias de um scan, restaura e mostra o que cada etapa mudou](assets/demo.gif)

A [demo ao vivo](https://arthur031221.github.io/Unfaded/) usa a saída real de três scans de exemplo. Ela não processa os seus arquivos, para isso instale a ferramenta.

## Antes e depois

| | Antes | Depois |
| --- | --- | --- |
| Retrato de família com vinco, 1891 | ![Antes](assets/creased-before.jpg) | ![Depois](assets/creased-after.jpg) |
| Acampamento madeireiro, 1926 | ![Antes](assets/camp-before.jpg) | ![Depois](assets/camp-after.jpg) |

Os dois são scans de domínio público aos quais `scripts/make_demo.py` adicionou arranhões, um vinco e poeira sintéticos. Depois é o fluxo padrão: separar, tom, reparar e rostos a 35 por cento. O detector também roda sobre a imagem invertida, assim ele acha os arranhões escuros, mas ainda deixa passar algumas linhas finas escuras, veja [Limites](#limites).

Modelos inventam coisas, então fiz a ferramenta dizer isso. Toda etapa que desenhou pixels leva o rótulo "inventado pelo modelo", a visão Inventado pinta exatamente onde, e o arquivo original nunca é tocado.

## O que faz

Unfaded é um fluxo curto. Cada etapa pode ser desligada e cada uma informa quanto da cópia mudou.

| Etapa | O que acontece | Modelo | Padrão |
| --- | --- | --- | --- |
| Separar | Recorta cada cópia de um scan de mesa e a endireita. Os cantos podem ser arrastados à mão. | OpenCV, sem modelo | ligada |
| Desbotado | Restaura os níveis e remove a dominante de cor. É pulada quando a cópia já ocupa 80 por cento da faixa tonal. | nenhum | ligada |
| Reparar | Acha arranhões, vincos e poeira e os preenche. É pulada se mais de 15 por cento da cópia precisasse ser preenchida. Você pode pintar a máscara. | Detector de arranhões de fotos antigas, LaMa | ligada |
| Rostos | Restaura cada rosto com seu próprio controle deslizante. 0 mantém o rosto antigo, 100 usa o que o GFPGAN desenha. | YuNet, GFPGAN v1.4 | ligada, 35 |
| Cor | Prevê a cor de cópias em preto e branco. A luminosidade nunca muda. | DDColor | desligada |
| Ampliar | 2x ou 4x, em blocos nas cópias grandes. | Real-ESRGAN x4plus | desligada |

Cada resultado recebe um arquivo auxiliar `.xmp` com o sha256 do arquivo de origem, cada etapa com seu modelo e suas configurações, e as etapas em que um modelo gerou pixels.

## Instalação

Python 3.10 ou mais novo. Os pesos dos modelos, cerca de 1,3 GB no total, são baixados no primeiro uso e conferidos com um sha256 fixo. Depois disso nada sai da sua máquina.

<details>
<summary>Linux com uma GPU NVIDIA (testado)</summary>

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
unfaded models --fetch
```

Desenvolvi em uma RTX 5090 com torch 2.11 e CUDA 12.8.

</details>

<details>
<summary>Qualquer máquina sem GPU</summary>

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
unfaded restore scan.jpg --device cpu
```

Funciona, mas é lento, veja os tempos abaixo.

</details>

<details>
<summary>macOS e Windows (não testado)</summary>

O código não tem partes específicas de plataforma, então `pip install -e .` deve funcionar. Não o executei em nenhum dos dois sistemas. Em um Mac dá para tentar `--device mps`, `auto` só escolhe CUDA ou a CPU.

</details>

Mais em [docs/install.md](docs/install.md).

## Uso

```bash
unfaded restore examples/scans/album-damaged.jpg -o restored --explain
```

Este é o comando que executei para a demo. Ele achou quatro cópias no scan e escreveu `album-damaged.unfaded-1.jpg` até `-4.jpg`, cada uma com seu arquivo auxiliar. Na RTX 5090 levou 12 segundos, incluindo o carregamento dos modelos. `--explain` mostra o que cada etapa fez:

```
album-damaged.jpg: 4 prints
  wrote restored/album-damaged.unfaded-1.jpg
    fade              skipped   0.01s  the print already uses 92% of the tonal range
    repair       4.0% changed   5.93s
    faces        1.2% changed   1.15s
```

Mais opções:

```bash
unfaded restore album/ -o restored/            # uma pasta inteira
unfaded restore scan.jpg --colorize --scale 2  # adicionar cor e ampliar
unfaded restore scan.jpg --face-strength 60    # rostos mais fortes
unfaded split scan.jpg                         # só recortar as cópias
unfaded serve                                  # interface web local em 127.0.0.1:8765
```

A interface web mostra os contornos encontrados, deixa você corrigi-los, executa o fluxo e depois deixa você percorrer o resultado etapa por etapa com um controle de antes e depois, um mapa de calor do que mudou, uma visão Inventado, um editor de máscara e um controle de força por rosto. Tem temas claro e escuro, funciona no celular e vem em inglês, chinês tradicional, chinês simplificado, japonês, coreano, espanhol, francês, alemão e português do Brasil. Referência completa: [docs/usage.md](docs/usage.md), [docs/configuration.md](docs/configuration.md).

## Benchmark

`unfaded bench` executa tudo abaixo, com a semente 5. A saída bruta da minha execução está em [docs/benchmark.json](docs/benchmark.json).

**Reparo.** As quatro fotos de `examples/photos` são tratadas como referência limpa. Cada uma é ajustada a 1600 pixels, recebe arranhões, vincos e poeira com uma máscara conhecida, só a etapa de reparo roda e o PSNR é medido contra a imagem limpa.

| Foto | PSNR danificada | PSNR reparada | SSIM danificada | SSIM reparada |
| --- | --- | --- | --- | --- |
| Acampamento madeireiro | 24.90 | 25.65 | 0.954 | 0.943 |
| Família King | 28.22 | 38.88 | 0.971 | 0.988 |
| Família Knowles | 26.96 | 27.98 | 0.975 | 0.965 |
| Família Roy | 27.01 | 31.68 | 0.969 | 0.982 |
| Média | 26.77 | 31.05 | 0.967 | 0.970 |

O PSNR melhorou nas quatro fotos e o SSIM em duas. Nas fotos do acampamento e de Knowles o detector marcou parte da textura como dano e o preenchimento baixou um pouco o SSIM. O ganho médio de SSIM é de apenas 0,003. Os arranhões escuros são achados rodando o detector sobre a imagem invertida, com as pontuações pela metade. Escolhi esse peso com esta mesma semente. Com as sementes 11 e 23, o ganho médio de PSNR sobre o detector anterior de uma única passada foi de 0,9 dB e 0,2 dB. Tudo é medido em danos que eu mesmo desenhei, que são mais fáceis que o desgaste real, então leia como um teste de regressão e não como uma promessa sobre as suas fotos.

**Separar.** As cópias de exemplo são colocadas quatro por scan, em três fundos e com ângulos aleatórios. As 12 cópias foram achadas, IoU médio 0,952, pior caso 0,931.

**Velocidade.** Uma execução por dispositivo após o aquecimento, com todas as etapas ligadas exceto separar, recuperação de tom forçada e ampliação de 2x.

| Dispositivo | Tamanho da imagem | fade | repair | faces | cor | ampliar | total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RTX 5090 | 960 x 1200 | 0.07 s | 0.40 s | 0.22 s | 0.06 s | 1.51 s | 2.26 s |
| Ryzen 5 7500F, CPU | 480 x 600 | 0.02 s | 9.26 s | 12.32 s | 1.87 s | 81.80 s | 105.27 s |

A linha da CPU usa uma imagem menor porque o tamanho completo demora demais, então as duas linhas não são comparáveis pelo tamanho. Sem a ampliação, que vem desligada por padrão, a execução na CPU leva cerca de 22 segundos.

## Limites

- O detector de arranhões foi treinado sobretudo com arranhões claros. Os arranhões escuros são achados rodando-o sobre a imagem invertida com meio peso, então as linhas finas escuras ainda passam mais vezes que as claras. Pinte-as no editor de máscara.
- Em áreas com textura ou sujeira o detector dá falsos positivos, foi assim que as fotos do acampamento e de Knowles perderam SSIM. A proteção de 15 por cento só segura os piores casos.
- O GFPGAN desenha rostos. Com força 100 um rosto pode parecer outra pessoa. Por isso o padrão é 35, e a visão Inventado mostra onde ele atuou.
- O DDColor adivinha a cor e tende a uma dominante quente. Trate a saída colorizada como uma ilustração.
- A recuperação de tom deixa cópias sépia em cinza neutro.
- O separador usa processamento de imagem clássico. Cópias com borda branca sobre a tampa branca do scanner podem ser recortadas errado. Corrija o contorno arrastando os cantos.
- A demo ao vivo é uma reprodução de saídas pré-calculadas. Só os controles de rosto e de cor reagem.

## Comparação com outras ferramentas

Bringing Old Photos Back to Life, GFPGAN, LaMa e Real-ESRGAN são os modelos que fazem o trabalho aqui, cada um é um repositório de pesquisa separado com sua própria linha de comando. O Unfaded não melhora nenhum deles. O que ele acrescenta é a montagem: um comando para um scan inteiro, uma regra para pular etapas que fariam mal, uma visão de mudanças por etapa e um registro do que os modelos inventaram.

## Estrutura do projeto

```
src/unfaded/        fluxo, um módulo por etapa, servidor, benchmark
src/unfaded/web/    interface e 9 arquivos de idioma
demo/               saídas pré-calculadas para a demo do GitHub Pages
examples/           fotos de domínio público e scans danificados, com fontes
docs/               instalação, uso, configuração, arquitetura
tests/              testes unitários, de navegador e de ponta a ponta que precisam dos pesos
```

As notas de design estão em [docs/architecture.md](docs/architecture.md), as regras de contribuição em [CONTRIBUTING.md](CONTRIBUTING.md) e as licenças dos modelos em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Licença

MIT. Os pesos dos modelos mantêm suas próprias licenças, listadas no arquivo de avisos.

Assisted by Claude/Codex.
