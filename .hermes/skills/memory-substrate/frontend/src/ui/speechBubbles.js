// speechBubbles.js — Bolhas de fala ambiente + estado de conversa NPC↔NPC (P1 cliente).
//
// CANAL SEPARADO (BLUEPRINT P1 §7): npc.conversation.line é fala ambiente —
// NUNCA vai para o chat do player. Bolhas são divs DOM posicionadas sobre o
// sprite do NPC, recalculadas por frame a partir da posição render (x/y
// contínuos interpolados pelo movement.js) projetada via camera.worldToScreen.
//
// Dois componentes independentes:
//   - ConversationState: mapa NPC → {conversationId, status} para UI/indicador.
//   - SpeechBubbles: fila por NPC, máx 3 bolhas empilhadas, auto-dismiss ~4s.
//
// NÃO toca em nenhum fluxo existente (npc.dialogue.*, chat.*, movimento).

import { isValidConversationMember } from '../net/messageTypes.js';

// Emoji por status (P1 §3.1) — indicador leve, v1 sem sprite novo (§2)
export const STATUS_EMOJI = {
  invited: '❓',
  walkingOver: '🚶',
  participating: '💬',
  left: null, // sem indicador após sair
};

// ===== ConversationState — estado local das conversas =====

export class ConversationState {
  constructor() {
    // Map<entityId, { conversationId, status, updatedAt }>
    this.members = new Map();
    // Map<conversationId, Set<entityId>> — membros por conversa ativa
    this.conversations = new Map();
  }

  /** Aplica um npc.conversation.state (P1 §3.1). Retorna true se aplicou. */
  applyState(msg) {
    if (!msg || typeof msg.conversationId !== 'string' || !Array.isArray(msg.members)) {
      return false;
    }
    const convId = msg.conversationId;
    let conv = this.conversations.get(convId);
    if (!conv) {
      conv = new Set();
      this.conversations.set(convId, conv);
    }

    let applied = 0;
    for (const m of msg.members) {
      if (!isValidConversationMember(m)) continue; // membro inválido: ignora
      const { entityId, status } = m;
      if (status === 'left') {
        // Saiu: limpa estado do NPC; conversa sem participantes ativos é removida
        this.members.delete(entityId);
        conv.delete(entityId);
        if (conv.size === 0) this.conversations.delete(convId);
      } else {
        this.members.set(entityId, {
          conversationId: convId,
          status,
          updatedAt: Date.now(),
        });
        conv.add(entityId);
      }
      applied++;
    }
    return applied > 0;
  }

  /** Status atual de um NPC (ou null se não está em conversa). */
  getStatus(entityId) {
    return this.members.get(entityId)?.status ?? null;
  }

  /** NPC está participando de conversa? (indicador visual) */
  isParticipating(entityId) {
    return this.getStatus(entityId) === 'participating';
  }

  /** Conversa ativa do NPC (id) ou null. */
  conversationOf(entityId) {
    return this.members.get(entityId)?.conversationId ?? null;
  }

  /** Limpa tudo (reconnect/world.sync não exige — mas disponível p/ testes). */
  clear() {
    this.members.clear();
    this.conversations.clear();
  }
}

// ===== SpeechBubbles — bolhas DOM sobre os sprites =====

const BUBBLE_LIFETIME_MS = 4000;  // ~4s por bolha (spec)
const BUBBLE_MAX_PER_NPC = 3;     // máx ~3 empilhadas (spec)
const BUBBLE_GAP_PX = 4;          // espaçamento vertical entre bolhas
const BUBBLE_BASE_OFFSET_PX = 38; // altura acima do "pé" do sprite (frame 16×32)

export class SpeechBubbles {
  constructor(worldState, camera, container = null) {
    this.worldState = worldState; // posições render (x/y contínuos)
    this.camera = camera;         // worldToScreen(x, y)
    this.container = container;   // HTMLElement pai das bolhas (null = lazy)
    // Map<entityId, Array<{ el, created, text }>> — fila por NPC
    this.bubbles = new Map();
  }

