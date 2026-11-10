# ASSETS-CREDITS — Provenance de todos os assets do "Escritório Vivo"

> Higiene de provenance (padrão Nephy): cada asset do frontend tem origem, licença,
> data de aquisição e uso pretendido documentados. Nenhum asset entra no build sem registro aqui.
> Última atualização: 17/09/2026 (Fase 0 — MORGANA).

---

## 1. Packs Kenney CC0 (isométricos) — baixados na Fase 0

Salvos em `public/assets/kenney/<pack>/` (ZIP original + extração completa).
**Ainda NÃO substituem os assets atuais** — substituição é trabalho da Fase 3, que atualizará este arquivo.

Licença: **Creative Commons Zero (CC0 1.0 Universal)** — uso livre em projetos pessoais,
educacionais e comerciais, sem atribuição obrigatória. Crédito ao Kenney (kenney.nl) é apreciado, não exigido.
Cada pack inclui seu próprio `License.txt` original — fonte primária da licença.

| Pack | Origem | Licença | Baixado em | Conteúdo | Uso pretendido (Fase 3) |
|---|---|---|---|---|---|
| Isometric Miniature Prototype (v1.0, ex-"Isometric Prototype Tiles") | https://kenney.nl/assets/isometric-miniature-prototype | CC0 | 17/09/2026 | 651 PNGs (3,1 MB) + personagens (8 direções/3 animações) + samples Tiled/Unity. Paredes, pisos, blocos, colunas, portas em vistas `Angle/` e `Isometric/` | Paredes e pisos base do escritório; auto-tiling por bitmask |
| Isometric Miniature Library (v1.0, ex-"Isometric Library Tiles") | https://kenney.nl/assets/isometric-miniature-library | CC0 | 17/09/2026 | 291 PNGs (5,3 MB) + samples. Estantes com livros, escadas, mesas, cadeiras | Estantes/bookshelves do escritório (sala de reuniões, decoração) |
| Isometric Miniature Dungeon (v1.0, ex-"Isometric Dungeon Tiles") | https://kenney.nl/assets/isometric-miniature-dungeon | CC0 | 17/09/2026 | 747 PNGs (13,2 MB) + personagens + samples. Móveis (barris→plantas/potes), mesas, escadas, paredes com móveis embutidos | Mobília diversa e propriedades visuais (mesas, objetos de decoração) |

### Downloads (verificação)

| Arquivo | Tamanho | SHA-256 (16 primeiros) |
|---|---|---|
| `kenney/kenney_isometric-miniature-prototype.zip` | 3.538.637 B (3,4 MB) | `8f35b991d0bad7eb` |
| `kenney/kenney_isometric-miniature-library.zip` | 5.819.017 B (5,5 MB) | `e8ac573b289e04d0` |
| `kenney/kenney_isometric-miniature-dungeon.zip` | 14.211.485 B (13,6 MB) | `187a0888451317fe` |

Links diretos usados (padrão kenney.nl/media/pages, hash de versão no caminho):
- https://kenney.nl/media/pages/assets/isometric-miniature-prototype/8c46fe34a0-1674932174/kenney_isometric-miniature-prototype.zip
- https://kenney.nl/media/pages/assets/isometric-miniature-library/577e09ff09-1674932086/kenney_isometric-miniature-library.zip
- https://kenney.nl/media/pages/assets/isometric-miniature-dungeon/bdcbf8d79d-1674932261/kenney_isometric-miniature-dungeon.zip

Estrutura interna comum: `Angle/` (tiles em ângulo N/E/S/W), `Isometric/` (projeção isométrica),
`Characters/`, `Samples/` (mapas Tiled/Unity), `License.txt`, `Preview.png`, `Sample.png`.

### Crédito Kenney

> Assets by Kenney (kenney.nl) — license CC0. Crédito não obrigatório, mas dado aqui
> por cortesia e higiene de provenance.

---

## 2. Assets atuais (ativos na build) — pixel-agents / JIK-A-4

Salvos em `public/assets/{characters,furniture,floors,walls,carpets,pets,sprites,tiles}/`.
Origem: projeto **pixel-agents** de Pablo De Lucca (licença MIT do código; assets de arte abaixo).

### 2.1 Personagens (characters/) e pets (pets/)

- **Origem:** "MetroCity — Free Top Down Character Pack" por **JIK-A-4**
  https://jik-a-4.itch.io/metrocity-free-topdown-character-pack
- **Licença:** pack gratuito, "Credits are not necessary but would be appreciated"
  (palavras do autor no perfil https://itch.io/profile/jik-a-4). Uso livre declarado.
- **Data de aquisição:** herdado do pixel-agents (importado para o Hermes-Corp em 15/09/2026).
- **Uso:** personagens/pets top-down 16×32 do escritório atual. Na Fase 3 serão substituídos
  ou complementados por sprites Kenney (isométricos).

### 2.2 Móveis, pisos, paredes, tapetes (furniture/, floors/, walls/, carpets/)

- **Origem:** asset pack "MetroCity — Free Top Down Interior Asset Pack" por **JIK-A-4**
  https://jik-a-4.itch.io/metrocity (Interior.rar) e ambiente externo em
  https://jik-a-4.itch.io/metro
- **Licença:** mesma do §2.1 — free, crédito apreciado não exigido.
- **Uso:** mobília/piso/parede/tapete top-down atuais (auto-tiling de paredes por bitmask,
  port do `wallTiles.ts` do pixel-agents — BLUEPRINT §4.3). Fase 3 substitui pelos Kenney CC0.

### 2.3 Sprites UI (sprites/avatars, sprites/ui)

- **Origem:** geração interna/da comunidade pixel-agents; ver manifestos em
  `public/assets/` e `docs/external-assets.md` do pixel-agents.
- **Uso:** avatares HUD e ícones de chat/meeting.

---

## 3. Regras de uso

1. **Nada entra no build sem linha neste arquivo.** Novo asset → nova linha com origem+licença+data.
2. CC0 e "credit appreciated" não exigem atribuição no jogo, mas mantemos o registro aqui (provenance hygiene).
3. Fase 3 (Morgana): ao substituir assets atuais pelos Kenney, marcar os itens do §2 como
   "REMOVIDO EM <data> — ver histórico git" e manter este arquivo como fonte da verdade.
4. Quarentena Habbo (`40-Arquivo/quarentena-assets-2026-09/`) continua FORA do frontend — decisão da reunião de 17/09.
