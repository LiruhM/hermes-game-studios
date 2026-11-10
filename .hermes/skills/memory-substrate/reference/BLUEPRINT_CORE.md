# BLUEPRINT CORE — Reconstrução do Núcleo de Jogo (Hermes-Corp)

> **Escopo:** reconstrução do NÚCLEO DO JOGO (colisão, pathfinding, renderização em camadas, protocolo WS) do escritório isométrico Hermes-Corp, usando o pixel-agents (clone local `C:/Users/mathe/pixel-agents-temp`) como fonte primária.
> **Fora de escopo (intacto):** diálogo NPC (`npc.dialogue.request/response`), chat, reuniões, `start_stack.sh`/`stop_stack.ps1`, assets de sprites.
> **Hardware alvo:** Ryzen 7 5700U, 12GB RAM, Windows 11 — arquitetura leve, sem dependências pesadas.
> **Fontes deste documento:** `comparison_report.json` (20 correções), `overlap_analysis.json` (7 causas de sobreposição), `analysis_result.json` (causa raiz do "No path found"), `game_server.py` (1498 linhas) e `frontend/src/`.

---

## 1. PRINCÍPIOS

Três princípios governam toda a reconstrução. Qualquer implementação que viole um deles está errada, mesmo que "funcione".

### 1.1 Autoridade do servidor (server-authoritative)

- **O servidor é a única fonte de verdade** sobre posições, colisão e caminhos. O cliente **nunca** calcula pathfinding; apenas interpola posições já validadas.
- Todo clique de movimento: cliente envia `move.request` → servidor valida origem/destino contra o grid autoritativo → servidor calcula o caminho (BFS) → servidor envia `move.path` com a lista completa de tiles → cliente apenas anima a travessia tile a tile (interpolação por delta-time).
- Se o servidor rejeita (destino bloqueado, sem caminho), responde `move.rejected` com motivo; o cliente NÃO move o sprite.
- **Causa raiz do bug "No path found" (não repetir):** o servidor marcava a própria posição do jogador como bloqueada no `collision_grid` (`move_entity`, linha ~451) e enviava esse grid no welcome; o cliente então falhava no `isWalkable(start)`. No novo núcleo, **o tile do jogador nunca entra no grid de colisão** (ver §2.4), eliminando a classe inteira de bug.
- NPCs seguem o mesmo modelo: servidor decide o próximo passo do NPC e transmite; cliente só renderiza.

### 1.2 Camadas de render explícitas (explicit render layers)

- Nada de "painter's algorithm" implícito com uma única lista ordenada por Y. Todo drawable tem uma **camada explícita** (`LAYER_*`), e **dentro** de cada camada os itens são ordenados por screen Y (§4).
- As 7 causas de sobreposição de sprites (`overlap_analysis.json`) derivam todas de uma raiz comum: renderizar tudo numa passada só, ordenar por tile Y (não screen Y), paredes todas após entidades, móveis multi-tile como um único retângulo. O sistema de camadas + sort por screen Y per tile elimina a classe inteira.
- Cada drawable carrega `zIndex` opcional em meta para override manual (itens voadores, overlays).

### 1.3 Colisão separada de visual

- **Colisão** é um conceito de mundo (`tileMap` + `blockedTiles`, §2). **Visual** é um conceito de tela (camadas, §4). Eles NUNCA se derivam um do outro:
  - Um tapete (carpet) é visual na `LAYER_FLOOR` mas não bloqueia nada.
  - As `backgroundTiles` de uma mesa (fileiras do topo do footprint) são VISUALMENTE desenhadas na frente do personagem que anda atrás, mas a colisão as trata como caminháveis.
  - Um móvel de 1 tile de footprint pode ter sprite alto (estante) — a altura visual afeta sort, nunca colisão.
- A regra prática: mudar arte/sprite JAMAIS muda o comportamento de colisão; mudar footprint (no manifest) muda colisão e apenas colisão.

### 1.4 Restrições de leveza (Ryzen 5700U / 12GB)

- Servidor: Python puro (websockets/stdlib), BFS com `collections.deque` — sem numpy, sem scipy.
- Cliente: Canvas 2D puro, zero bibliotecas de render. `requestAnimationFrame` único; sort por frame limitado a entidades + tiles visíveis (culling por câmera).
- Grid ≤ ~40×40 tiles por sala; BFS é O(V+E) ≈ instantâneo nesse tamanho.
- Payloads WS compactos (arrays de tiles, não objetos aninhados) — ver §5.

---

## 2. MODELO DE COLISÃO

Modelo derivado do pixel-agents: `tileMap` + `blockedTiles` + `backgroundTiles`, com VOID para fora do escritório. Substitui o `collision_grid` monolítico atual (paredes+portas+móveis+jogador tudo num boolean[][], que foi a raiz do "No path found").