  /** Garante o container DOM (cria uma vez, id fixo). */
  _ensureContainer() {
    if (this.container && document.getElementById('speech-bubbles') !== this.container) {
      if (!this.container.isConnected) {
        (document.getElementById('game-container') || document.body).appendChild(this.container);
      }
    } else if (!this.container) {
      const el = document.getElementById('speech-bubbles');
      if (el) {
        this.container = el;
      } else {
        this.container = document.createElement('div');
        this.container.id = 'speech-bubbles';
        (document.getElementById('game-container') || document.body).appendChild(this.container);
      }
    }
    return this.container;
  }

  /**
   * Nova fala de NPC em conversa (npc.conversation.line, P1 §3.2).
   * Retorna true se criou bolha; false se NPC desconhecido/inválido
   * (ignora silenciosamente — coerência com worldState local).
   */
  addLine(msg) {
    if (!msg || typeof msg.authorId !== 'string' || typeof msg.text !== 'string') {
      return false;
    }
    const ent = this.worldState.getEntity(msg.authorId);
    if (!ent) return false; // NPC que não conhecemos: ignora silenciosamente

    const queue = this.bubbles.get(msg.authorId) || [];
    // Cota cheia: descarta a MAIS ANTIGA (auto-dismiss forçado)
    while (queue.length >= BUBBLE_MAX_PER_NPC) {
      const oldest = queue.shift();
      this._remove(oldest);
    }

    const el = document.createElement('div');
    el.className = 'speech-bubble';
    el.textContent = msg.text; // textContent: zero XSS, zero HTML do servidor
    const bubble = { el, created: Date.now(), text: msg.text };
    queue.push(bubble);
    this.bubbles.set(msg.authorId, queue);
    this._renderNPC(msg.authorId); // posiciona imediatamente
    return true;
  }

  /** Remove uma bolha do DOM. */
  _remove(bubble) {
    bubble.el?.remove();
  }

  /** Posiciona as bolhas de UM NPC sobre o sprite (posição render atual). */
  _renderNPC(entityId) {
    const queue = this.bubbles.get(entityId);
    if (!queue || queue.length === 0) {
      this.bubbles.delete(entityId);
      return;
    }
    const ent = this.worldState.getEntity(entityId);
    if (!ent || !this.camera) { // NPC sumiu (despawn): descarta bolhas
      for (const b of queue) this._remove(b);
      this.bubbles.delete(entityId);
      return;
    }

    // Posição de tela do sprite: mesmo cálculo do render B (iso.tileToScreen)
    // — mas bolhas são DOM, então usamos camera.worldToScreen sobre a
    // projeção iso (TILE_W=32/TILE_H=16, espelha render/iso.js).
    const wx = ent.x, wy = ent.y; // contínuo (unidades de tile)
    const isoX = (wx - wy) * 16;   // tileToScreen: x = (tx - ty) * TILE_W/2
    const isoY = (wx + wy) * 8;    // y = (tx + ty) * TILE_H/2
    const p = this.camera.worldToScreen
      ? this.camera.worldToScreen(isoX, isoY)
      : { x: isoX, y: isoY };

    let yOffset = -BUBBLE_BASE_OFFSET_PX;
    for (let i = queue.length - 1; i >= 0; i--) {
      const b = queue[i];
      b.el.style.left = `${p.x}px`;
      b.el.style.bottom = `${-yOffset}px`; // sobe de baixo do sprite
      yOffset -= b.el.offsetHeight + BUBBLE_GAP_PX;
      // anchor: bottom no ponto do sprite — transform translate(-50%, 100%) no CSS
      if (!b.el.isConnected) this._ensureContainer().appendChild(b.el);
    }
  }

