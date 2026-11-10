// handlers.js — Despacho das mensagens do servidor (§5) para o estado local.
// Registra TODOS os tipos no wsClient e aplica welcome/world.sync/delta/
// spawn/despawn/move/path/rejected. Chat/diálogo/reuniões mantêm a UI
// atual funcionando com a lógica INTACTA (§6.3).

import * as MT from './messageTypes.js';
import * as Movement from '../world/movement.js';

export function registerHandlers(wsClient, worldState, ui = {}) {
  // ui = { chat, npcDialogue, meetingPanel, hud, camera, onSelfSpawned }
  // — componentes opcionais; ausentes = handlers de UI viram no-op.

  const S = MT.SERVER_TO_CLIENT;

  // ===== Estado do mundo =====

  wsClient.on(S.WELCOME, (msg) => {
    worldState.applyWelcome(msg);
    ui.onWelcome?.(msg);
  });

  wsClient.on(S.WORLD_SYNC, (msg) => {
    // Snapshot na (re)conexão (C2): limpa paths ativos — posições vêm no sync
    Movement.clearActivePaths();
    worldState.applyWorldSync(msg);
    ui.onWorldSync?.(msg);
  });

  wsClient.on(S.ENTITY_SPAWN, (msg) => {
    worldState.upsertEntity(msg.entity);
    ui.hud?.addLogMessage?.({ type: 'entity',
      content: `Entity spawned: ${msg.entity?.type} (${msg.entity?.id})`, timestamp: Date.now() });
  });

  wsClient.on(S.ENTITY_DESPAWN, (msg) => {
    worldState.removeEntity(msg.entityId);
    Movement.clearActivePath?.(msg.entityId);
    ui.hud?.addLogMessage?.({ type: 'entity',
      content: `Entity despawned: ${msg.entityId} (${msg.reason})`, timestamp: Date.now() });
  });

  // ===== Movimento (§3.3: path uma vez, move = âncora) =====

  wsClient.on(S.MOVE_PATH, (msg) => {
    Movement.onMovePath(worldState, msg);
  });

  wsClient.on(S.ENTITY_MOVE, (msg) => {
    Movement.onEntityMove(worldState, msg);
    ui.hud?.onEntityMove?.(msg);
  });

  wsClient.on(S.MOVE_REJECTED, (msg) => {
    // Cliente NÃO move o sprite (§3.2.5) — só toast discreto
    const reasons = {
      destination_blocked: 'Destino bloqueado',
      no_path: 'Sem caminho até o destino',
      too_far: 'Destino muito distante',
    };
    ui.hud?.showToast?.('Movimento', reasons[msg.reason] || `Recusado: ${msg.reason}`, 'warning');
    ui.onMoveRejected?.(msg);
  });

  // ===== Deltas de blockedTiles (§5.2 world.state.delta) =====

  wsClient.on(S.WORLD_STATE_DELTA, (msg) => {
    worldState.applyDelta(msg.changes);
    ui.onWorldDelta?.(msg);
  });

  // ===== UI INTACTA: chat / diálogo / reuniões (§6.3) =====

  wsClient.on(S.CHAT_MESSAGE, (msg) => {
    // chat.message: { from, fromName, content, timestamp } (§5.2)
    ui.chat?.addMessage({
      msg_id: `${msg.timestamp}_${msg.from}`,
      sender_name: msg.fromName,
      sender_id: msg.from,
      content: msg.content,
      ts: msg.timestamp,
    });
    ui.hud?.onChatMessage?.({ sender_name: msg.fromName, content: msg.content, ts: msg.timestamp });
  });

  wsClient.on(S.NPC_DIALOGUE_RESPONSE, (msg) => {
    // payload atual, intacto (§5.3) — UI de diálogo consome como antes
    ui.npcDialogue?.show(msg);
    ui.hud?.onNPCDialogueResponse?.(msg);
  });

  wsClient.on(S.MEETING_STATE, (msg) => {
    ui.meetingPanel?.handleMeetingState?.(msg);
    ui.onMeetingState?.(msg);
  });

  // ===== Conversa NPC↔NPC (P1 — BLUEPRINT-P1-CONVERSA §3) =====
  // Canal SEPARADO: fala ambiente em bolha sobre o sprite; NÃO vai pro
  // chat do player (§7). Fluxos existentes (npc.dialogue.*, chat.*,
  // movimento, world.sync/delta) permanecem INTACTOS acima.

  wsClient.on(S.NPC_CONVERSATION_STATE, (msg) => {
    // { conversationId, members:[{entityId,status}] } — status ∈ P1 §3.1.
    // Só atualiza o mapa local p/ UI/indicador; nenhum efeito colateral.
    ui.conversations?.applyState?.(msg);
    ui.onConversationState?.(msg);
  });

  wsClient.on(S.NPC_CONVERSATION_LINE, (msg) => {
    // { conversationId, authorId, text, ts } — fala ambiente (P1 §3.2).
    // NPC que não conhecemos (fora do worldState local): ignora silenciosamente.
    const author = worldState.getEntity(msg?.authorId);
    if (!author) return;
    ui.speechBubbles?.addLine?.(msg);
    ui.onConversationLine?.(msg);
  });

  // meeting.* variados (join/leave/…) — repassados ao painel sem inspeção
  for (const type of ['meeting.join', 'meeting.leave', 'meeting.speak', 'meeting.list']) {
    wsClient.on(type, (msg) => ui.meetingPanel?.handleMeetingState?.(msg));
  }

  // ===== Erros e controle =====

  wsClient.on(S.ERROR, (msg) => {
    // unknown_type etc. (§5.3) — não derruba a sessão
    ui.hud?.showToast?.('Servidor', `${msg.code}: ${msg.message}`, 'danger');
  });

  wsClient.on(S.PONG, (msg) => {
    if (typeof msg.serverTime === 'number') wsClient.lastPongAt = Date.now();
  });

  // ===== Ciclo de conexão =====

  // (Re)conexão: reenvia hello p/ servidor reidentificar e disparar world.sync (C2)
  wsClient.on('ws.open', () => {
    ui.hud?.addLogMessage?.({ type: 'system', content: 'Conectado ao servidor', timestamp: Date.now() });
    let name = 'Jogador', characterKey = 'avatar_player'; // chave REAL do manifest
    try { // localStorage pode não existir (testes em Node)
      name = localStorage.getItem('hermes-corp-player-name') || name;
      characterKey = localStorage.getItem('hermes-corp-character') || characterKey;
    } catch { /* fora do browser: defaults */ }
    wsClient.sendHello(name, characterKey);
  });

  wsClient.on('ws.close', () => {
    ui.hud?.addLogMessage?.({ type: 'warning', content: 'Desconectado — reconectando...', timestamp: Date.now() });
  });
}
