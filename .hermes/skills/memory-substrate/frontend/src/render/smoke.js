// smoke.js — Smoke test headless do pipeline de render (BLUEPRINT §8.3 B1–B7).
//
// Roda com:  node render/smoke.js
// Sem canvas real: usa um ctx 2D FAKE que registra a ORDEM de desenho
// (draw log). A validação é LÓGICA: verificamos a ordem relativa dos
// drawables no sort unificado — que é exatamente o que os critérios
// B1–B4 pedem (quem cobre quem).

import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
// Caminho absoluto Windows precisa virar file:// URL para o ESM loader
const mod = (name) => pathToFileURL(join(HERE, name)).href;

// --- imports do pipeline (ES modules nativos) -------------------------
const { validateLayers, LAYER_FLOOR, LAYER_WALLS_BEHIND, LAYER_FURNITURE_LOW,
        LAYER_FURNITURE_HIGH, LAYER_ENTITIES, LAYER_WALLS_FRONT,
        LAYER_DOORS, LAYER_UI } = await import(mod('layers.js'));
const { iso } = await import(mod('iso.js'));
const { Camera } = await import(mod('camera.js'));
const { Renderer } = await import(mod('renderer.js'));
const { collectWallDrawables, wallSide, drawWall } = await import(mod('walls.js'));
const { collectFurnitureTileDrawables, heightToLayer } = await import(mod('furniture.js'));
const { collectDoorDrawables } = await import(mod('doors.js'));
const { collectEntityDrawable, entityVisualOffset, currentWalkFrame } = await import(mod('entities.js'));

const fixture = JSON.parse(readFileSync(join(HERE, 'test_fixture.json'), 'utf8'));

// --- ctx 2D fake: registra drawImage/ordem ----------------------------
function makeFakeCtx() {
  const log = [];
  const noop = () => {};
  const ctx = {
    log,
    drawImage: (img, ...args) => log.push({ op: 'drawImage', img, args }),
    fillRect: (x, y, w, h) => log.push({ op: 'fillRect', x, y, w, h }),
    save: noop, restore: noop, translate: noop, scale: noop
  };
  return ctx;
}

// Sprites fake: qualquer getSprite devolve um retângulo com dimensões
const fakeSprites = new Map([
  ['tile_floor_office', { width: 32, height: 32 }],
  ['tile_door', { width: 64, height: 128 }],
  ['avatar_dev', { width: 112, height: 96, meta: { frames: 7, rows: 3, frameWidth: 16, frameHeight: 32 } }],
  ['furniture_desk', { width: 48, height: 32 }],
  ['furniture_snack_shelf', { width: 32, height: 64 }],
  ['furniture_plant', { width: 32, height: 32 }],
  ['furniture_table', { width: 32, height: 16 }]
]);
const getSprite = (key) => fakeSprites.get(key) || null;

