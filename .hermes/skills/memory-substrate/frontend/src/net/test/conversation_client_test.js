// conversation_client_test.js — Testes Node puros dos handlers P1 (conversa NPC↔NPC).
// Sem servidor: wsClient falso (Map de handlers) + shim DOM mínimo.
// Valida: registro dos tipos novos, ConversationState (ciclo de status),
// bolhas (máx 3, auto-dismiss, NPC desconhecido ignora), canal separado
// (NÃO vai pro chat), fluxos existentes intactos.
import { WorldState } from '../../world/worldState.js';
import { registerHandlers } from '../handlers.js';
import {
  SERVER_TO_CLIENT, CONVERSATION_STATUSES, isValidConversationMember,
} from '../messageTypes.js';
import {
  ConversationState, SpeechBubbles, ConversationIndicators, STATUS_EMOJI,
} from '../../ui/speechBubbles.js';

let passed = 0, failed = 0;
const check = (name, cond, detail = '') => {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail ? ' — ' + detail : ''}`); }
};

// ===== Shim DOM mínimo (Node não tem document) =====
function fakeElement(tag = 'div') {
  const el = {
    tagName: tag, style: {}, children: [], isConnected: true,
    className: '', textContent: '', offsetHeight: 10,
    appendChild(c) { this.children.push(c); return c; },
    remove() {
      if (el.parentElement) {
        el.parentElement.children = el.parentElement.children.filter(c => c !== el);
        el.parentElement = null;
        el.isConnected = false;
      }
    },
  };
  return el;
}
globalThis.document = {
  createElement: (tag) => fakeElement(tag),
  getElementById: () => null,
  body: fakeElement('body'),
};

// ===== WsClient falso — mesmo contrato on/_emit =====
class FakeWs {
  constructor() { this._h = new Map(); }
  on(t, fn) { if (!this._h.has(t)) this._h.set(t, new Set()); this._h.get(t).add(fn); }
  emit(t, msg) { for (const fn of this._h.get(t) || []) fn(msg); }
  send() { return true; }
}

// ===== Mundo local com 2 NPCs =====
const ws = new FakeWs();
const state = new WorldState();
state.upsertEntity({ id: 'npc_anna', type: 'npc', name: 'Anna', col: 10, row: 5 });
state.upsertEntity({ id: 'npc_boris', type: 'npc', name: 'Boris', col: 11, row: 5 });

const conversations = new ConversationState();
const cameraStub = { worldToScreen: (x, y) => ({ x, y }) };
const speechBubbles = new SpeechBubbles(state, cameraStub, fakeElement());

// Captura de chat: linha de conversa NÃO pode vazar pro canal do player
let chatCalls = 0;
registerHandlers(ws, state, {
  conversations,
  speechBubbles,
  chat: { addMessage: () => { chatCalls++; } },
  npcDialogue: { show: () => {} },
  meetingPanel: { handleMeetingState: () => {} },
  hud: { showToast: () => {}, addLogMessage: () => {} },
});

// ===== 1. messageTypes =====
console.log('[1] messageTypes — tipos P1 registrados');
check('SERVER_TO_CLIENT.NPC_CONVERSATION_STATE === "npc.conversation.state"',
  SERVER_TO_CLIENT.NPC_CONVERSATION_STATE === 'npc.conversation.state');
check('SERVER_TO_CLIENT.NPC_CONVERSATION_LINE === "npc.conversation.line"',
  SERVER_TO_CLIENT.NPC_CONVERSATION_LINE === 'npc.conversation.line');
check('CONVERSATION_STATUSES = invited|walkingOver|participating|left',
  CONVERSATION_STATUSES.join(',') === 'invited,walkingOver,participating,left');
check('isValidConversationMember aceita membro válido',
  isValidConversationMember({ entityId: 'npc_anna', status: 'participating' }));
check('isValidConversationMember rejeita status inválido',
  !isValidConversationMember({ entityId: 'x', status: 'dancing' }));

// ===== 2. ConversationState — ciclo de vida P1 §5 =====
console.log('[2] ConversationState — invited → walkingOver → participating → left');
check('handlers.js registrou npc.conversation.state', ws._h.has('npc.conversation.state'));
check('handlers.js registrou npc.conversation.line', ws._h.has('npc.conversation.line'));

ws.emit('npc.conversation.state', {
  type: 'npc.conversation.state', conversationId: 'conv_1',
  members: [
    { entityId: 'npc_anna', status: 'invited' },
    { entityId: 'npc_boris', status: 'invited' },
  ],
});
check('invited aplicado nos dois membros',
  conversations.getStatus('npc_anna') === 'invited' &&
  conversations.getStatus('npc_boris') === 'invited');
check('isParticipating=false antes da chegada', !conversations.isParticipating('npc_anna'));

ws.emit('npc.conversation.state', {
  type: 'npc.conversation.state', conversationId: 'conv_1',
  members: [{ entityId: 'npc_anna', status: 'walkingOver' }],
});
check('delta parcial atualiza só o membro citado (anna=walkingOver, boris intacto)',
  conversations.getStatus('npc_anna') === 'walkingOver' &&
  conversations.getStatus('npc_boris') === 'invited');

ws.emit('npc.conversation.state', {
  type: 'npc.conversation.state', conversationId: 'conv_1',
  members: [
    { entityId: 'npc_anna', status: 'participating' },
    { entityId: 'npc_boris', status: 'participating' },
  ],
});
check('participating aplicado', conversations.isParticipating('npc_anna') &&
  conversations.isParticipating('npc_boris'));
check('conversationOf resolve a conversa', conversations.conversationOf('npc_anna') === 'conv_1');

// msg malformada: ignora sem quebrar
const antes = conversations.getStatus('npc_anna');
ws.emit('npc.conversation.state', { type: 'npc.conversation.state', members: 'lixo' });
ws.emit('npc.conversation.state', { type: 'npc.conversation.state', conversationId: 'conv_1', members: [{ entityId: 'npc_anna', status: 'invalid_status' }] });
check('state malformado/inválido ignora sem quebrar estado',
  conversations.getStatus('npc_anna') === antes);

// ===== 3. npc.conversation.line → bolha (canal SEPARADO) =====
console.log('[3] npc.conversation.line → bolha sobre o autor, NÃO pro chat');
ws.emit('npc.conversation.line', {
  type: 'npc.conversation.line', conversationId: 'conv_1',
  authorId: 'npc_anna', text: 'Ei Boris, viu o que aconteceu na fazenda?', ts: Date.now(),
});
check('bolha criada sobre o autor conhecido', speechBubbles.countFor('npc_anna') === 1);

// NPC que não conhecemos: ignora silenciosamente (spec f)
const linesAntes = speechBubbles.countFor('npc_anna');
let erro = null;
try {
  ws.emit('npc.conversation.line', {
    type: 'npc.conversation.line', conversationId: 'conv_1',
    authorId: 'npc_fantasma', text: 'quem é você?', ts: Date.now(),
  });
} catch (e) { erro = e; }
check('line de NPC desconhecido ignora silenciosamente (sem throw)',
  erro === null && speechBubbles.countFor('npc_fantasma') === 0 && linesAntes === 1);

// Linha de conversa NÃO vai pro chat do player (canal separado, §7)
check('nenhuma mensagem vaza pro chat do player', chatCalls === 0,
  `chatCalls=${chatCalls}`);

// Máx 3 empilhadas: 4ª descarta a mais antiga
for (let i = 0; i < 3; i++) {
  ws.emit('npc.conversation.line', {
    type: 'npc.conversation.line', conversationId: 'conv_1',
    authorId: 'npc_boris', text: `fala ${i}`, ts: Date.now(),
  });
}
check('máx 3 bolhas por NPC (4ª descarta a mais antiga)',
  speechBubbles.countFor('npc_boris') === 3);

// Auto-dismiss ~4s: envelhece as bolhas e roda update()
const queue = speechBubbles.bubbles.get('npc_boris');
for (const b of queue) b.created = Date.now() - 4100;
speechBubbles.update();
check('auto-dismiss após ~4s', speechBubbles.countFor('npc_boris') === 0);

// update() com bolhas recém-criadas mantém tudo posicionado
// (a 1ª fala da Anna ainda está viva: <4s → 2 bolhas no total)
ws.emit('npc.conversation.line', {
  type: 'npc.conversation.line', conversationId: 'conv_1',
  authorId: 'npc_anna', text: 'ainda aqui', ts: Date.now(),
});
speechBubbles.update();
check('bolhas jovens sobrevivem ao update() (2 da anna: 1ª + nova)',
  speechBubbles.countFor('npc_anna') === 2);

// ===== 4. Indicador visual de conversa =====
console.log('[4] ConversationIndicators — emoji sobre NPC em conversa');
const indicators = new ConversationIndicators(state, cameraStub, conversations);
indicators.update();
check('indicador presente p/ NPC participating', indicators.countFor('npc_anna') === 1 &&
  indicators.countFor('npc_boris') === 1);
check('emoji participating = 💬', STATUS_EMOJI.participating === '💬');

// left: indicador some
ws.emit('npc.conversation.state', {
  type: 'npc.conversation.state', conversationId: 'conv_1',
  members: [
    { entityId: 'npc_anna', status: 'left' },
    { entityId: 'npc_boris', status: 'left' },
  ],
});
indicators.update();
check('left remove indicador e limpa estado',
  conversations.getStatus('npc_anna') === null &&
  indicators.countFor('npc_anna') === 0 && indicators.countFor('npc_boris') === 0);
check('conversa sem membros ativos é removida do mapa',
  conversations.conversations.size === 0);

// ===== 5. Fluxos existentes intactos =====
console.log('[5] Fluxos existentes — sem regressão de registro');
check('chat.message ainda registrado', ws._h.has('chat.message'));
check('npc.dialogue.response ainda registrado', ws._h.has('npc.dialogue.response'));
check('world.sync ainda registrado', ws._h.has('world.sync'));
check('world.state.delta ainda registrado', ws._h.has('world.state.delta'));
check('move.path ainda registrado', ws._h.has('move.path'));
check('entity.move ainda registrado', ws._h.has('entity.move'));

// chat.message normal continua alimentando o chat do player
ws.emit('chat.message', { type: 'chat.message', from: 'p1', fromName: 'P1', content: 'oi', timestamp: Date.now() });
check('chat.message do player continua indo pro chat (canal intacto)', chatCalls === 1);

console.log(`\nCONVERSATION CLIENT: ${passed} passaram, ${failed} falharam`);
process.exit(failed > 0 ? 1 : 0);
