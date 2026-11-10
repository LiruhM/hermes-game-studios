// walls.js — Auto-tiling de paredes por bitmask (port do pixel-agents), BLUEPRINT §4.3.
//
// PORT do sistema wallTiles.ts do pixel-agents: cada sprite wall_N.png
// é um SET 64×128 com 16 peças de 16×32 (grid 4×4), indexadas por um
// bitmask de 4 bits dos vizinhos cardeais WALL do tileMap:
//
//   N=1, E=2, S=4, W=8   (N=row-1, E=col+1, S=row+1, W=col-1)
//   peça do bitmask M: col=M%4, row=floor(M/4) no set.
//   Fora do grid NÃO é wall (bit=0).
//
// Cada peça 16×32 tem ALTURA DE 2 TILES: metade de baixo (rows 16-31)
// cobre o próprio tile, metade de cima (rows 0-15) sobe sobre o tile
// vizinho do norte. O contorno escuro de 1px aparece em cada aresta
// onde NÃO há vizinho wall — cantos e arestas ficam definidos
// ("dá pra ver onde começa cada coisa", linha do CEO).
//
// GEOMETRIA: aqui o tile iso é 32×16 (§4) e o sprite deles é 16×32 com
// TILE_SIZE=16 → escala 2× exata. Peça escalada: 32×64 world-px.
// Ancoragem (idêntica ao pixel-agents, offsetY = TILE_SIZE - altura):
// a BASE da peça fica na base do tile de parede, o topo sobe 2 tiles:
//   dx = screenX - 16 (largura escalada/2 — o tile iso tem 32 de largura)
//   dy = screenY + 8 - 64 (+8 = metade do TILE_H 16: base do tile)
//
// CAMADAS preservadas (§4.3, critério B2): tiles N (row 0) e W (col 0)
// → LAYER_WALLS_BEHIND (antes das entidades); S/E → LAYER_WALLS_FRONT
// (lista unificada, Y-sorted). O auto-tiling só escolhe o RECORTE do
// set; a classificação behind/front continua a mesma.

import { iso } from './iso.js';
import { LAYER_WALLS_BEHIND, LAYER_WALLS_FRONT } from './layers.js';
import { TILE_WALL } from '../net/messageTypes.js';

// ── Dimensões do set de paredes (formato pixel-agents) ─────────────
export const WALL_SET_COLS = 4;   // grid 4×4 de peças no PNG 64×128
export const WALL_SET_ROWS = 4;
export const WALL_PIECE_W = 16;  // peça crua 16×32 (TILE_SIZE deles = 16)
export const WALL_PIECE_H = 32;  // altura 2 tiles deles
export const WALL_SCALE = 2;     // nosso tile iso 32×16 → escala 2× exata
export const WALL_DRAW_W = WALL_PIECE_W * WALL_SCALE;  // 32 world-px
export const WALL_DRAW_H = WALL_PIECE_H * WALL_SCALE;  // 64 world-px

/**
 * Classifica um segmento de parede (§4.3).
 * side: 'north' | 'west' → 'behind'; 'south' | 'east' → 'front'.
 * Mantido do renderer original — auto-tiling não mexe nisso.
 */
export function wallSide(side) {
  if (side === 'north' || side === 'west') return 'behind';
  return 'front'; // south | east
}

/**
 * Tile é WALL? Lê o tileMap direto quando existe; senão (sem tileMap,
 * ex. mock legado) usa a geometria do perímetro retangular.
 * Fora do grid = NÃO é wall (bit 0) — igual ao pixel-agents.
 */
export function isWallTile(room, col, row) {
  if (!room) return false;
  if (col < 0 || row < 0 || col >= room.width || row >= room.height) return false;
  const tm = room.tileMap;
  if (Array.isArray(tm) && tm.length > 0 && Array.isArray(tm[row])) {
    return tm[row][col] === TILE_WALL;
  }
  // fallback sem tileMap: perímetro do retângulo
  return row === 0 || row === room.height - 1 || col === 0 || col === room.width - 1;
}

