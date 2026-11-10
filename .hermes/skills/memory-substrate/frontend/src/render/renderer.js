// renderer.js — Pipeline renderScene, BLUEPRINT §4.1.
//
// Ordem por frame:
//   1. Culling por câmera: só tiles/móveis/entidades visíveis entram.
//   2. LAYER_FLOOR desenhado direto (sem sort — varredura basta).
//   3. LAYER_WALLS_BEHIND desenhado direto (norte/oeste).
//   4. Camadas 2–6 (furniture low/high, entities, walls front, doors)
//      entram numa lista ÚNICA, ordenada por screenY (§4.2) — o sort
//      "unificado". zIndex em meta sobrepõe a camada (Princípio 1.2).
//   5. LAYER_UI por último.
//
// B consome o mundo via worldState.getDrawables() (API §7.2): retorna
// {room, entities, furniture, doors, carpetTiles}. O renderer NUNCA
// abre WebSocket e nunca importa src/net/.

import { iso } from './iso.js';
import {
  LAYER_FLOOR, LAYER_WALLS_BEHIND, LAYER_FURNITURE_LOW,
  LAYER_FURNITURE_HIGH, LAYER_ENTITIES, LAYER_WALLS_FRONT,
  LAYER_DOORS, LAYER_UI
} from './layers.js';
import { collectWallDrawables, drawWall, carpetJunctionCase } from './walls.js';
import { collectFurnitureTileDrawables, drawFurnitureTile } from './furniture.js';
import { collectDoorDrawables, drawDoor } from './doors.js';
import { collectEntityDrawable, drawEntity, currentWalkFrame } from './entities.js';

export class Renderer {
  constructor(ctx, getSprite, options = {}) {
    this.ctx = ctx;
    this.getSprite = getSprite || (() => null);
    this.manifest = options.manifest || {}; // manifest de assets (leitura)
    this.floorSpriteKey = options.floorSpriteKey || 'tile_floor_office';
    this.now = () => options.now ? options.now() :
      (typeof performance !== 'undefined' ? performance.now() : Date.now());
    // Estatísticas por frame (usadas pelo smoke test / B6)
    this.stats = { drawables: 0, sorted: 0, culled: 0, sortTimeMs: 0 };
  }

  /**
   * Móvel → entrada do manifest (43 entradas). Chaves possíveis:
   * manifestKey no meta, furniture_<type> ou o campo "sprite" do servidor
   * (já é uma chave de manifest, ex. "furniture_reception"). Somente leitura (§6.3).
   */
  manifestFor(furniture) {
    const key = furniture.meta?.manifestKey || furniture.manifestKey ||
                furniture.sprite || furniture.type;
    return this.manifest[key] || this.manifest[`furniture_${key}`] || null;
  }

  /**
   * renderScene — UM frame completo.
   * worldData: saída de worldState.getDrawables() (ou do mock no smoke):
   *   {room: {width, height, tileMap?, doors}, entities: [], furniture: [],
   *    carpetTiles: []}
   * camera: instância de Camera (culling + transform já aplicada? Não —
   *   o renderer aplica ctx.translate/scale da câmera aqui).
   * timeMs: relógio p/ animação (injetável p/ teste determinístico).
   */
  renderScene(worldData, camera, timeMs) {
    const ctx = this.ctx;
    const t = timeMs ?? this.now();
    this.stats = { drawables: 0, sorted: 0, culled: 0, sortTimeMs: 0 };
    if (!worldData || !worldData.room) return this.stats;

    const room = worldData.room;
    const range = camera.visibleTileRange();

    ctx.save();
    ctx.scale(camera.zoom, camera.zoom);
    ctx.translate(-camera.x, -camera.y);

    // FASE 2 — piso direto, sem sort (§4.1)
    this.drawFloor(room, worldData.carpetTiles || [], range);
    // FASE 3 — paredes norte/oeste direto (§4.3)
    const walls = collectWallDrawables(room, range);
    for (const w of walls) {
      if (w.layer === LAYER_WALLS_BEHIND) drawWall(ctx, w, this.getSprite);
    }

    // FASE 4 — lista UNIFICADA: furniture low/high + entities +
    // walls front + doors, tudo ordenado por screenY (§4.2)
    const unified = [];
    for (const w of walls) {
      if (w.layer === LAYER_WALLS_FRONT) unified.push(w);
    }
    for (const f of worldData.furniture || []) {
      const tiles = collectFurnitureTileDrawables(f, this.manifestFor(f), range);
      this.stats.culled += tiles.length === 0 ? 1 : 0;
      unified.push(...tiles);
    }
    for (const d of collectDoorDrawables(room.doors, range)) unified.push(d);
    for (const e of worldData.entities || []) {
      const d = collectEntityDrawable(e, range);
      if (d) unified.push(d); else this.stats.culled++;
    }

    const t0 = this.now();
    // Sort unificado (§4.1 fase 4 / §4.2): PURELY por screenY — camadas
    // 2–6 juntas. zIndex em meta SUBSTITUI a chave quando presente
    // (item voador sobre mesa: zIndex = screenY da mesa + 0.5, §4.1).
    // A camada LAYER_* do drawable não participa da chave aqui; os
    // épsilons (+0.5 móvel/porta, +1 parede front) resolvem empates.
    unified.sort((a, b) =>
      ((a.meta?.zIndex ?? a.screenY) - (b.meta?.zIndex ?? b.screenY)));
    this.stats.sortTimeMs = this.now() - t0;
    this.stats.sorted = unified.length;
    this.stats.drawables = unified.length + walls.length;

    for (const d of unified) this.drawDrawable(d, t);

    ctx.restore();
    return this.stats;
  }

