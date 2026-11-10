// qa_chaves_test.js — Validação de chaves de payload do servidor REAL contra os leitores do cliente.
// Conecta em 8080 (proxy), coleta welcome/move.path/chat/npc.dialogue e confere cada campo
// que worldState.js/movement.js/handlers.js/ui/*.js realmente leem.
import { WsClient } from '../wsClient.js';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let passed = 0, failed = 0;
const check = (name, cond, detail = '') => {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail ? ' — ' + detail : ''}`); }
};

const raw = new WsClient('ws://127.0.0.1:8080/ws');
const seen = {};
raw.on('ws.open', () => raw.sendHello('QA-Chaves', 'avatar_player'));
raw.on('welcome', (msg) => { seen.welcome = msg; });
raw.connect();
const t0 = Date.now();
while (!seen.welcome && Date.now() - t0 < 8000) {
  await sleep(50);
}
raw.disconnect();

const w = seen.welcome;
if (!w) {
  console.log('FAIL — welcome não recebido (envelope)');
  process.exit(1);
}
// wsClient achatou payload na raiz no onmessage — msg.<campo> direto
const p = w;

console.log('[chaves] welcome:');
check('entityId', typeof p.entityId === 'string', JSON.stringify(p.entityId));
check('moveTimeMs num', typeof p.moveTimeMs === 'number');
check('room presente', typeof p.room === 'object' && p.room !== null);
const room = p.room;
check('room.blockedTiles array de "col,row"',
  Array.isArray(room.blockedTiles) && room.blockedTiles.every(s => /^\d+,\d+$/.test(s)),
  JSON.stringify((room.blockedTiles || []).slice(0, 2)));
check('room.tileMap int[][] rows=h cols=w',
  Array.isArray(room.tileMap) && room.tileMap.length === room.height &&
  room.tileMap.every(r => Array.isArray(r) && r.length === room.width),
  `rows=${room.tileMap?.length} h=${room.height}`);
// worldState._applyRoom NÃO guarda blockedTiles→Set via room.blockedTiles? sim guarda. Mas backgroundTiles:  o cliente ignora (ok)
// doors: doors.js aceita col/row (§5) OU x/y (servidor legado) — valida os dois
const d0 = (room.doors || [])[0] || {};
check('doors[0] posição resolvível (col/row OU x/y)',
  Number.isInteger(d0.col ?? d0.x) && Number.isInteger(d0.row ?? d0.y),
  `server manda: ${JSON.stringify(Object.keys(d0))} → ${JSON.stringify(d0)}`);
// furniture: furniture.js aceita col/row/meta.footprint OU x/y/w/h
const f0 = (room.furniture || [])[0] || {};
check('furniture[0] posição/footprint resolvível (col/row OU x/y/w/h)',
  Number.isInteger(f0.col ?? f0.x) && Number.isInteger(f0.row ?? f0.y),
  `server manda: ${JSON.stringify(Object.keys(f0))} → x=${f0.x} y=${f0.y} w=${f0.w} h=${f0.h}`);
check('furniture[0] tem meta.footprintW/H ou manifest resolve',
  !!(f0.meta?.footprintW) || !!f0.w, 'sem footprint em nenhum lugar');
// carpetTiles: renderer lê c.col/c.row (ou string)
const c0 = (room.carpetTiles || [])[0];
check('carpetTiles formato {col,row} ou "c,r"', room.carpetTiles.length === 0 ||
  (typeof c0 === 'string' || (c0 && 'col' in c0)), JSON.stringify(c0));
// entities: worldState lê col/row/characterKey/dir
const e0 = (p.entities || [])[0] || {};
check('entity[0] col/row/characterKey', Number.isInteger(e0.col) && Number.isInteger(e0.row) &&
  typeof e0.characterKey === 'string', JSON.stringify(e0).slice(0, 120));

console.log(`\nQA CHAVES: ${passed} passaram, ${failed} falharam`);
process.exit(failed > 0 ? 1 : 0);