### 2.1 `tileMap` — camada base de pisos (TileType)

Grid 2D `tileMap[row][col]` com tipos de tile (equivalente ao enum TileType do pixel-agents):

| Valor | Tipo | Caminhável? |
|-------|------|-------------|
| `0` | `WALL` — parede | **NÃO** |
| `1..9` | `FLOOR_1..FLOOR_9` — pisos | SIM |
| `255` | `VOID` — fora do escritório | **NÃO** |

- O perímetro e paredes internas são gravados no `tileMap` como `WALL` no momento da construção da sala (nada de `INTERNAL_WALLS` processados a cada rebuild).
- Área fora do retângulo da sala ou não-piso = `VOID`. O check de caminhabilidade inclui VOID explicitamente — não basta o bounds-check atual.
- **O `tileMap` é imutável durante a execução** (só muda se a sala for editada). Isso o torna cacheável e serializável no welcome payload.

### 2.2 `blockedTiles` — ocupação dinâmica de móveis

`Set<string>` de chaves `"col,row"` com todos os tiles ocupados por móveis:

- Construído por `get_blocked_tiles()` a partir dos móveis instanciados: para cada móvel, o footprint (`footprintW × footprintH` do manifest `manifest.json` de cada móvel em `frontend/public/assets/`) é percorrido tile a tile.
- **Exceção `backgroundTiles`:** as fileiras do topo do footprint declaradas como background (ex.: cadeira embutida atrás da mesa) são **puladas** — o personagem anda ali (fica "atrás" do móvel visualmente, §4.6). Número de fileiras vem do manifest (`backgroundTiles`), igual ao `getBlockedTiles()` do `layoutSerializer.ts`.
- NPCs: cada NPC adiciona seu tile atual a `blockedTiles` enquanto parado; **ao andar, remove o tile de origem antes de adicionar o de destino** (nunca ambos).
- `is_walkable(col, row)` = `tileMap[row][col] ∈ {FLOOR_*}` **E** `"col,row" ∉ blockedTiles`. Uma única implementação, no servidor (§3).

### 2.3 Supressão do que NÃO bloqueia

- **Tapetes/carpetas:** puramente visuais (`LAYER_FLOOR`), zero efeito em colisão.
- **Portas:** o tile da porta é `FLOOR_*` no `tileMap` (nunca `WALL`), apenas visualizado com frame próprio.
- **Zonas de área/reunião:** overlays visuais, não bloqueiam.

### 2.4 O jogador NUNCA bloqueia o próprio tile (regra absoluta)

- **Jogadores não entram em `blockedTiles` nem em nenhuma estrutura de colisão.** Dois jogadores podem visualmente ocupar tiles adjacentes ou até o mesmo tile (separados por offset visual, §4.7); a colisão jogador-jogador não existe (igual ao Habbo/pixel-agents).
- Isso elimina a raiz do bug "No path found": não existe mais o estado "grid diz que meu tile está bloqueado", pois nenhum código pode marcar o tile de um jogador.
- NPCs continuam bloqueando (são parte do cenário previsível), mas o pathfinding do servidor os contorna; NPCs cedem o tile quando começam a andar.

### 2.5 Estrutura de dados no servidor (game_server.py)

```python
class Room:
    tile_map: list[list[int]]        # TileType, imutável pós-build
    blocked_tiles: set[str]          # "col,row" — móveis + NPCs parados
    # REMOVIDO: collision_grid: list[list[bool]] (apagado por completo)

    def is_walkable(self, col, row) -> bool:
        if not (0 <= row < self.height and 0 <= col < self.width): return False
        t = self.tile_map[row][col]
        if t == WALL or t == VOID: return False
        return f"{col},{row}" not in self.blocked_tiles
```

- No welcome payload (§5) o cliente recebe `tileMap` (uma vez por sala) + `blockedTiles` (array de `"col,row"`) — nunca um boolean grid derivado.
- Cliente usa **cópia local de leitura** desses dados apenas para feedback visual (cursor de destino válido/inválido); nunca para calcular caminho.

---

## 3. PATHFINDING

**Uma única implementação, no servidor** (`pathfinding.py`). O cliente NÃO tem algoritmo de path — só animação. O BFS 4-direções do pixel-agents (`tileMap.ts → findPath()`) é portado para Python puro.

### 3.1 Algoritmo — BFS 4-direções (igual ao pixel-agents)

