// qa_envelope_test.js — Teste de integração Node contra o servidor REAL (8080).
// Usa os módulos reais do cliente (WorldState, Movement, registerHandlers, WsClient)
// e valida se welcome/move.path/entity.move são aplicados de fato no estado.
import { WorldState } from '../../world/worldState.js';
import * as Movement from '../../world/movement.js';
import { registerHandlers } from '../handlers.js';
import { WsClient } from '../wsClient.js';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let passed = 0, failed = 0;
const check = (name, cond, detail = '') => {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail ? ' — ' + detail : ''}`); }
};

const ws = new WsClient('ws://127.0.0.1:8080/ws');
const state = new WorldState();
registerHandlers(ws, state, {
  chat: { addMessage: () => {} },
  npcDialogue: { show: () => {} },
  meetingPanel: { handleMeetingState: () => {} },
  hud: { showToast: () => {}, addLogMessage: () => {} },
});

console.log('[QA] conectando ao servidor real (8080, proxy → 8081)...');
ws.connect();

// espera welcome
{
  const t0 = Date.now();
  while (state.selfEntityId === null && Date.now() - t0 < 8000) await sleep(50);
  check('welcome aplicado — selfEntityId definido', state.selfEntityId !== null,
    'welcome não chegou/foi aplicado');
}

if (state.selfEntityId) {
  check('room aplicado (id reception, 60×15)',
    state.room?.id === 'reception' && state.room?.width === 60 && state.room?.height === 15,
    `room=${JSON.stringify(state.room && { id: state.room.id, w: state.room.width, h: state.room.height })}`);
  check('tileMap aplicado (15 rows × 60 cols, row0 WALL)',
    Array.isArray(state.room?.tileMap) && state.room.tileMap.length === 15 &&
    state.room.tileMap[0].length === 60 && state.room.tileMap[0][0] === 0);
  check('blockedTiles aplicado (Set não vazio)', state.blockedTiles.size > 0,
    `size=${state.blockedTiles.size}`);
  check('entities aplicadas (≥2: player + NPC)', state.entities.size >= 2,
    `size=${state.entities.size}`);
  const self = state.getSelfEntity();
  check('self entity com col/row numéricos',
    Number.isInteger(self?.col) && Number.isInteger(self?.row),
    `col=${self?.col} row=${self?.row}`);

  // move.request real
  const targetCol = self.col === 26 ? 25 : 26;
  ws.sendMoveRequest(self.id, targetCol, self.row);
  const t0 = Date.now();
  while (Date.now() - t0 < 4000) {
    await sleep(50);
    if (Movement.getActivePath(self.id)) break;
  }
  check('move.path → path ativo criado no Movement', Movement.getActivePath(self.id) !== null,
    'nenhum path ativo após 4s');
  // posição render interpola?
  await sleep(150);
  const walk = Movement.getActivePath(self.id);
  if (walk) {
    Movement.update(state, ws.nowServerTime() + 300);
    check('interpolação avança x/y', self.x !== undefined && self.y !== undefined,
      `x=${self.x} y=${self.y}`);
  }
  // âncora final moving=false chega?
  const t1 = Date.now();
  while (Date.now() - t1 < 3000) {
    await sleep(50);
    if (!self.moving && !Movement.getActivePath(self.id)) break;
  }
  check('âncora final entity.move(moving=false) aplicada', !Movement.getActivePath(self.id),
    'path ainda ativo após 3s');

  // chat round-trip via handler real
  let chatGot = null;
  ws.on('chat.message', (m) => { chatGot = m; });
  ws.sendChatMessage('qa-roundtrip');
  const t2 = Date.now();
  while (!chatGot && Date.now() - t2 < 4000) await sleep(50);
  check('chat.message ecoado com from/fromName/content',
    chatGot && (chatGot.fromName || chatGot.from) && chatGot.content === 'qa-roundtrip',
    chatGot ? `keys=${Object.keys(chatGot).join(',')}` : 'sem eco');
}

ws.disconnect();
Movement.clearActivePaths();
console.log(`\nQA ENVELOPE: ${passed} passaram, ${failed} falharam`);
process.exit(failed > 0 ? 1 : 0);
