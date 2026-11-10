---
name: playwright-cli-browser
description: Use para controlar o navegador real por CLI. Print e vídeo.
---

# Playwright CLI (microsoft/playwright-cli — instalado 13/10, v0.1.22 global)

## Quando usar
- Validar app/demo web de verdade (o gate de browser da casa)
- Screenshot, vídeo de navegação, extração de conteúdo
- Quando o browser-harness interno do Hermes engasgar (daemon instável — queda real de 13/10)
- Testes E2E: keyboard.down(' ') + esperar HUD/#fim + restart com 'r'

## Comandos essenciais
```bash
playwright-cli open <url>        # abre (--headed para ver)
playwright-cli find <texto>      # busca na página com refs
playwright-cli snapshot          # estado da página com refs e6, e7...
playwright-cli click <ref>       # clica por ref
playwright-cli screenshot        # print da tela
playwright-cli press <tecla>     # tecla (a, arrowleft, Enter)
playwright-cli keydown/keyup <k> # segurar tecla (segurar espaço = atacar)
playwright-cli eval "<js>"       # executa JS na página
playwright-cli video-start --fps=60  # grava vídeo da navegação
playwright-cli close             # fecha (SEMPRE fechar — zero zumbi)
```

## Pitfalls
- Headless shell pode não disparar rAF: se HUD congela, testar rAF com probe de 1s antes de culpar o jogo.
- --use-gl=angle necessário para WebGL (Three.js) no headless.
- waitForFunction(fn, undefined, {timeout}) — options são o 3º argumento.
- Sempre `playwright-cli close` no fim — processo zumbi viola a regra de limpeza.
- Para E2E programático complexo, o pacote playwright (npm) direto também serve — o CLI é o caminho rápido.