- Vizinhança: **4-direções apenas** (N/S/L/O). Sem diagonais — elimina todo o problema de "canto cortado" e simplifica a interpolação.
- Estrutura: `collections.deque` como fila + `dict` de predecessores (`came_from[(col,row)] = (prev_col,prev_row)`). Sem `heapq`, sem numpy.
- **Sem limite de expansão artificial:** em grid ≤ 40×40 o BFS visita no máximo ~1600 tiles — O(V+E) instantâneo (~<1ms no 5700U). Nada de `maxRadius=5` como o `findNearestWalkable` atual.
- Early-exit quando o destino é desenfileirado (destino é garantido caminhável pelo §2; se não for, rejeita antes de buscar — ver §3.2).

```python
def find_path(room, start, goal):
    if start == goal:
        return [start]
    if not room.is_walkable(*goal):
        return None                      # -> move.rejected: destination_blocked
    if not room.is_walkable(*start):
        return None                      # não deve ocorrer (§2.4), mas é defensivo
    came_from, queue = {start: None}, deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            path = []
            while cur is not None:
                path.append(cur); cur = came_from[cur]
            return path[::-1]
        for d in ((0,-1),(0,1),(-1,0),(1,0)):
            nxt = (cur[0]+d[0], cur[1]+d[1])
            if nxt not in came_from and room.is_walkable(*nxt):
                came_from[nxt] = cur
                queue.append(nxt)
    return None                          # -> move.rejected: no_path
```

### 3.2 Fluxo de um clique de movimento (fim a fim)

1. Cliente: clique → converte screen→tile (projeção inversa do iso) → envia `move.request {entityId, targetCol, targetRow}`.
2. Servidor (`rooms.py`): valida entidade existe e pertence à sala → `start = (ent.col, ent.row)` → `find_path(room, start, goal)`.
3. Caminho encontrado → estado da entidade vira `walking` com `path` e `step_progress` → servidor transmite **`move.path`** (§5) a todos da sala.
4. Servidor avança a entidade tile a tile por **tick** (ver §3.3), transmitindo `entity.move` a cada tile concluído.
5. Caminho não encontrado → **`move.rejected {entityId, reason}`** só para o solicitante; cliente mantém o sprite parado e mostra toast discreto.
6. NPCs: mesma `find_path`; o servidor decide destinos (comportamento existente de wander/NPC fica intacto) e usa as mesmas mensagens.

### 3.3 Avanço server-side por tick (autoritativo)

- O servidor tem um tick de lógica (ex.: 10 Hz) que avança TODAS as entidades em movimento 1 tile por `MOVE_TIME` (ex.: 350ms/tile, constante compartilhada com o cliente no welcome).
- Posição contínua autoritativa: `col + progress*dx`. O cliente recebe `move.path` UMA vez e interpola localmente por delta-time na MESMA velocidade; `entity.move` por tile serve de **âncora de correção** (se o cliente divergir >½ tile, teleporta suavemente para a âncora).
- Ao iniciar o passo, um NPC **remove o tile de origem de `blockedTiles`** e só adiciona o de destino ao concluir (§2.2) — nunca bloqueia dois tiles simultaneamente.
- Chegada ao destino: estado → `idle`, broadcast `entity.move` final com `moving:false`.

### 3.4 O que o cliente faz (e NÃO faz)

- **FAZ:** recebe `move.path`, anima sprite tile a tile (interpolação linear entre tiles, `requestAnimationFrame`), escolhe o frame de direção pela delta do tile (4 direções), predição local irrestrita com snap nas âncoras `entity.move`.
- **NÃO FAZ:** `findPath`, `isWalkable` para decisão (só para cursor de destino), `findNearestWalkable`, qualquer fallback de path. `frontend/src/world/pathfinding.js` é **apagado** (§6).

### 3.5 Mensagens de path/move no protocolo (resumo; payload completo na §5)

- `move.request` (C→S) — clique do jogador.
- `move.path` (S→C, broadcast) — caminho completo como `[[col,row],...]`, hora em que o servidor começou.
- `entity.move` (S→C, broadcast) — âncora por tile; também usado por movimentos de NPC.
- `move.rejected` (S→C, unicast) — com `reason ∈ {destination_blocked, no_path, too_far}`.

---

## 4. CAMADAS DE RENDER

Implementação no cliente (`frontend/src/render/`). Constantes exatas:

```javascript
const LAYER_FLOOR          = 0;   // pisos + tapetes + overlays de área
const LAYER_WALLS_BEHIND   = 1;   // paredes norte/oeste
const LAYER_FURNITURE_LOW  = 2;   // móveis de altura 1 (cadeiras, plantas)
const LAYER_FURNITURE_HIGH = 3;   // móveis altura 2+ (estantes, armários)
const LAYER_ENTITIES       = 4;   // jogadores, NPCs
const LAYER_WALLS_FRONT    = 5;   // paredes sul/leste
const LAYER_DOORS          = 6;   // portas (Y-sorted dentro da camada)
const LAYER_UI             = 10;  // cursores, tooltips, headicons
```