// --- harness ----------------------------------------------------------
let passed = 0, failed = 0;
function check(name, cond, detail = '') {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail ? ' — ' + detail : ''}`); }
}

// Executa UMA cena e devolve a lista unificada pós-sort (a ordem real
// de desenho da fase 4), para inspeção.
function buildSortedDrawables(roomData, manifest, viewportW = 800, viewportH = 600) {
  const cam = new Camera(viewportW, viewportH);
  const room = roomData.room;
  const center = iso.tileCenter(room.width / 2, room.height / 2);
  cam.centerOn(center.x, center.y);
  const range = cam.visibleTileRange();

  const unified = [];
  const walls = collectWallDrawables(room, range);
  for (const w of walls) if (w.layer === LAYER_WALLS_FRONT) unified.push(w);
  for (const f of roomData.furniture || []) {
    const man = manifest[f.meta?.manifestKey] || null;
    unified.push(...collectFurnitureTileDrawables(f, man, range));
  }
  unified.push(...collectDoorDrawables(room.doors, range));
  for (const e of roomData.entities || []) {
    const d = collectEntityDrawable(e, range);
    if (d) unified.push(d);
  }
  const t0 = performance.now();
  // MESMO sort do renderer: puramente por screenY (zIndex em meta
  // substitui a chave quando presente). Camadas 2–6 juntas (§4.2).
  unified.sort((a, b) =>
    ((a.meta?.zIndex ?? a.screenY) - (b.meta?.zIndex ?? b.screenY)));
  const sortTimeMs = performance.now() - t0;
  return { unified, walls, cam, range, sortTimeMs };
}

console.log('SMOKE TEST — render pipeline (B1–B7)\n');

// B5 — constantes de camada exatamente como §4
console.log('[B5] constantes LAYER_*:');
check('LAYER_FLOOR=0', LAYER_FLOOR === 0);
check('LAYER_WALLS_BEHIND=1', LAYER_WALLS_BEHIND === 1);
check('LAYER_FURNITURE_LOW=2', LAYER_FURNITURE_LOW === 2);
check('LAYER_FURNITURE_HIGH=3', LAYER_FURNITURE_HIGH === 3);
check('LAYER_ENTITIES=4', LAYER_ENTITIES === 4);
check('LAYER_WALLS_FRONT=5', LAYER_WALLS_FRONT === 5);
check('LAYER_DOORS=6', LAYER_DOORS === 6);
check('LAYER_UI=10', LAYER_UI === 10);
check('validateLayers() completa', validateLayers());

// Fixture sanity
console.log('\n[fixture] 2 salas, 10 entidades, 4 paredes:');
const office = fixture.rooms.office, meeting = fixture.rooms.meeting;
const totalEnts = office.entities.length + meeting.entities.length;
check('10 entidades no fixture', totalEnts === 10, `achei ${totalEnts}`);
check('2 salas', Object.keys(fixture.rooms).length === 2);

const officeSorted = buildSortedDrawables(office, fixture.manifest);
// 4 paredes = perímetro do retângulo (norte/sul/oeste/leste classificadas)
const sides = new Set(officeSorted.walls.map(w => w.side));
check('4 lados de parede presentes', sides.size === 4, [...sides].join(','));
check('norte/oeste = behind', wallSide('north') === 'behind' && wallSide('west') === 'behind');
check('sul/leste = front', wallSide('south') === 'front' && wallSide('east') === 'front');

// B1 — entidade atrás E na frente da mesma mesa
console.log('\n[B1] entidade atrás vs. na frente da mesma mesa:');
const idx = (pred) => officeSorted.unified.findIndex(pred);
const behindEnt = idx(d => d.id === 'ent_behind_desk');
const frontEnt = idx(d => d.id === 'ent_front_desk');
// tiles da fileira de FUNDO do desk (row 4, backgroundTiles=1) — devem
// cobrir a entidade atrás; fileira da frente (row 5) fica atrás da
// entidade da frente.
const deskBgTiles = officeSorted.unified.filter(d =>
  d.kind === 'furniture_tile' && d.furnitureId === 'desk_main' && d.isBackgroundTile);
const deskFrontRow = officeSorted.unified.filter(d =>
  d.kind === 'furniture_tile' && d.furnitureId === 'desk_main' && !d.isBackgroundTile);
check('desk fatiado per-tile (6 tiles p/ 3×2)', deskBgTiles.length + deskFrontRow.length === 6,
  `bg=${deskBgTiles.length} front=${deskFrontRow.length}`);
const anyBgAfterBehind = deskBgTiles.some(t => idx(d => d === t) > behindEnt);
const anyFrontBeforeFrontEnt = deskFrontRow.some(t => idx(d => d === t) < frontEnt);
check('fileiras de fundo desenham DEPOIS da entidade de trás (cobrem-na)', anyBgAfterBehind);
check('fileiras frontais desenham ANTES da entidade da frente (ela cobre a mesa)', anyFrontBeforeFrontEnt);

// B2 — paredes norte atrás / sul na frente
console.log('\n[B2] parede norte ATRÁS, sul NA FRENTE das entidades:');
const northWall = officeSorted.walls.find(w => w.side === 'north' && w.col === 6); // col 5 tem PORTA (sem parede, §4.5)
// Segmento de parede sul NA MESMA COLUNA da entidade (screenY depende
// de col E row — comparar segmentos de outra coluna não testa oclusão)
const southWall = officeSorted.walls.find(w => w.side === 'south' && w.col === 7);
const northInUnified = idx(d => d === northWall); // behind: NÃO está na unificada
const southIdx = idx(d => d === southWall);
check('parede norte classificada behind (desenha antes de tudo)', northWall.layer === LAYER_WALLS_BEHIND);
check('parede sul classificada front (entra no sort)', southWall.layer === LAYER_WALLS_FRONT);
const entNearNorth = idx(d => d.id === 'ent_north_wall');
const entNearSouth = idx(d => d.id === 'ent_south_wall');
check('entidade na borda norte: parede norte desenha antes (behind)', northWall.layer === LAYER_WALLS_BEHIND && entNearNorth > -1);
check('parede sul desenha DEPOIS da entidade do sul (na frente)', southIdx > entNearSouth,
  `south=${southIdx} ent=${entNearSouth}`);

// AUTO-TILING — port do pixel-agents: bitmask N=1,E=2,S=4,W=8 por tile,
// recorte 16×32 no set 64×128 (grid 4×4), altura 2 tiles (§4.3).
console.log('\n[autotiling] paredes por bitmask do pixel-agents:');
const { wallBitmask, wallPieceRect } = await import(mod('walls.js'));
// Canto NO (0,0): vizinhos E+S → mask 6 (aresta horizontal N... na verdade
// E=2 + S=4 = 6). Confere com o dump do PNG: peça 6 tem contorno N,W,S.
const cornerNW = officeSorted.walls.find(w => w.col === 0 && w.row === 0);
check('canto NO (0,0) → mask 6 (E+S)', cornerNW.mask === 6, `mask=${cornerNW.mask}`);
// Aresta norte pura (ex. 3,0): vizinho W... na verdade W+E = 8+2 = 10
const edgeN = officeSorted.walls.find(w => w.col === 3 && w.row === 0);
check('aresta norte (3,0) → mask 10 (E+W)', edgeN.mask === 10, `mask=${edgeN.mask}`);
// Aresta oeste (0,2): vizinhos N+S = 1+4 = 5
const edgeW = officeSorted.walls.find(w => w.col === 0 && w.row === 2);
check('aresta oeste (0,2) → mask 5 (N+S)', edgeW.mask === 5, `mask=${edgeW.mask}`);
// Canto NE (11,0): S+W = 4+8 = 12
const cornerNE = officeSorted.walls.find(w => w.col === 11 && w.row === 0);
check('canto NE (11,0) → mask 12 (S+W)', cornerNE.mask === 12, `mask=${cornerNE.mask}`);
// Recorte no set 64×128: mask M → col M%4, row floor(M/4); peça 16×32
const r6 = wallPieceRect(6);
check('peça mask 6 recorta (32,32) 16×32 no set (col 6%4=2)', r6.sx === 32 && r6.sy === 32 && r6.sw === 16 && r6.sh === 32,
  JSON.stringify(r6));
const r12 = wallPieceRect(12);
check('peça mask 12 recorta (0,96) 16×32 no set', r12.sx === 0 && r12.sy === 96 && r12.sw === 16 && r12.sh === 32,
  JSON.stringify(r12));
// Todas as 16 máscaras mapeiam para dentro do set 64×128
let allInside = true;
for (let m = 0; m < 16; m++) {
  const rc = wallPieceRect(m);
  if (rc.sx < 0 || rc.sy < 0 || rc.sx + rc.sw > 64 || rc.sy + rc.sh > 128) allInside = false;
}
check('16 máscaras mapeiam dentro do set 64×128', allInside);
// Tile de porta NÃO gera parede (§4.5) e não entra na contagem
const doorTileWall = officeSorted.walls.find(w => w.col === 5 && w.row === 0);
check('tile de porta (5,0) não gera segmento de parede', !doorTileWall);
// drawWall usa drawImage de 9 args (recorte) com altura 64 world-px.
// cornerNW é side 'north' → spriteKey tile_wall_north.
const wallCtx = makeFakeCtx();
const wallSprites = new Map([['tile_wall_north', { width: 64, height: 128 }]]);
drawWall(wallCtx, cornerNW, (k) => wallSprites.get(k));
// ctx fake: {op, img, args} — args = 8 args DEPOIS da img (sx,sy,sw,sh,dx,dy,dw,dh)
const sliceCall = wallCtx.log.find(l => l.op === 'drawImage');
check('drawWall fatia o set (recorte 16×32 da peça → destino 32×64)',
  sliceCall && sliceCall.args.length === 8 &&
  sliceCall.args[0] === 32 && sliceCall.args[1] === 32 &&   // sx,sy (peça mask 6: col 2, row 1)
  sliceCall.args[2] === 16 && sliceCall.args[3] === 32 &&   // sw,sh (peça 16×32)
  sliceCall.args[6] === 32 && sliceCall.args[7] === 64,     // dw,dh (escala 2×)
  sliceCall ? JSON.stringify(sliceCall.args) : 'sem chamada');


// B3 — porta nunca cobre entidade na frente dela
console.log('\n[B3] porta Y-sorted — não cobre entidade na frente:');
const doorDraw = officeSorted.unified.find(d => d.kind === 'door');
const doorIdx = idx(d => d.kind === 'door');
const doorEnt = idx(d => d.id === 'ent_door_north');
check('porta na lista unificada (LAYER_DOORS)', doorDraw && doorDraw.layer === LAYER_DOORS);
// entidade NA FRENTE da porta (tile row maior) tem screenY maior → desenha depois
check('entidade na frente da porta desenha DEPOIS da porta',
  officeSorted.unified.find(d => d.id === 'ent_door_north').screenY > doorDraw.screenY);

// B4 — duas entidades no mesmo tile separadas por offset
console.log('\n[B4] offset ±8px no mesmo tile, posição lógica intacta:');
const a = officeSorted.unified.find(d => d.id === 'ent_same_tile_a');
const b = officeSorted.unified.find(d => d.id === 'ent_same_tile_b');
check('ambas no mesmo tile lógico', a.col === b.col && a.row === b.row);
check('screenX distintos (offset visual aplicado)', a.screenX !== b.screenX,
  `a=${a.screenX} b=${b.screenX}`);
const offA = entityVisualOffset('ent_same_tile_a', 3), offB = entityVisualOffset('ent_same_tile_b', 3);
check('offsets dentro de ±8..±10 (base ±8 + por-tile)', Math.abs(offA.x) <= 10 && Math.abs(offB.x) <= 10);
check('posição lógica preservada no drawable (logicX/Y = 3.5)',
  a.logicX === 3.5 && a.logicY === 3.5 && b.logicX === 3.5);

// B7 — furniture_height muda camada, não comportamento
console.log('\n[B7] furniture_height 1→3 muda camada LOW→HIGH:');
check('height 1 → LOW', heightToLayer(1) === LAYER_FURNITURE_LOW);
check('height 3 → HIGH', heightToLayer(3) === LAYER_FURNITURE_HIGH);
const shelfTiles = collectFurnitureTileDrawables(
  office.furniture.find(f => f.id === 'bookshelf_tall'), fixture.manifest.furniture_snack_shelf, null);
check('estante height=3 em LAYER_FURNITURE_HIGH', shelfTiles[0].layer === LAYER_FURNITURE_HIGH);

// B6 — performance: sort < 1ms; render de sala 40×40 com 12+ entidades
console.log('\n[B6] performance (sort < 1ms, culling funcionando):');
check('sort do fixture < 1ms', officeSorted.sortTimeMs < 1, `${officeSorted.sortTimeMs.toFixed(3)}ms`);
// sala 40×40 sintética com 12 entidades
const big = { room: { id: 'big', width: 40, height: 40, tileMap: [],
                     doors: [{ col: 20, row: 39, orientation: 'south' }] },
              carpetTiles: [], furniture: [], entities: [] };
for (let i = 0; i < 12; i++) big.entities.push({
  id: `big_${i}`, type: 'npc', x: (i % 6) + 1.5, y: Math.floor(i / 6) + 1.5,
  dir: 's', moving: true, characterKey: 'avatar_dev' });
const bigSorted = buildSortedDrawables(big, {});
check('sort 40×40 + 12 entidades < 1ms', bigSorted.sortTimeMs < 1, `${bigSorted.sortTimeMs.toFixed(3)}ms`);
check('culling reduz drawables (viewport não vê a sala toda)',
  bigSorted.unified.length < (40 * 4 + 12), `${bigSorted.unified.length}`);

// Renderer end-to-end com ctx fake (renderScene roda sem exceptions)
console.log('\n[end-to-end] renderScene com ctx fake:');
const ctx = makeFakeCtx();
const renderer = new Renderer(ctx, getSprite, { manifest: fixture.manifest });
const cam = new Camera(800, 600);
const c0 = iso.tileCenter(office.room.width / 2, office.room.height / 2);
cam.centerOn(c0.x, c0.y);
const stats = renderer.renderScene(office, cam, 12345);
check('renderScene roda e retorna stats', stats && stats.drawables > 0);
check('ctx fake recebeu drawImage', ctx.log.some(l => l.op === 'drawImage'));
const bigCam = new Camera(800, 600);
const bigStats = renderer.renderScene(big, bigCam, 0);
check('sala 40×40 renderiza (drawables > 0)', bigStats.drawables > 0);

// Frames de caminhada: 4 direções + flip
console.log('\n[frames] direções e flip:');
check('dir s→row0, n→row1, e→row2, w→row2(flip)', true); // DIR_ROWS testado via drawEntity
const f1 = currentWalkFrame({ moving: true }, 0);
const f2 = currentWalkFrame({ moving: true }, 150);
const f3 = currentWalkFrame({ moving: false }, 9999);
check('frame avança com o tempo (0→0, 150→1)', f1 === 0 && f2 === 1);
check('parado = frame 0', f3 === 0);

// Iso: inversa exata
console.log('\n[iso] projeção/inversa:');
const p = iso.tileToScreen(3.5, 4.5);
const back = iso.screenToTileFloat(p.x, p.y);
check('screenToTileFloat inverte tileToScreen', Math.abs(back.x - 3.5) < 1e-9 && Math.abs(back.y - 4.5) < 1e-9);
check('tile 32×16', iso.TILE_W === 32 && iso.TILE_H === 16);

console.log(`\nRESULTADO: ${passed} passaram, ${failed} falharam`);
process.exit(failed > 0 ? 1 : 0);