/**
 * Bitmask N=1, E=2, S=4, W=8 dos vizinhos cardeais WALL (port direto
 * do buildWallMask do pixel-agents). Fora do grid → bit 0.
 */
export function wallBitmask(room, col, row) {
  let mask = 0;
  if (isWallTile(room, col, row - 1)) mask |= 1; // N
  if (isWallTile(room, col + 1, row)) mask |= 2; // E
  if (isWallTile(room, col, row + 1)) mask |= 4; // S
  if (isWallTile(room, col - 1, row)) mask |= 8; // W
  return mask;
}

/**
 * Recorte (sx, sy) da peça de bitmask `mask` no set 64×128.
 * col = mask % 4, row = floor(mask / 4) — idêntico ao parseWallPng deles.
 */
export function wallPieceRect(mask) {
  const m = ((mask % 16) + 16) % 16; // 0..15
  return {
    sx: (m % WALL_SET_COLS) * WALL_PIECE_W,
    sy: Math.floor(m / WALL_SET_COLS) * WALL_PIECE_H,
    sw: WALL_PIECE_W,
    sh: WALL_PIECE_H
  };
}

/**
 * Gera drawables de parede: UM POR TILE WALL do tileMap da sala,
 * com o bitmask de vizinhos calculado (auto-tiling portado).
 * Cada drawable: {layer, screenX, screenY, spriteKey, col, row, side, mask, rect}.
 *
 * O sprite é o SET 64×128 (manifest: tile_wall_north/east apontam para
 * walls/wall_0.png); o RECORTE 16×32 da peça certa vem no drawable
 * (`rect`) e o drawWall fatia. Nenhuma peça é desenhada
 * proceduralmente — contorno/altura vêm do PNG (§4.3).
 *
 * Portas: tiles com porta NÃO geram parede (a porta desenha em
 * LAYER_DOORS, §4.5). Compat: portas chegam como {col,row} (§5) ou
 * {x,y} (servidor legado).
 *
 * tiles WALL fora do perímetro (paredes internas) também são emitidos —
 * o tileMap é a fonte da verdade, não a geometria do retângulo.
 */
export function collectWallDrawables(room, range) {
  const out = [];
  if (!room) return out;
  // Compat: portas chegam como {col,row} (§5) ou {x,y} (servidor legado)
  const doorSet = new Set((room.doors || []).map(d => `${d.col ?? d.x},${d.row ?? d.y}`));

  // Fonte de tiles: tileMap quando existe; sem tileMap (mock legado),
  // varre o perímetro como antes — sala retangular clássica.
  const wallTiles = [];
  const tm = room.tileMap;
  if (Array.isArray(tm) && tm.length > 0) {
    for (let row = 0; row < Math.min(tm.length, room.height); row++) {
      const tmRow = Array.isArray(tm[row]) ? tm[row] : [];
      for (let col = 0; col < Math.min(tmRow.length, room.width); col++) {
        if (tmRow[col] === TILE_WALL) wallTiles.push([col, row]);
      }
    }
  } else {
    const W = room.width, H = room.height;
    for (let col = 0; col < W; col++) { wallTiles.push([col, 0]); wallTiles.push([col, H - 1]); }
    for (let row = 1; row < H - 1; row++) { wallTiles.push([0, row]); wallTiles.push([W - 1, row]); }
  }

  for (const [col, row] of wallTiles) {
    if (doorSet.has(`${col},${row}`)) continue; // tile de porta → sem parede (§4.5)
    if (range && (col < range.minCol || col > range.maxCol ||
                  row < range.minRow || row > range.maxRow)) continue;

    // Lado §4.3 preservado — MESMA prioridade do renderer original
    // (bordas primeiro, depois colunas): row 0 → north (behind);
    // row H-1 → south (front); col 0 → west (behind); col W-1 →
    // east (front); parede interna → front (jogador nunca passa
    // atrás de perímetro de 1 tile).
    const onNorth = row === 0;
    const onSouth = row === room.height - 1;
    const onWest = !onNorth && !onSouth && col === 0;
    const onEast = !onNorth && !onSouth && col === room.width - 1;
    const side = onNorth ? 'north' : onSouth ? 'south' : onWest ? 'west' : 'east';
    const layer = (onNorth || onWest) ? LAYER_WALLS_BEHIND : LAYER_WALLS_FRONT;

    const c = iso.tileCenter(col, row);
    // Auto-tiling: bitmask dos 4 vizinhos cardeais (N=1,E=2,S=4,W=8)
    const mask = wallBitmask(room, col, row);
    out.push({
      kind: 'wall',
      layer,
      col, row, side,
      mask,
      rect: wallPieceRect(mask),
      screenX: c.x,
      // Chave de sort = screenY do centro do tile (§4.2). Paredes front
      // ganham +1 (padrão §4.2): em empate com entidade no tile ao
      // norte, a parede vence — nunca "some atrás do sprite" (B2).
      screenY: iso.sortKey(col, row) + (layer === LAYER_WALLS_FRONT ? 1 : 0),
      // Manifest real: tile_wall_north/east (mesmo PNG walls/wall_0.png).
      // Norte/oeste → north; sul/leste → east (chaves preservadas).
      spriteKey: (side === 'north' || side === 'west') ? 'tile_wall_north' : 'tile_wall_east'
    });
  }
  return out;
}