### 4.1 Ordem do pipeline por frame (renderScene)

1. Culling por câmera: apenas tiles/móveis/entidades visíveis entram na lista.
2. `LAYER_FLOOR` desenhado direto (sem sort — ordem de varredura é suficiente).
3. `LAYER_WALLS_BEHIND` desenhado direto.
4. **Camadas 2–6 entram numa lista ÚNICA e são ordenadas por `screenY`** (ver §4.2) — é o sort "unificado" do pixel-agents.
5. `LAYER_UI` desenhado por cima, por último.
- `zIndex` em `meta` (Princípio 1.2) sobrepõe a camada do drawable: um item voando sobre mesa usa `zIndex` do dono da superfície + 0.5.

### 4.2 Sort por screen Y (não tile Y)

- **Chave de sort de TODA entidade/móvel-per-tile/porta:** `screenY = iso.tileToScreen(x + 0.5, y + 0.5).y`. Em isométrico, `screenY` depende de X **e** Y — ordenar por `position.y` puro é a causa nº 2 das sobreposições (`overlap_analysis.json`).
- Móveis multi-tile são fatiados **per-tile** (§4.4): cada tile do footprint é um drawable independente com seu próprio `screenY`.
- Itens sobre mesa (`canPlaceOnSurfaces`): `screenY = screenY_da_mesa + 0.5` (ordem estável os mantém acima da mesa).
- Cadeira com encosto voltado para a câmera (`orientation: back`): `screenY = (tileY + footprintH) * TILE_SIZE + 1` — o encosto cobre o personagem sentado (correção nº 9 do `comparison_report`).

### 4.3 Paredes — behind × front

- Classificação pela geometria isométrica: **norte e oeste = behind** (desenha antes das entidades), **sul e leste = front** (desenha depois). Hoje T ODAS as paredes desenham após as entidades — causa nº 1 das sobreposições.
- Implementação: `renderWalls(room, side)` com `side ∈ {behind, front}`; o pipeline chama `behind` na fase 3 e `front` dentro da lista unificada da fase 4.
- Frames modulares (canto, reto, batente de porta) vêm do manifest de sprites — nenhuma peça de parede é desenhada proceduralmente.

### 4.4 Móveis per-tile (nunca grupo)

- Cada móvel vira N drawables (um por tile do footprint), cada um com `screenY` próprio calculado do SEU tile — nunca do centro do grupo (causa nº 3).
- **backgroundTiles** (§2.2): o personagem que anda nas fileiras de fundo do móvel deve aparecer **atrás** delas. Isso emerge naturalmente do sort per-tile: nessas fileiras o tile do móvel tem `screenY` maior que o do personagem, então o móvel desenha depois (na frente). Nenhum caso especial é necessário — o mesmo sort resolve.
- Altura do móvel (`meta.furniture_height`, default 1): 1 → `LAYER_FURNITURE_LOW`, 2+ → `LAYER_FURNITURE_HIGH`. A altura afeta apenas camada visual — nunca colisão (Princípio 1.3).

### 4.5 Portas

- Tile da porta é `FLOOR_*` na colisão (§2.3); visualmente o frame de porta desenha em `LAYER_DOORS`, mas participa da **mesma lista unificada com sort por `screenY`** — nunca "depois de tudo". Isso elimina a causa nº 6 (portas sem Y-sort cobrindo entidades).

### 4.6 Entidades e separação visual

- Entidades ordenadas por `screenY` do seu tile centro (`x+0.5, y+0.5`), camada `LAYER_ENTITIES` dentro da lista unificada.
- Offset visual anti-pilha: base ±8px + componente por tile (`offsetX += (col % 3) * 2 - 2`), quando dois jogadores dividem visualmente o mesmo tile (permitido — §2.4). Offset é só de render; nunca afeta posição lógica.

### 4.7 Leveza

- Um único `requestAnimationFrame`; lista unificada ≤ ~600 drawables após culling em sala 40×40; sort é `Array.prototype.sort` (V8 TimSort) — desprezível. Zero libs de render; Canvas 2D puro.

---

## 5. PROTOCOLO WS CONGELADO

**CONGELADO:** esta seção é o contrato. Nenhum implementador adiciona, remove ou renomeia campos sem atualizar este documento. Envelope único: `{"type": "<nome>", ...payload}` — JSON sobre WS, UTF-8. Formato de tile: par `[col, row]` (arrays, nunca objetos). Posições contínuas: `{"x": <col+0.5 pode ser fracionado>, "y": <row>}` apenas quando marcado.