  /**
   * Tick por frame (chamado no gameLoop): reposiciona bolhas (NPC anda)
   * e faz o auto-dismiss das que passaram do tempo de vida.
   * Sem bolhas = custo zero (early return).
   */
  update() {
    if (this.bubbles.size === 0) return;
    const now = Date.now();
    let dirty = false;
    for (const [entityId, queue] of this.bubbles) {
      // Auto-dismiss: remove expiradas da cauda (mais antigas primeiro)
      while (queue.length > 0 && now - queue[0].created >= BUBBLE_LIFETIME_MS) {
        this._remove(queue.shift());
        dirty = true;
      }
      if (queue.length === 0) continue;
      this._renderNPC(entityId);
    }
    // Limpa filas vazias
    for (const [entityId, queue] of this.bubbles) {
      if (queue.length === 0) this.bubbles.delete(entityId);
    }
  }

  /** Bolhas ativas de um NPC (p/ teste/inspeção). */
  countFor(entityId) {
    return this.bubbles.get(entityId)?.length ?? 0;
  }

  /** Limpa tudo (testes). */
  clear() {
    for (const queue of this.bubbles.values()) {
      for (const b of queue) this._remove(b);
    }
    this.bubbles.clear();
  }
}

// ===== ConversationIndicators — emoji/pontinho sobre NPC em conversa =====
// Indicador leve v1 (P1 §2: sem sprite novo, render não ganha overlay
// obrigatório): um pequeno div DOM com o emoji do status do membro,
// posicionado sobre o sprite de TODO NPC que está em conversa.
// participating = 💬; walkingOver = 🚶; invited = ❓; left = sem indicador.

export class ConversationIndicators {
  constructor(worldState, camera, conversations) {
    this.worldState = worldState;
    this.camera = camera;
    this.conversations = conversations; // ConversationState
    this.container = null;               // HTMLElement (lazy)
    this.indicators = new Map();         // Map<entityId, HTMLElement>
  }

  _ensureContainer() {
    if (this.container && !this.container.isConnected) {
      (document.getElementById('game-container') || document.body).appendChild(this.container);
    } else if (!this.container) {
      const el = document.getElementById('conversation-indicators');
      if (el) {
        this.container = el;
      } else {
        this.container = document.createElement('div');
        this.container.id = 'conversation-indicators';
        (document.getElementById('game-container') || document.body).appendChild(this.container);
      }
    }
    return this.container;
  }

  /**
   * Tick por frame: cria/remove/posiciona os indicadores.
   * Sem NPCs em conversa = custo quase zero (varredura do mapa pequeno).
   */
  update() {
    const c = this.conversations;
    if (!c || c.members.size === 0) {
      if (this.indicators.size > 0) this._removeAll();
      return;
    }

    // Remove indicadores de membros que saíram ou sumiram do worldState
    for (const [entityId, el] of this.indicators) {
      const status = c.getStatus(entityId);
      if (!status || !this.worldState.getEntity(entityId)) {
        el.remove();
        this.indicators.delete(entityId);
      }
    }

    for (const [entityId, info] of c.members) {
      const ent = this.worldState.getEntity(entityId);
      if (!ent) continue;
      const emoji = STATUS_EMOJI[info.status];
      if (!emoji) continue; // left: sem indicador
      let el = this.indicators.get(entityId);
      if (!el) {
        el = document.createElement('div');
        el.className = 'conversation-indicator';
        el.textContent = emoji;
        this.indicators.set(entityId, el);
        this._ensureContainer().appendChild(el);
      }
      // Mesma projeção iso→tela das bolhas, um pouco acima do sprite
      const isoX = (ent.x - ent.y) * 16;
      const isoY = (ent.x + ent.y) * 8;
      const p = this.camera.worldToScreen
        ? this.camera.worldToScreen(isoX, isoY)
        : { x: isoX, y: isoY };
      el.style.left = `${p.x + 10}px`;
      el.style.top = `${p.y - 44}px`;
    }
  }

  _removeAll() {
    for (const el of this.indicators.values()) el.remove();
    this.indicators.clear();
  }

  countFor(entityId) {
    return this.indicators.has(entityId) ? 1 : 0;
  }
}