/**
 * Desenha um drawable de parede no ctx (transformação da câmera JÁ
 * aplicada — coordenadas de mundo). FatiA o set 64×128: recorte 16×32
 * da peça de bitmask, escalado 2× (32×64 world-px — tile iso 32×16).
 * Ancoragem: base da peça = base do tile; o topo sobe 2 tiles
 * (offset Y do pixel-agents: peça ancorada no fundo, "tall sprites
 * extend upward").
 */
export function drawWall(ctx, wall, getSprite) {
  const sprite = getSprite ? getSprite(wall.spriteKey) : null;
  if (!sprite) return false;

  const rect = wall.rect || wallPieceRect(0);
  const dw = (rect.sw || WALL_PIECE_W) * WALL_SCALE; // 32
  const dh = (rect.sh || WALL_PIECE_H) * WALL_SCALE; // 64

  // Centraliza horizontalmente no tile; base do sprite = base do tile
  // (+8 = metade do TILE_H 16 — mesmo ancoramento das entidades/§4.2).
  const dx = wall.screenX - dw / 2;
  const dy = wall.screenY + 8 - dh;
  ctx.drawImage(sprite,
    rect.sx, rect.sy, rect.sw, rect.sh, // recorte no set 64×128
    dx, dy, dw, dh);                    // destino escalado 2×
  return true;
}

/**
 * Caso marching-squares da JUNÇÃO (col+1,row+1) para o tile de tapete
 * (col,row) — port do carpetJunctionCase do pixel-agents (NW=1, NE=2,
 * SE=4, SW=8 sobre os 4 tiles ao redor da junção). O tile em si é o
 * quadrante SE; fora do grid não conta (bit 0). A peça correspondente
 * no set 64×64 fica em col=msCase%4, row=floor(msCase/4).
 */
export function carpetJunctionCase(carpetSet, col, row, cols, rows) {
  const has = (c, r) =>
    c >= 0 && r >= 0 && c < cols && r < rows && carpetSet.has(`${c},${r}`);
  let msCase = 0;
  if (has(col - 1, row - 1)) msCase |= 1; // NW
  if (has(col, row - 1)) msCase |= 2;    // NE
  if (has(col, row)) msCase |= 4;        // SE (o próprio tile)
  if (has(col - 1, row)) msCase |= 8;    // SW
  return msCase;
}
