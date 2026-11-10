---
name: pixel-art-forja
description: Use when drawing pixel art sprites or scenes procedurally.
---

# CARTILHA PIXEL ART — de geometria pra cluster

O erro padrão de código: desenhar FORMAS (elipses, retângulos, bandas de luminosidade). Isso gera "protótipo de Paint". Artista desenha CLUSTERS: grupos de pixels da mesma cor, esculpidos do grande pro pequeno.

## As 6 regras (extraídas por dissecação do Zerie + guias Saint11/Derek Yu)

1. CLUSTER NÃO GEOMETRIA — blocos contínuos de mesma cor; zero orphan pixels (1px isolado). Silhueta primeiro: squint test — se apertar o olho e não ler a forma, nenhum detalhe salva.
2. BONECO PEQUENO E DENSO — Orc do Zerie: 22x15px. Leitura vem de poucos pixels BEM postos. 3 tons por material, ~13 cores por boneco.
3. HUE-SHIFT — sombra puxa pro AZUL (ex.: cinza sombra (81,109,125) hue 201°), luz puxa pro AMARELO (verde luz (184,208,138) amarelado). Sombra "mesma cor mais escura" = chapado. Frio na sombra, quente na luz.
4. OUTLINE QUENTE — contorno (31,26,26) quase-preto quente, nunca preto puro; preto só em olho/pupila. Selective outlining: lado da luz pode perder outline.
5. LUZ GLOBAL 45° SUP-ESQ — nunca pillow shading (luz no meio de cada membro = "balão inflável"). Luz coerente no boneco TODO.
6. CEL-SHADING — bandas DURAS de 3 tons, zero gradiente liso/interpolado; dithering xadrez só na fronteira de banda (1-2px).

## Método que funcionou: mapa ASCII → render
Desenhar o sprite à mão como grade de caracteres (um por material/tom), validar, renderizar via PIL. Ex.: orc 17 linhas x 22 colunas. É o workflow Aseprite traduzido pro código. NÃO gerar pixels por fórmula de luminosidade — desenhar mapa explícito.

## Ferramentas no ecossistema
- Motor aprovado pelo CEO (07/10/2026): C:/Users/mathe/Downloads/TCC/ESTUDO/MOTOR_JRPG.py (1534 linhas, pygame, 3 abas: creator/bestiário/butim, itens procedurais, saves). Rodar com o python do venv Hermes (C:/Users/mathe/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe) — os Python 3.14 do sistema não têm wheel de pygame. Modo print sem janela: --demo.
- Sprites piloto salvos: Brain/10-Projetos/App-Android-Kotlin/30-qa/comparacao-assets/ (ORC-MAO4-vs-ZERIE.png = gabarito 6/10 vs Zerie 9/10; REPLICA V1-V5 = evolução cel-shading)
- Packs de referência p/ dissecação: Brain/10-Projetos/JRPG-Aetherion/assets/extract/ (zerie01, zerie02, pixel-crawler)

## Regra de processo
Iterar com visão (vision_analyze) OU dump ASCII no terminal — nunca confiar só no código. Aprovação visual do CEO é o veredito final; veredito de modelo de visão é referência.