### 5.1 Cliente → Servidor

| type | payload | resposta/efeito |
|------|---------|-----------------|
| `client.hello` | `{"name": str, "characterKey": str}` | registra o jogador; dispara `welcome` (unicast) + `entity.spawn` (broadcast) |
| `move.request` | `{"entityId": str, "targetCol": int, "targetRow": int}` | `move.path` (broadcast) ou `move.rejected` (unicast) |
| `chat.message` | `{"content": str}` | `chat.message` ecoada em broadcast (com `from`, `fromName`, `timestamp`) |
| `npc.dialogue.request` | `{"npcId": str}` | `npc.dialogue.response` (unicast) — **já existe, intacto** |
| `meeting.*` | payload atual (join/leave/speak/…) | eco atual — **já existe, intacto** |
| `ping` | `{}` | `pong` (unicast) |

### 5.2 Servidor → Cliente

| type | payload |
|------|---------|
| `welcome` | `{"entityId", "name", "room": {id, name, width, height, "tileMap": int[][], "blockedTiles": ["col,row",…], "doors": [{"col","row","orientation","targetRoom"}], "furniture": [...], "carpetTiles": [...]}, "entities": [entidade…], "moveTimeMs": 350, "serverTime": epoch_ms}` |
| `world.sync` | `{"entities": [...], "serverTime"}` — snapshot completo, enviado na (re)conexão |
| `entity.spawn` | `{"entity": {id, type, name, col, row, characterKey, meta}}` |
| `entity.despawn` | `{"entityId": str, "reason": "left"\|"kicked"}` |
| `entity.move` | `{"entityId", "col", "row", "moving": bool, "dir": "n"\|"s"\|"e"\|"w", "serverTime"}` — âncora por tile (§3.3) |
| `move.path` | `{"entityId", "path": [[col,row],…], "startedAt": epoch_ms, "moveTimeMs": int}` |
| `move.rejected` | `{"entityId", "targetCol", "targetRow", "reason": "destination_blocked"\|"no_path"\|"too_far"}` |
| `world.state.delta` | `{"changes": [{"op": "add"\|"remove"\|"update", "kind": "blockedTile", "col", "row"}], "serverTime"}` — deltas de `blockedTiles` (NPC parou/andou, móvel movido) |
| `chat.message` | `{"from", "fromName", "content", "timestamp"}` |
| `npc.dialogue.response` | payload atual — **já existe, intacto** |
| `meeting.*` | payloads atuais — **já existem, intactos** |
| `error` | `{"code": str, "message": str}` — ex.: `{"code": "invalid_move", "message": "…"}` |
| `pong` | `{"serverTime": epoch_ms}` |

### 5.3 Regras do protocolo

- **`tileMap` vai UMA vez por sala** (no `welcome`/`world.sync`), como array de ints — o cliente cacheia. `blockedTiles` é array de strings `"col,row"` na entrada; depois disso, mudanças chegam só via `world.state.delta`.
- **Não existe mais `collision_grid` no wire.** Qualquer payload boolean-grid é proibido — é a raiz do bug "No path found" (§1.1).
- Mensagens intactas (`npc.dialogue.*`, `chat.message`, `meeting.*`) mantêm os payloads atuais exatamente como estão — a reconstrução não pode quebrar o que funciona.
- `serverTime` em toda mensagem de movimento/estado: base para interpolação e reconciliação de clock (offset calculado no welcome).
- Compatibilidade: o servidor ignora `type` desconhecido com `error code=unknown_type` (não derruba a conexão) — permite rollout incremental cliente/servidor.
- Tamanho: `welcome` de sala 40×40 ≈ 20KB (tileMap) — aceitável UMA vez; mensagens por tile (`entity.move`) ≈ 80 bytes. Sem gzip obrigatório no 5700U.

---

## 6. ESTRUTURA DE ARQUIVOS ALVO

### 6.1 Servidor — `game_server.py` (1498 linhas) é DIVIDIDO em 5 módulos

```
game_server.py     → APAGADO (conteúdo migrado e dividido)
server.py           → NOVO — main: argparse, loop websockets, conexões, ping/pong, despacho de mensagens
rooms.py           → NOVO — Room (tileMap, blockedTiles, furniture, tick de movimento §3.3), RoomManager
pathfinding.py     → NOVO — find_path BFS (§3.1), sem estado; função pura (room, start, goal) → path
protocol.py        → NOVO — dicionário HANDLERS {type: handler}; serialização welcome/delta; constantes MOVE_TIME
entities.py        → NOVO — Entity dataclass (id, type, name, col, row, characterKey, meta, path, step_progress)
```

