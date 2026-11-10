# HISTÓRICO DE ANÁLISES — Hermes-Corp

**Consolidado em 18/09/2026 pela Curadoria (Alice).** Substitui os três JSONs de análise
(`analysis_result.json`, `comparison_report.json`, `overlap_analysis.json`), apagados após esta
consolidação — todo o conteúdo está preservado abaixo.

**Contexto:** estas análises diagnósticam bugs do servidor/frontend ANTIGOS — o
`game_server.py` monolítico de 1498 linhas, o `pathfinding.js` do cliente e o `collision_grid`,
todos EXTINTOS pela reconstrução do núcleo em 17/09 (ver TOMORROW.md). Valor restante:
histórico de decisões + referências do pixel-agents para as próximas fases do plano Escritório Vivo.

---

## 1. analysis_result.json — Bug "No path found to target"

### Causa raiz

Server's Room.move_entity() marks player's new position as blocked in collision_grid (line 451: self.collision_grid[new_y][new_x] = True). This grid is sent to client in welcome payload. Client's isWalkable() returns false for player's current position, causing findPath() to fail at start position check (line 85-91 in pathfinding.js attempts to find nearest walkable but maxRadius=5 may be insufficient).

### Fixes de cliente (pathfinding.js / main.js antigos)

1. pathfinding.js: In isWalkable(), add explicit check to allow player's current position as walkable regardless of collision_grid (lines 19-29)
2. pathfinding.js: In findNearestWalkable(), increase maxRadius from 5 to 10 for larger rooms (line 178)
3. pathfinding.js: In updateCollisionGrid(), ensure player position unblocking runs for BOTH server-initialized and rebuilt grids (already at lines 254-265, verified working)
4. main.js: In moveWithPathfinding(), call updateCollisionGrid() BEFORE finding path (already done at line 244)

### Fixes de servidor (game_server.py antigo)

1. game_server.py: In Room.move_entity(), do NOT mark player's new position as blocked in collision_grid (lines 457-459). Only mark as blocked for non-player entities (NPCs, furniture)
2. game_server.py: In Room.add_entity(), ensure player is never added to collision_grid (already at line 434 but move_entity overrides it - now fixed)
3. game_server.py: In Room.rebuild_collision_grid(), ensure player position is explicitly set to walkable (False) after rebuilding (lines 420-423 added)
4. game_server.py: In _handle_hello() welcome payload, collision_grid sent to client now has player position as walkable (automatically fixed by move_entity and rebuild_collision_grid changes)

### Comandos de teste da época

    cd frontend && npm run build  # Verify client builds
    python game_server.py  # Start server
    cd frontend && npm run dev  # Start frontend dev server
    Open http://localhost:8080 and test clicking to move - should not show 'No path found to target'
    Check browser console for pathfinding debug logs

---

## 2. comparison_report.json — Hermes-Corp frontend vs Pixel Agents (comparativo detalhado)