  /** Despacho de desenho por kind (fase 4 + fase 5 UI). */
  drawDrawable(d, timeMs) {
    const ctx = this.ctx;
    switch (d.kind) {
      case 'wall': drawWall(ctx, d, this.getSprite); break;
      case 'door': drawDoor(ctx, d, this.getSprite); break;
      case 'entity':
        drawEntity(ctx, d, this.getSprite(d.characterKey),
          d.moving ? currentWalkFrame(d, timeMs) : 0, timeMs);
        break;
      case 'furniture_tile': {
        // O slice precisa do footprint do móvel — guardado no drawable
        const sprite = this.getSprite(d.spriteKey);
        const fpW = d.fpW || 1, fpH = d.fpH || 1;
        drawFurnitureTile(ctx, d, sprite, fpW, fpH);
        break;
      }
      default: break; // kinds futuros (ui, cursor) — LAYER_UI na fase 5
    }
  }

  /**
   * FASE 2 — pisos + tapetes. Tapete é LAYER_FLOOR, nunca colide
   * (§2.3). Piso desenhado na ordem de varredura (sem sort).
   *
   * Pisos REAIS do pixel-agents: PNG 16×16 uniformes (RGB). Nosso tile
   * iso é 32×16 → escala 2× horizontal e vertical (fillRect-equivalente:
   * 32×32 desenhado ancorado na base do tile, cobrindo o losango e a
   * "espessura" do chão, como o renderer original fazia com 32×32).
   * Tapete: set 64×64 com 16 peças 16×16 (marching-squares portado do
   * pixel-agents) — cada tile de tapete desenha a peça da sua junção,
   * escalada 2×, com cantos arredondados definidos pelo vizinho.
   */
  drawFloor(room, carpetTiles, range) {
    const ctx = this.ctx;
    const floorSprite = this.getSprite(this.floorSpriteKey);
    const carpetSet = new Set((carpetTiles || []).map(c =>
      typeof c === 'string' ? c : `${c.col},${c.row}`));
    // Piso 16×16 escalado 2× → 32×32 world-px (preenche o tile iso 32×16
    // + metade de cima, ancorado na base — igual ao desenho antigo).
    const fw = 32, fh = 32;
    const carpetSprite = this.getSprite('tile_carpet');

    for (let row = range.minRow; row <= range.maxRow; row++) {
      for (let col = range.minCol; col <= range.maxCol; col++) {
        if (row < 0 || col < 0 || row >= room.height || col >= room.width) continue;
        const c = iso.tileCenter(col, row);
        const isCarpet = carpetSet.has(`${col},${row}`);
        if (isCarpet && carpetSprite) {
          // Tapete: peça 16×16 da junção (marching-squares), escala 2×.
          // tile_carpet → carpets/carpet_0.png (64×64, grid 4×4).
          const msCase = carpetJunctionCase(carpetSet, col, row, room.width, room.height);
          const sx = (msCase % 4) * 16, sy = Math.floor(msCase / 4) * 16;
          ctx.drawImage(carpetSprite, sx, sy, 16, 16,
            c.x - 16, c.y + 8 - 32, 32, 32);
        } else if (floorSprite) {
          ctx.drawImage(floorSprite, c.x - fw / 2, c.y + 8 - fh, fw, fh);
        } else {
          // fallback procedural só quando não há sprite (teste headless)
          ctx.fillStyle = (col + row) % 2 === 0 ? '#1c2128' : '#161b22';
          ctx.fillRect(c.x - 16, c.y - 8, 32, 16);
        }
      }
    }
  }
}