- **`start_stack.sh`/`stop_stack.ps1` apontam para `python server.py`** — são eles que mudam (uma linha), nada mais.
- Regra: `pathfinding.py` não importa `rooms.py` (função pura recebe room); `protocol.py` não conhece lógica, só despacho; `server.py` ≤ 200 linhas.

### 6.2 Frontend — `src/` reorganizado em `render/`, `world/`, `net/`

```
frontend/src/render/     → NOVO — camadas (§4): layers.js (constantes), renderer.js (pipeline, culling, sort unificado),
                           walls.js (behind/front), furniture.js (per-tile + manifest), doors.js, entities.js (sprites+frames), camera.js, iso.js (tileToScreen e inverso)
frontend/src/world/      → NOVO — estado local: worldState.js (entidades, paths, blockedTiles cópia de leitura),
                           movement.js (interpolação por delta-time + âncoras entity.move, §3.3/3.4)
frontend/src/net/        → NOVO — wsClient.js (conexão, reconnect, ping/pong, clock offset),
                           messageTypes.js (espelha §5, gerado à mão a partir desta seção), handlers.js (aplica world.sync/delta/path/anch)
```

- `world/pathfinding.js` → **APAGADO** (§3.4: cliente não calcula path).
- `main.js` atual → reduzido a bootstrap: monta câmera, registra handlers, inicia `wsClient`; a lógica de render/movimento migra para os módulos acima.
- Cada módulo expõe uma classe ou conjunto de funções puras; import via ES modules nativo (sem bundler obrigatório — o `npm run dev`/build atual continua funcionando).

### 6.3 INTACTO — ninguém toca

- **Diálogo NPC** (`npc.dialogue.request/response` handlers no servidor; UI de diálogo no cliente).
- **Chat** (`chat.message` + UI de chat).
- **Reuniões** (todos os `meeting.*`).
- `start_stack.sh` / `stop_stack.ps1` (só a linha do `python game_server.py` → `python server.py`, §6.1).
- **Assets:** todos os sprites em `frontend/public/assets/` + o manifest de 43 entradas (`manifest.json`, com footprintW/H, backgroundTiles, isDesk, canPlaceOnSurfaces, category, orientation por móvel — correções nº 13/15 do `comparison_report`). A renderização nova CONSOME o manifest; ninguém edita os PNGs.
- `package.json`/build config do frontend — zero dependências novas.

### 6.4 Mapeamento migração (o que virou o quê)

| Antigo (game_server.py / src atual) | Novo destino |
|---|---|
| `Room._build_collision_grid`, `collision_grid` | **apagado** → `rooms.py` (tileMap + blockedTiles, §2) |
| `Room.move_entity`, tick de movimento | `rooms.py` (tick §3.3) |
| BFS embutido / `findNearestWalkable` | `pathfinding.py` (§3.1) |
| `_handle_*` handlers de mensagem | `protocol.py` (despacho) + `rooms.py` (lógica) |
| `renderer.js` monolítico | `src/render/*` (§4) |
| `pathfinding.js` (cliente) | **apagado** → `src/world/movement.js` (interpolação) |
| conexão WS inline no `main.js` | `src/net/wsClient.js` |
| handlers de estado no `main.js` | `src/net/handlers.js` + `src/world/worldState.js` |

---

## 7. DIVISÃO DE TRABALHO — IMPLEMENTADORES A / B / C

Três implementadores trabalham em **paralelo**, cada um com posse exclusiva de arquivos. Regra de ouro: **ninguém edita arquivo que não é seu**; o único contrato entre eles é a §5 (protocolo congelado) e o manifest de assets. Dúvida sobre payload = reler §5, nunca "combinar no chat".

### 7.1 IMPLEMENTADOR A — Servidor (`server.py`, `rooms.py`, `pathfinding.py`, `protocol.py`, `entities.py`)

- **Posse exclusiva:** os 5 módulos do servidor + a linha do `start_stack.sh`/`stop_stack.ps1` (§6.1).
- **Entrega:** servidor autoritativo conforme §2 (colisão), §3 (pathfinding), §5 (protocolo).
- **Interface com os outros:** os JSONs da §5. A implementa o servidor; B e C escrevem o cliente contra essa tabela. Qualquer campo que A sinta falta → atualiza ESTE documento primeiro, código depois.
- Não toca em NENHUM arquivo de `frontend/src/`. Diálogo NPC/chat/reuniões: A move os handlers atuais para `protocol.py`/`rooms.py` sem alterar comportamento (copy-migrate, zero refatoração de lógica).

### 7.2 IMPLEMENTADOR B — Renderer + assets (`frontend/src/render/`)