> HERMES-CORP FRONTEND vs PIXEL AGENTS - DETAILED COMPARISON
> 
> ========================================================================
> 1. COLLISION/WALKABLE TILES DEFINITION
> ========================================================================
> 
> PIXEL AGENTS APPROACH:
> - TileType enum: WALL=0, FLOOR_1..9=1..9, VOID=255
> - isWalkable(col, row, tileMap, blockedTiles):
>   * Returns false for WALL or VOID tiles
>   * Returns false if tile in blockedTiles Set (furniture footprints)
>   * blockedTiles built from furniture via getBlockedTiles() which skips backgroundTiles rows
>   * backgroundTiles: top N rows of furniture footprint are walkable (characters walk behind desk)
> - Separate tileMap (TileType[][]) from blockedTiles (Set<string> "col,row")
> - CarpetTiles are separate visual layer, don't affect walkability
> - Wall painting directly modifies tileMap
> 
> HERMES-CORP CURRENT:
> - Room.collision_grid[y][x] = boolean (true = blocked)
> - Built in Room._build_collision_grid() from:
>   * INTERNAL_WALLS (perimeter + internal rects)
>   * DOOR_COORDS (explicitly set to walkable/false)
> - Furniture added as entities, then Room.add_entity() marks collision_grid[y][x]=true
> - NPC entities also mark collision_grid when added
> - Player position explicitly kept walkable (set to false)
> - pathfinding.js isWalkable() checks both collision_grid AND furniture entities at position
> - No concept of backgroundTiles - entire furniture footprint blocks
> 
> KEY DIFFERENCES:
> 1. Pixel Agents: tileMap defines base walkability (floor types), blockedTiles adds furniture
>    Hermes-Corp: collision_grid is monolithic - walls, doors, furniture all merged
> 2. Pixel Agents: backgroundTiles allows partial furniture walkability (chairs under desks)
>    Hermes-Corp: all furniture tiles fully block
> 3. Pixel Agents: VOID tiles (outside office) are non-walkable
>    Hermes-Corp: bounds check only, no VOID concept
> 4. Pixel Agents: carpet layer is purely visual, doesn't affect collision
>    Hermes-Corp: no carpet layer
> 
> ========================================================================
> 2. PATHFINDING INTEGRATION CLIENT/SERVER
> ========================================================================
> 
> PIXEL AGENTS:
> - Single-threaded in webview (both pathfinding and rendering in same process)
> - findPath() in tileMap.ts: BFS on 4-connected grid (no diagonals)
> - Uses isWalkable() with tileMap + blockedTiles
> - Characters.updateCharacter() calls findPath with current tileMap/blockedTiles
> - Path stored in character.path, character moves along it with moveProgress lerp
> - Server not involved - local simulation
> 
> HERMES-CORP CURRENT:
> - DUAL pathfinding: client (pathfinding.js) AND server (game_server.py Room.find_path)
> - Client: A* with diagonals (8-directional), corner-cutting prevention
> - Server: A* 4-directional only (matching pixel-agents)
> - Client moveWithPathfinding() calls pathfinder.findPath(), sends final step to server
> - Server _handle_entity_move() validates via room.move_entity() which checks collision_grid
> - Server also has cross-room pathfinding via find_cross_room_path() using DOOR_COORDS
> - PathfindRequest message type exists but client doesn't use it for regular movement
> 
> ISSUES:
> 1. Client finds path with diagonals, server validates with 4-directional -> mismatch
> 2. Client sends final destination, server moves entity directly (no step-by-step)
> 3. Server collision_grid may differ from client (race conditions, async updates)
> 4. No path synchronization - client interpolates, server authoritative but may reject
> 5. "No path found" occurs when client thinks tile walkable but server collision_grid blocks it
> 
> ========================================================================
> 3. RENDER LAYERING/Z-INDEX (VISUAL OVERLAP)
> ========================================================================
> 
> PIXEL AGENTS RENDER ORDER (renderer.ts renderScene):
> 1. renderTileGrid() - floor + wall base colors
> 2. renderCarpetLayer() - carpet junctions (between floor and furniture)
> 3. renderAreaOverlay() - area color washes
> 4. Furniture drawables collected with zY = y + spriteHeight
> 5. Characters drawables with zY = ch.y + TILE_SIZE/2 + CHARACTER_Z_SORT_OFFSET
> 6. Pets with petZY = pet.y + TILE_SIZE/2
> 7. ALL drawables sorted by zY ascending (lower = behind, higher = front)
> 8. renderAreaLabels() - centroid labels on top
> 9. Selection/highlight overlays
> 
> KEY Z-SORTING DETAILS:
> - Furniture zY = item.row * TILE_SIZE + sprite.length (bottom edge)
> - Chairs back-facing: zY = (row + footprintH) * TILE_SIZE + 1 (in front of seated char)
> - Chairs other: zY = (row + 1) * TILE_SIZE (characters render in front)
> - Surface items: zY = deskZ + 0.5 (just in front of desk)
> - Characters: bottom of tile + CHARACTER_Z_SORT_OFFSET (small bias)
> - Single unified sort across furniture + characters + pets
> 
> HERMES-CORP CURRENT (renderer.js renderRoom):
> 1. renderFloor() - floor tiles
> 2. renderFurniture() - grouped by parent_id, sorted by average Y
> 3. renderEntities() - filtered non-furniture, sorted by entity.position.y (TILE Y only!)
> 4. renderWalls() - ALL walls (north, south, east, west)
> 5. renderDoors() - door sprites
> 
> OVERLAP CAUSES (from overlap_analysis.json):
> 1. Walls render AFTER entities - north/west walls should be BEHIND entities
> 2. Entity sort uses tile Y only, but screen Y depends on both X and Y in isometric
> 3. Furniture grouped by parent, average Y sort - multi-tile furniture doesn't interleave
> 4. Entity offset only ±4px - insufficient separation
> 5. Furniture center positioning may not match visual bounds
> 6. Doors render at tile level, no Y-sort
> 7. No explicit layer system - flat painter's algorithm
> 
> ========================================================================
> 4. MISSING PIECES FOR FULL BROWSER ADAPTATION
> ========================================================================
> 
> ARCHITECTURE:
> - Pixel Agents: single process (renderer + simulation + state)
> - Hermes-Corp: split client/server + Supervisor + Memory Substrate
> - Need: clear separation of concerns, deterministic state sync
> 
> COLLISION SYSTEM:
> - Missing: backgroundTiles concept for partial furniture walkability
> - Missing: VOID tile type for out-of-bounds
> - Missing: carpet layer (visual only)
> - Missing: area tiles (visual overlays)
> - Server collision_grid rebuild doesn't match client pathfinding assumptions
> 
> PATHFINDING:
> - Missing: unified pathfinding (client predictive + server authoritative)
> - Missing: step-by-step movement with interpolation sync
> - Missing: cross-room pathfinding on client side
> - Missing: path smoothing / corner cutting consistency
> - Missing: dynamic obstacle avoidance (moving NPCs)
> 
> RENDERING:
> - Missing: explicit layer system (0=floor, 1=walls_behind, 2=furniture_low, 3=furniture_high, 4=entities, 5=walls_front, 6=doors)
> - Missing: screen-space Y sorting for entities (not tile Y)
> - Missing: per-tile furniture rendering for proper interleaving
> - Missing: CHARACTER_Z_SORT_OFFSET equivalent
> - Missing: chair back-facing z-sorting logic
> - Missing: surface item z-sorting (desk items in front of desk)
> - Missing: wall side classification (north/west behind, south/east front)
> 
> ASSETS/SPRITES:
> - Pixel Agents: manifest-driven, colorized sprites, carpet junctions, wall frames
> - Hermes-Corp: static sprites, fallback mappings, no colorization
> - Missing: dynamic sprite colorization
> - Missing: carpet junction rendering
> - Missing: modular wall frames (corners, straights, door frames)
> - Missing: furniture manifest with footprintW/H, backgroundTiles, isDesk, canPlaceOnSurfaces
> 
> NETWORK/STATE:
> - Missing: deterministic state reconciliation (client prediction + server correction)
> - Missing: entity interpolation with server authority
> - Missing: room transition state synchronization
> - Missing: NPC behavior tree sync (server runs, client renders)
> 
> ========================================================================
> RECOMMENDED FIXES PRIORITY
> ========================================================================
> 
> P0 - CRITICAL (Blocking pathfinding/rendering):
> 1. Align client/server pathfinding: both 4-directional, same collision source
> 2. Fix render order: floor -> north/west walls -> furniture (per-tile Y-sort) -> entities (screen Y-sort) -> south/east walls -> doors
> 3. Implement screen-space Y sorting for entities using iso.tileToScreen()
> 4. Split renderWalls() into behind/front passes
> 5. Furniture per-tile rendering instead of group-center rendering
> 
> P1 - HIGH (Visual correctness):
> 6. Add explicit layer constants and renderLayer() system
> 7. Add furniture_height meta for z-sorting tiers
> 8. Implement chair back-facing z-sort logic
> 9. Increase entity offset range, add tile-based component
> 10. Door Y-sorting
> 
> P2 - MEDIUM (Feature parity with Pixel Agents):
> 11. Add backgroundTiles to furniture meta (walkable top rows)
> 12. Add carpet visual layer
> 13. Add area overlay system
> 14. Modular wall frames from sprites
> 15. Sprite colorization pipeline
> 
> P3 - ARCHITECTURE (Long-term):
> 16. Client-side predictive movement with server reconciliation
> 17. Cross-room pathfinding on client
> 18. Furniture manifest system (footprintW/H, isDesk, canPlaceOnSurfaces)
> 19. NPC behavior tree client prediction / server authority split
> 20. Deterministic state snapshots for reconnection

