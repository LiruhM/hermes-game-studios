// entities.js — Entidades: frames de caminhada, 4 direções, BLUEPRINT §4.6.
//
// Spritesheets de personagem (manifest): 112×96, 7 frames × 3 rows,
// frame 16×32. Mapeamento de rows (herdado do pixel-agents):
//   row 0 = down/sul, row 1 = up/norte, row 2 = right/leste.
//   LEFT = flip horizontal do RIGHT (não há row própria).
//
// Sort: screenY do centro do tile (§4.2), LAYER_ENTITIES na lista
// unificada. Offset visual anti-pilha: ±8px quando entidades dividem
// visualmente o mesmo tile (§4.6) — offset é SÓ de render; posição
// lógica (col/row) nunca muda (critério B4).

import { iso } from './iso.js';
import { LAYER_ENTITIES } from './layers.js';

// Mapa dir (protocolo §5: n|s|e|w) → row do spritesheet
export const DIR_ROWS = { s: 0, n: 1, e: 2, w: 2 }; // w = flip de e
// Velocidade de animação de caminhada (ms por frame)
export const WALK_FRAME_MS = 150;

/**
 * Offset determinístico por entidade (hash do id) — §4.6.
 * Faixa: ±8px em X, mais componente por tile (col % 3) * 2 - 2.
 * Duas entidades no mesmo tile ficam visivelmente separadas (B4).
 */
export function entityVisualOffset(id, col) {
  let hash = 0;
  const s = String(id);
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash + s.charCodeAt(i)) | 0;
  }
  const base = (Math.abs(hash) % 17) - 8; // −8..+8
  const perTile = ((col % 3) * 2) - 2;   // componente por tile (§4.6)
  return { x: base + perTile };
}

/**
 * Gera o drawable de uma entidade.
 * entity (API §7.2): {id, type, name, x, y, dir, moving, characterKey}
 *   x/y são contínuos (col+progress*dx) — interpolados pelo C (§3.3).
 */
export function collectEntityDrawable(entity, range) {
  if (!entity) return null;
  const col = Math.floor(entity.x);
  const row = Math.floor(entity.y);
  if (range && (col < range.minCol || col > range.maxCol ||
                row < range.minRow || row > range.maxRow)) return null;
  // x/y contínuos JÁ vêm em unidades de centro (protocolo §5:
  // "x": col+0.5) — logo a projeção é DIRETA, sem outro +0.5.
  const c = iso.tileToScreen(entity.x, entity.y);
  const off = entityVisualOffset(entity.id, col);
  return {
    kind: 'entity',
    layer: LAYER_ENTITIES,
    id: entity.id,
    type: entity.type,
    name: entity.name || null,
    col, row,
    // posição lógica contínua preservada (o C é dono dela)
    logicX: entity.x,
    logicY: entity.y,
    dir: entity.dir || 's',
    moving: !!entity.moving,
    characterKey: entity.characterKey || null,
    screenX: c.x + off.x, // offset visual aplicado (B4)
    screenY: c.y
  };
}

/**
 * Frame atual de caminhada para a entidade (animação de render).
 * timeMs: relógio (performance.now() no browser; injetável p/ teste).
 */
export function currentWalkFrame(entity, timeMs) {
  if (!entity.moving) return 0;
  const maxFrames = 7;
  return Math.floor(timeMs / WALK_FRAME_MS) % maxFrames;
}

/**
 * Desenha a entidade (spritesheet 7×3, frame 16×32; flip p/ oeste).
 */
export function drawEntity(ctx, drawable, sprite, frame, timeMs) {
  if (!sprite) return false;
  const meta = sprite.meta || {};
  const fw = meta.frameWidth || 16;
  const fh = meta.frameHeight || 32;
  const frames = meta.frames || 7;
  const dir = drawable.dir || 's';
  const row = DIR_ROWS[dir] ?? 0;
  const f = frame ?? currentWalkFrame(drawable, timeMs ?? 0);
  const sx = (f % frames) * fw;
  const sy = row * fh;

  ctx.save();
  ctx.translate(drawable.screenX, drawable.screenY);
  if (dir === 'w') ctx.scale(-1, 1); // LEFT = flip do RIGHT
  // Sprite ancorado: base do frame na base do tile (screenY é o centro
  // do tile; +8 = meio TILE_H). Pés no chão, corpo subindo.
  const dx = -fw / 2;
  const dy = 8 - fh;
  const img = sprite.image || sprite;
  ctx.drawImage(img, sx, sy, fw, fh, dx, dy, fw, fh);
  ctx.restore();
  return true;
}
