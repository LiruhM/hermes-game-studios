// doors.js — Portas Y-sorted na lista unificada, BLUEPRINT §4.5.
//
// O tile da porta é FLOOR_* na colisão (§2.3); visualmente o frame
// desenha em LAYER_DOORS mas PARTICIPA da mesma lista unificada com
// sort por screenY — nunca "depois de tudo". Isso elimina a causa
// nº 6 (portas sem Y-sort cobrindo entidades; critério B3).

import { iso } from './iso.js';
import { LAYER_DOORS } from './layers.js';

/**
 * Gera drawables de porta — um por porta (portas de 1 tile no grid;
//  portas largas podem vir do worldState como N tiles, respeitamos
 *  width se presente).
 * door (API §7.2): {col, row, orientation, targetRoom, width?, label?}
 */
export function collectDoorDrawables(doors, range) {
  const out = [];
  if (!doors) return out;
  for (const door of doors) {
    // Compat: servidor real manda {x, y, target_room, width, label};
    // protocolo §5 (fixture/mock) manda {col, row, orientation, targetRoom}.
    const dCol = door.col ?? door.x;
    const dRow = door.row ?? door.y;
    const width = door.width || 1;
    for (let w = 0; w < width; w++) {
      const col = dCol + w;
      const row = dRow;
      if (range && (col < range.minCol || col > range.maxCol ||
                    row < range.minRow || row > range.maxRow)) continue;
      const c = iso.tileCenter(col, row);
      out.push({
        kind: 'door',
        layer: LAYER_DOORS,
        doorId: `${dCol},${dRow}`,
        col, row,
        orientation: door.orientation ?? (row === 0 ? 'north' : 'south'),
        label: door.label || null,
        targetRoom: door.targetRoom || door.target_room || null,
        screenX: c.x,
        // +0.5 (padrão §4.2): em empate, a porta cobre quem está ATRÁS
        // do vão; quem está NA FRENTE (tile ao sul, screenY maior)
        // desenha depois e cobre o frame (critério B3).
        screenY: iso.sortKey(col, row) + 0.5
      });
    }
  }
  return out;
}

/**
 * Desenha o frame da porta. O sprite de porta (manifest: tile_door,
 * 64×128) é mais alto que o tile — o frame sobe do chão. Como a porta
 * está na lista unificada, entidade NA FRENTE (screenY maior) desenha
 * depois e cobre o frame; entidade ATRÁS desenha antes e é coberta
//  pela batente — correto para quem passa "por dentro" do vão.
 */
export function drawDoor(ctx, door, getSprite) {
  const sprite = getSprite ? getSprite('tile_door') : null;
  if (!sprite) return false;
  const w = sprite.width || 64;
  const h = sprite.height || 128;
  const dx = door.screenX - w / 2;
  const dy = door.screenY + 8 - h;
  ctx.drawImage(sprite, dx, dy, w, h);
  return true;
}