### 1. Peças faltantes (missing_pieces)

1. Unified collision system: merge server collision_grid with client pathfinding assumptions, add backgroundTiles concept
2. Single authoritative pathfinding: either server-only with client prediction, or shared deterministic algorithm
3. Explicit render layer system with z-index constants (floor, walls_behind, furniture_low, furniture_high, entities, walls_front, doors, ui)
4. Screen-space Y sorting for all renderables using iso.tileToScreen(entity.position.x+0.5, entity.position.y+0.5).y
5. Per-tile furniture rendering instead of group-center rendering for proper interleaving with entities
6. Wall side classification: north/west walls render BEFORE entities, south/east AFTER
7. Furniture manifest with footprintW, footprintH, backgroundTiles, isDesk, canPlaceOnSurfaces, category
8. Sprite colorization pipeline (like Pixel Agents getColorizedFloorSprite/getColorizedSprite)
9. Modular wall frames (corners, straights, door frames) with proper sprites
10. Carpet visual layer between floor and furniture
11. Area overlay system for workspace zones
12. Chair back-facing z-sort logic (chair back renders in front of seated character)
13. Surface item z-sort (desk items render at deskZ + 0.5)
14. CHARACTER_Z_SORT_OFFSET constant for entity depth bias
15. Cross-room pathfinding on client side using door transitions
16. Client-side predictive movement with server reconciliation
17. Deterministic entity interpolation with server-authoritative positions
18. VOID tile type for out-of-bounds areas
19. NPC behavior tree state sync between server (authoritative) and client (visual)
20. Room transition state synchronization across client/server