- **Posse exclusiva:** tudo em `src/render/` (layers, renderer, walls, furniture, doors, entities, camera, iso).
- **Entrega:** pipeline da §4 — constantes `LAYER_*`, sort unificado por `screenY`, walls behind/front, móveis per-tile consumindo `manifest.json` (43 entradas), portas Y-sorted.
- **Interface com os outros:** lê o mundo via uma **API de leitura simples** exposta por C (`worldState.getDrawables()`): entidades {id, x, y, dir, moving}, móveis, portas, carpetTiles. B nunca abre WebSocket e nunca importa `src/net/` — se precisa de um dado, pede a API ao C.
- Enquanto C não entrega, B desenvolve contra um **mock determinístico** de `worldState` (fixture JSON com 2 salas, 10 entidades, salas de teste com paredes n/o/s/l) — o mock morre na integração.
- Não edita PNGs nem o manifest; se um sprite/manifest parece errado, reporta, não conserta.

### 7.3 IMPLEMENTADOR C — Movimento cliente + rede (`frontend/src/net/`, `frontend/src/world/`)

- **Posse exclusiva:** `wsClient.js`, `messageTypes.js`, `handlers.js`, `worldState.js`, `movement.js`, e o `main.js` reduzido a bootstrap.
- **Entrega:** conexão + clock offset, aplicação de welcome/world.sync/world.state.delta, interpolação de `move.path` com âncoras `entity.move` (§3.3/3.4), envio de `move.request`, e a API de leitura `worldState.getDrawables()` para B.
- **Interface com os outros:** consome a §5 (contra o servidor de A, ou o mock até A subir); publica a API para B e a congela no dia 1 da integração — mudanças posteriores só com aviso prévio a B.
- Não desenha nada: zero código de canvas em `src/net/` e `src/world/`. Cursor de destino válido/inválido é desenhado por B, decidido por C via `worldState.isTileLikelyWalkable()` (feedback visual, §3.4).

### 7.4 Fronteiras — tabela de "quem pode tocar o quê"

| Arquivo/dir | A | B | C |
|---|---|---|---|
| `server.py` `rooms.py` `pathfinding.py` `protocol.py` `entities.py` | **edita** | — | — |
| `frontend/src/render/**` | — | **edita** | — |
| `frontend/src/net/**` `frontend/src/world/**` `main.js` | — | — | **edita** |
| `frontend/public/assets/**` + manifest | — | lê | lê |
| diálogo NPC / chat / reuniões (lógica) | **migra intacto** | lê | lê |
| `start_stack.sh`/`stop_stack.ps1` | **edita (1 linha)** | — | — |
| BLUEPRINT §5 (protocolo) | propõe mudança | propõe mudança | propõe mudança |

### 7.5 Sequência de integração (depois do paralelo)

1. A sobe servidor + `test_client.py` (bot que conecta e loga as mensagens) — B e C apontam seus mocks/testes contra ele.
2. C conecta `wsClient` real → valida welcome/delta contra a tabela da §5.
3. B troca o mock de `worldState` pelo real → primeira imagem correta end-to-end.
4. Testes de aceite da §8 rodam na ordem A → C → B → integração.

---

## 8. CRITÉRIOS DE ACEITE VERIFICÁVEIS

Todo critério abaixo é um teste que roda num terminal ou navegador e tem resultado binário (passa/falha). Nenhum "parece certo".

### 8.1 IMPLEMENTADOR A — servidor

| # | Comando | Resultado esperado |
|---|---------|--------------------|
| A1 | `python -m pytest tests/test_pathfinding.py -q` (ou `python tests/test_pathfinding.py`) | BFS: caminho reto de 5 tiles = 5 passos; destino em `WALL`/`VOID`/`blockedTiles` → `None`; sala 40×40 com obstáculos → caminho válido < 50ms; **start = tile do jogador nunca bloqueado** |
| A2 | `python -c "from rooms import Room; r=Room(...); assert not hasattr(r,'collision_grid')"` | Falha se existir qualquer `collision_grid` — a classe foi extinta |
| A3 | `python test_client.py --room office` | Bot conecta, recebe `welcome` com `tileMap` 2D de ints + `blockedTiles` array de `"col,row"`; **nenhum campo boolean-grid no payload** |
| A4 | bot envia `move.request` para tile livre → loga `move.path`; repete para tile de parede → loga `move.rejected reason=destination_blocked`; repete após cercar o destino com móveis → `no_path` | 3 respostas corretas, zero `error` |
| A5 | bot envia `{"type":"coisa_inexistente"}` | Recebe `error code=unknown_type` e **continua conectado** |
| A6 | dois bots pedem movimento em cruzamento simultâneo | `move.path` de ambos válidos; nenhum fica preso; NPCs bloqueiam e são contornados pelo path |
| A7 | abrir 2 abas + 10 NPCs e medir: `python - <<'print CPU do processo python>>'` | Processo python < 10% CPU num núcleo do 5700U com 12 entidades andando; latência ping/pong < 20ms local |

