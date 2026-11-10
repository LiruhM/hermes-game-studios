// furniture.js — Móveis per-tile consumindo manifest, BLUEPRINT §4.4.
//
// Cada móvel vira N drawables (um por tile do footprint), cada um com
// screenY próprio calculado do SEU tile — nunca do centro do grupo
// (causa nº 3 das sobreposições).
//
// backgroundTiles (§2.2): as fileiras do topo do footprint declaradas
// como background. Nenhum caso especial: nessas fileiras o tile do
// móvel tem screenY MAIOR que o do personagem atrás, então o sort
// unificado desenha o móvel DEPOIS (na frente) — emerge naturalmente
// (§4.4). Aqui apenas marcamos isBackgroundTile p/ depuração.
//
// Altura (meta.furniture_height, default 1): 1 → LAYER_FURNITURE_LOW,
// 2+ → LAYER_FURNITURE_HIGH. Afeta APENAS camada visual — nunca
// colisão (Princípio 1.3, critério B7).

import { iso } from './iso.js';
import { LAYER_FURNITURE_LOW, LAYER_FURNITURE_HIGH } from './layers.js';

/**
 * Converte furniture_height em camada (§4.4 / B7).
 */
export function heightToLayer(furnitureHeight) {
  return (furnitureHeight || 1) >= 2 ? LAYER_FURNITURE_HIGH : LAYER_FURNITURE_LOW;
}

/**
 * Gera drawables per-tile para UM móvel.
 * furniture (API §7.2 do C): {id, type, col, row, orientation, meta}
 *   meta: {footprintW, footprintH, backgroundTiles, furniture_height,
//          spriteKey, manifestKey}
 * manifestEntry: dados do manifest (footprintW/H, backgroundTiles…) —
 *   os do meta têm prioridade (C pode passar EITHER; B consome ambos,
 *   manifest vence como fonte autoritativa de arte).
 */
export function collectFurnitureTileDrawables(furniture, manifestEntry, range) {
  const out = [];
  if (!furniture) return out;

  // Compat de formato: servidor real manda {x, y, w, h, sprite, type};
  // protocolo §5 (fixture/mock) manda {col, row, meta:{footprintW/H,...}}.
  const fcol = furniture.col ?? furniture.x ?? 0;
  const frow = furniture.row ?? furniture.y ?? 0;

  const man = manifestEntry || {};
  const fpW = man.footprintW ?? furniture.meta?.footprintW ?? furniture.w ?? 1;
  const fpH = man.footprintH ?? furniture.meta?.footprintH ?? furniture.h ?? 1;
  const bgTiles = man.backgroundTiles ?? furniture.meta?.backgroundTiles ?? 0;
  const fHeight = man.furniture_height ?? furniture.meta?.furniture_height ?? 1;
  const layer = heightToLayer(fHeight);
  const spriteKey = furniture.meta?.spriteKey || furniture.spriteKey ||
                    furniture.sprite || man.spriteKey || `furniture_${furniture.type}`;

  // Fileiras de background = topo do footprint (norte visual). Para
  // orientação "front", background fica nas primeiras fileiras (row
  // menor). Guardamos a flag para o sort — o comportamento emerge do
  // screenY, nada de caso especial no desenho.
  const isBgRow = (r) => r < bgTiles;

  for (let dc = 0; dc < fpW; dc++) {
    for (let dr = 0; dr < fpH; dr++) {
      const col = fcol + dc;
      const row = frow + dr;
      if (range && (col < range.minCol || col > range.maxCol ||
                    row < range.minRow || row > range.maxRow)) continue;
      const c = iso.tileCenter(col, row);
      out.push({
        kind: 'furniture_tile',
        layer,
        furnitureId: furniture.id,
        spriteKey,
        // footprint no drawable — o renderer fatia o sprite com isso
        fpW, fpH,
        col, row,
        dc, dr,
        isBackgroundTile: isBgRow(dr),
        screenX: c.x,
        // Sort: screenY do tile + 0.5 (padrão §4.2). Em empate com uma
        // entidade no tile adjacente ao norte, O MÓVEL vence: quem anda
        // atrás do móvel é coberto pelas fileiras de fundo (B1), e a
        // superfície frontal cobre o corpo de quem está no tile de
        // fundo (pose "de pé na mesa"). Entidade ao sul (na frente)
        // continua com screenY maior e cobre o móvel.
        screenY: iso.sortKey(col, row) + 0.5
      });
    }
  }
  return out;
}

/**
 * Desenha UM tile do móvel.
 * O sprite do móvel tem o footprint inteiro; o tile (dc,dr) recorta a
 * fatia correspondente do sprite (fatia proporcional: cada tile do
 * footprint = 1/fpW da largura, 1/fpH da altura). A fatia é ancorada
 * no centro do tile atual. Isso é o "per-tile slicing" da §4.4 —
//  o móvel nunca é desenhado como um retângulo único.
 */
export function drawFurnitureTile(ctx, tile, sprite, fpW = 1, fpH = 1) {
  if (!sprite) return false;
  const sw = (sprite.width || 32) / fpW;
  const sh = (sprite.height || 32) / fpH;
  const sx = tile.dc * sw;
  const sy = tile.dr * sh;
  // Desenha a fatia centrada no tile do footprint
  const dx = tile.screenX - sw / 2;
  const dy = tile.screenY + 8 - sh; // +8 = meio TILE_H: base do sprite na base do tile
  ctx.drawImage(sprite, sx, sy, sw, sh, dx, dy, sw, sh);
  return true;
}