### 2. Fixes recomendados (recommended_fixes)

1. Fix 1: In game_server.py Room._build_collision_grid(), add backgroundTiles support - furniture meta should include backgroundTiles, skip those rows when marking collision
2. Fix 2: In pathfinding.js isWalkable(), use screen-space check matching server: check collision_grid only, remove duplicate furniture entity check
3. Fix 3: In renderer.js renderRoom(), reorder: renderFloor() -> renderWallsBehind() (north, west) -> renderFurniturePerTile() -> renderEntitiesScreenYSorted() -> renderWallsFront() (south, east) -> renderDoorsSorted()
4. Fix 4: Add LayerManager with explicit layers: LAYER_FLOOR=0, LAYER_WALLS_BEHIND=1, LAYER_FURNITURE_LOW=2, LAYER_FURNITURE_HIGH=3, LAYER_ENTITIES=4, LAYER_WALLS_FRONT=5, LAYER_DOORS=6, LAYER_UI=10
5. Fix 5: In renderFurniture(), iterate individual furniture tiles, compute screen Y per tile via iso.tileToScreen(tileX+0.5, tileY+0.5).y, sort all tiles + entities together by screen Y
6. Fix 6: In renderWalls(), split into renderWallsBehind(room) for north/west and renderWallsFront(room) for south/east, call at correct render passes
7. Fix 7: In renderEntities(), sort by screen Y: iso.tileToScreen(e.position.x+0.5, e.position.y+0.5).y instead of e.position.y
8. Fix 8: Add furniture.meta.furniture_height (default 1), use to assign LAYER_FURNITURE_LOW (1) or LAYER_FURNITURE_HIGH (2+)
9. Fix 9: For chair furniture (category=chairs), if orientation=back, set zY = (tileY + footprintH) * TILE_SIZE + 1, else zY = (tileY + 1) * TILE_SIZE
10. Fix 10: For furniture with canPlaceOnSurfaces=true, compute deskZ from underlying desk tiles, set zY = deskZ + 0.5
11. Fix 11: In renderDoors(), sort doors by screen Y before rendering
12. Fix 12: Increase entity offset range from ±4 to ±8, add tile-based offset: offsetX += (entity.position.x % 3) * 2 - 2
13. Fix 13: Add backgroundTiles to furniture meta in ROOM_CONFIGS and game_server.py furniture creation
14. Fix 14: Implement AssetLoader colorization using canvas drawImage with globalCompositeOperation for sprite tinting
15. Fix 15: Create furniture manifest JSON (like pixel-agents) with footprint, backgroundTiles, isDesk, category, orientation
16. Fix 16: Add carpetTiles to room data, render in renderCarpetLayer() between floor and furniture
17. Fix 17: Implement cross-room pathfinding in pathfinding.js using DOOR_COORDS from server welcome payload
18. Fix 18: Add client-side movement prediction: interpolate locally, correct on server move ack
19. Fix 19: Add entity zIndex meta property for manual layer override
20. Fix 20: Add VOID tile handling in collision_grid and pathfinding bounds check

