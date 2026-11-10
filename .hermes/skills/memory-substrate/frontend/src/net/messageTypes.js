// messageTypes.js — Espelho do PROTOCOLO CONGELADO (BLUEPRINT §5)
// NÃO editar sem atualizar a §5 do BLUEPRINT_CORE.md primeiro.
// Envelope único: { "type": "<nome>", ...payload } — JSON sobre WS, UTF-8.
// Tile = par [col, row] (array, nunca objeto).

// ---------- Constantes compartilhadas ----------
export const DEFAULT_MOVE_TIME_MS = 350; // ms por tile (§3.3; servidor envia moveTimeMs no welcome)

// Tipos de tile (§2.1) — espelham o enum do servidor
export const TILE_WALL = 0;      // parede — NÃO caminhável
export const TILE_FLOOR_MIN = 1; // FLOOR_1..FLOOR_9 — caminháveis
export const TILE_FLOOR_MAX = 9;
export const TILE_VOID = 255;   // fora do escritório — NÃO caminhável

// Direções (§5.2 entity.move)
export const DIRECTIONS = ['n', 's', 'e', 'w'];

// Razões de rejeição (§5.2 move.rejected)
export const MOVE_REJECT_REASONS = ['destination_blocked', 'no_path', 'too_far'];

// Status de membro de conversa NPC↔NPC (BLUEPRINT P1 §3.1)
export const CONVERSATION_STATUSES = ['invited', 'walkingOver', 'participating', 'left'];

// Validador leve de membro de conversa: { entityId, status } (P1 §3.1)
export function isValidConversationMember(m) {
  return m !== null && typeof m === 'object' &&
    typeof m.entityId === 'string' && m.entityId.length > 0 &&
    CONVERSATION_STATUSES.includes(m.status);
}

// ---------- Cliente → Servidor (§5.1) ----------
export const CLIENT_TO_SERVER = Object.freeze({
  CLIENT_HELLO: 'client.hello',       // { name, characterKey }
  MOVE_REQUEST: 'move.request',      // { entityId, targetCol, targetRow }
  CHAT_MESSAGE: 'chat.message',      // { content }
  NPC_DIALOGUE_REQUEST: 'npc.dialogue.request', // { npcId } — intacto
  PING: 'ping',                      // {}
  // meeting.* — payloads atuais, intactos, repassados sem inspeção
});

// ---------- Servidor → Cliente (§5.2) ----------
export const SERVER_TO_CLIENT = Object.freeze({
  WELCOME: 'welcome',                // { entityId, name, room{...}, entities, moveTimeMs, serverTime }
  WORLD_SYNC: 'world.sync',          // { entities, serverTime } — snapshot na (re)conexão
  ENTITY_SPAWN: 'entity.spawn',      // { entity }
  ENTITY_DESPAWN: 'entity.despawn',  // { entityId, reason }
  ENTITY_MOVE: 'entity.move',        // { entityId, col, row, moving, dir, serverTime } — âncora
  MOVE_PATH: 'move.path',            // { entityId, path, startedAt, moveTimeMs }
  MOVE_REJECTED: 'move.rejected',    // { entityId, targetCol, targetRow, reason }
  WORLD_STATE_DELTA: 'world.state.delta', // { changes, serverTime }
  CHAT_MESSAGE: 'chat.message',      // { from, fromName, content, timestamp }
  NPC_DIALOGUE_RESPONSE: 'npc.dialogue.response', // intacto
  NPC_CONVERSATION_STATE: 'npc.conversation.state', // P1 §3.1 — estado/delta da conversa NPC↔NPC
  NPC_CONVERSATION_LINE: 'npc.conversation.line',   // P1 §3.2 — fala ambiente (NÃO vai pro chat)
  MEETING_STATE: 'meeting.state',    // intacto
  ERROR: 'error',                    // { code, message }
  PONG: 'pong',                      // { serverTime }
});

// ---------- Validadores leves (defensivos; servidor é autoritativo) ----------

// move.path.path: array de pares [col, row]
export function isValidPath(path) {
  return Array.isArray(path) && path.every(t => Array.isArray(t) && t.length === 2 &&
    Number.isInteger(t[0]) && Number.isInteger(t[1]));
}

// entity.move.dir
export function isValidDir(dir) {
  return DIRECTIONS.includes(dir);
}

// world.state.delta.changes: [{op, kind, col, row}]
export function isValidDelta(change) {
  return change && (change.op === 'add' || change.op === 'remove' || change.op === 'update') &&
    change.kind === 'blockedTile' &&
    Number.isInteger(change.col) && Number.isInteger(change.row);
}

// Tipo de tile é caminhável (FLOOR_1..FLOOR_9) — §2.1
export function isFloorTile(tileValue) {
  return tileValue >= TILE_FLOOR_MIN && tileValue <= TILE_FLOOR_MAX;
}