### 8.2 IMPLEMENTADOR C — net/world

| # | Comando | Resultado esperado |
|---|---------|--------------------|
| C1 | no devtools: `grep -r "findPath\|isWalkable" frontend/src/net frontend/src/world` | Zero ocorrências de pathfinding no cliente (só `isTileLikelyWalkable` para cursor) |
| C2 | devtools console: desconectar rede → reconectar | `wsClient` reconecta sozinho, recebe `world.sync`, estado volta íntegro (contagem de entidades igual) |
| C3 | devtools console: `worldState.getDrawables().length` com 12 entidades na sala | ≥ 12 entidades + todos móveis/portas/carpetTiles; B desenha a partir disso sem chamar net |
| C4 | clicar num tile e logar `wsClient.sent` | Exatamente UM `move.request`; nenhum path calculado no cliente |
| C5 | spoof: servidor envia âncora `entity.move` deslocada 2 tiles da interpolação local | Cliente corrige (snap suave) em < 300ms — nunca "teleporta para trás" repetidamente |
| C6 | dois cliques rápidos em destinos diferentes | Segundo `move.request` substitui o path atual (ou recebe rejeição) — sem dois sprites de movimento simultâneos |
| C7 | console limpo com 2 clientes + 10 NPCs andando 60s | Zero erros JS; uso de heap estável (sem leak de handlers em reconnect) |

### 8.3 IMPLEMENTADOR B — render

| # | Comando | Resultado esperado |
|---|---------|--------------------|
| B1 | fixture `render/test_fixture.json` (entidade atrás e na frente da mesma mesa, 4 paredes) renderizada em teste headless (`node render/smoke.js` ou screenshot) | Personagem atrás da mesa é coberto pelas fileiras de fundo; personagem na frente cobre a mesa — o mesmo fixture não renderiza correto no renderer antigo |
| B2 | andar com o personagem ao longo da parede norte e depois da parede sul | Norte: parede ATRÁS do personagem; sul: parede NA FRENTE — em nenhum momento a parede some atrás do sprite |
| B3 | entidade atravessando a frente de uma porta | Frame da porta nunca cobre o sprite (causa nº 6 eliminada) |
| B4 | duas entidades no mesmo tile | Visíveis separadas pelo offset ±8px; zero mudança de posição lógica (col/row idênticos no worldState) |
| B5 | `grep -c "LAYER_" frontend/src/render/layers.js` e conferir constantes | 8 constantes exatamente como na §4 (0,1,2,3,4,5,6,10) |
| B6 | medir FPS (devtools performance) com 12 entidades + sala 40×40 | ≥ 55 FPS no 5700U; tempo de sort por frame < 1ms |
| B7 | trocar `furniture_height` de um móvel no manifest de 1→3 ( teste, revertido depois) | Camada visual muda (LOW→HIGH), colisão idêntica — Princípio 1.3 comprovado |

### 8.4 INTEGRAÇÃO — end-to-end (A+B+C)

| # | Comando | Resultado esperado |
|---|---------|--------------------|
| E1 | `./start_stack.sh` (ou `stop_stack.ps1` + start) sobe `server.py` + frontend | Stack sobe com um comando; console do servidor loga `listening` |
| E2 | abrir 2 navegadores, mover ambos, conversar no chat, dialogar com NPC, entrar em reunião | Movimento correto nos DOIS clientes; chat/diálogo/reunião funcionam **exatamente como antes** (regressão zero no que é intocado) |
| E3 | **teste do bug original:** logar como jogador, clicar no tile em que se está e em tiles adjacentes, depois atravessar a sala inteira 20× | ZERO ocorrências de "No path found" no console — o bug raiz (§1.1) está extinto por construção |
| E4 | sala com mesa multi-tile: andar por trás e pela frente em todos os lados | Personagem correto atrás/na frente em TODAS as fileiras do footprint — as 7 causas de `overlap_analysis.json` verificadas uma a uma neste cenário |
| E5 | desconectar o cliente B durante movimento do A | `entity.despawn` chega ao A; sprite some; nada de erros no servidor |

### 8.5 Definição de pronto (documento)

- Todas as células das tabelas A1–A7, C1–C7, B1–B7, E1–E5 executadas com resultado esperado confirmado por quem implementou.
- `frontend && npm run build` passa sem erros/warnings novos; nenhum arquivo de `game_server.py` restante no repo (exceto histórico git).
- Este BLUEPRINT é atualizado apenas se §5 mudar — todo o resto é imutável durante a implementação.