### 3. Referências no código pixel-agents

1. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/layout/tileMap.ts - isWalkable(), getWalkableTiles(), findPath() BFS
2. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/layout/layoutSerializer.ts - getBlockedTiles() with backgroundTiles, layoutToFurnitureInstances() with zY computation
3. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/layout/furnitureCatalog.ts - FurnitureCatalogEntry with footprintW/H, backgroundTiles, isDesk, canPlaceOnSurfaces, category, orientation
4. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/engine/renderer.ts - renderScene() unified zY sort, renderTileGrid(), renderCarpetLayer(), renderAreaOverlay()
5. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/engine/characters.ts - updateCharacter() pathfinding integration, CharacterState machine
6. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/types.ts - TileType enum, FurnitureInstance with zY, Character with tileCol/tileRow, SpriteData type
7. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/sprites/spriteData.ts - getCharacterSprites(), character spritesheet metadata
8. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/sprites/carpetTiles.ts - carpet junction rendering
9. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/floorTiles.ts - getColorizedFloorSprite() for dynamic floor colors
10. https://github.com/pixel-agents-hq/pixel-agents/blob/main/webview-ui/src/office/wallTiles.ts - wall rendering with modular frames (referenced in renderer.ts)

---

## 3. overlap_analysis.json — Sobreposição de renderização isométrica

### Causas de sobreposição

1. Walls render after ALL entities, but north/west walls should render BEFORE entities (behind them in isometric view), only south/east walls should render after
2. Entities sorted by tile Y only, but screen Y depends on both tile X and Y in isometric projection - entities at same tile Y but different X can overlap incorrectly
3. Furniture rendered as single pass before entities with average Y sorting - multi-tile furniture spanning multiple Y rows doesn't interleave correctly with entities
4. Entity hash-based offset only ±4 pixels - insufficient for visual separation when multiple entities occupy adjacent tiles
5. Furniture grouping uses center tile for positioning, but large furniture visual bounds may not match center, causing misalignment with entities
6. Doors render after walls but at tile level (no Y-sort), can overlap entities incorrectly
7. No Z-layer system - all rendering is flat painter's algorithm without explicit layer priorities

### Fixes de renderer (renderer.js antigo)

1. Change renderRoom() order: floor -> north/west walls -> furniture (Y-sorted per tile) -> entities (Y-sorted by screen Y) -> south/east walls -> doors
2. Replace entity Y-sort (a.position.y - b.position.y) with screen Y sort using iso.tileToScreen(entity.position.x + 0.5, entity.position.y + 0.5).y
3. Split renderWalls() into renderWallsBehind() (north, west) and renderWallsFront() (south, east), call at correct render passes
4. In renderFurniture(): sort individual furniture tiles by screen Y, not group average Y; render each tile separately for proper interleaving with entities
5. Increase entity offset range from ±4 to ±8 pixels, add tile-based offset component so adjacent tiles get different offsets
6. Add furniture 'height' meta property (default 1 tile), use it to adjust render Y offset: taller furniture renders lower (higher screen Y)
7. In renderDoors(): sort doors by screen Y before rendering, apply same Y-sorting as entities

### Sistema de camadas (layer_fixes)

1. Define explicit render layers: 0=floor, 1=walls_behind(north/west), 2=furniture_low, 3=furniture_high, 4=entities, 5=walls_front(south/east), 6=doors
2. Add zIndex property to entity meta for manual override (e.g., flying entities, UI overlays)
3. In renderer.js, create renderLayer(layerName, room) function that renders all objects assigned to that layer
4. Assign furniture to furniture_low or furniture_high based on meta.furniture_height (1=low, 2+=high)
5. Add wall side classification: north/west=behind, south/east=front based on isometric view geometry
6. Update room transition renderRoomTransition() to respect new layer order for both rooms

---

*Fim da consolidação. Fonte: 3 JSONs de 16/09/2026, originais de ~20 KB no total.*
