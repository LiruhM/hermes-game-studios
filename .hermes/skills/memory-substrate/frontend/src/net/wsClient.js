// wsClient.js — Cliente WebSocket do Hermes-Corp (§5, §7.3)
// Conexão em ws://127.0.0.1:8080/ws, reconexão exponencial com jitter,
// ping/pong periódico, reconciliação de clock via serverTime (offset do welcome/pong).
// NÃO conhece lógica de jogo — só transporte e eventos.

import { CLIENT_TO_SERVER, SERVER_TO_CLIENT } from './messageTypes.js';

// Parâmetros de conexão (leves para o 5700U — §1.4)
const DEFAULT_URL = 'ws://127.0.0.1:8080/ws';
const MAX_RECONNECT_ATTEMPTS = Infinity; // nunca desiste (jogo desktop local)
const BASE_RECONNECT_DELAY_MS = 500;     // backoff exponencial: 0.5s → 1s → 2s → 4s...
const MAX_RECONNECT_DELAY_MS = 10000;    // teto 10s + jitter
const JITTER_MS = 200;                   // evita thundering herd em multi-abas
const PING_INTERVAL_MS = 10000;          // heartbeat (A7: ping/pong < 20ms local)
const CLOCK_SAMPLES = 8;                 // amostras p/ mediana do offset

export class WsClient {
  constructor(url = DEFAULT_URL) {
    this.url = url;
    this.ws = null;
    this.connected = false;
    this.closedByUser = false;

    // Eventos: Map<type, Set<handler>> — sem leak em reconnect (C7)
    this._handlers = new Map();
    this._sentLog = [];                  // log de envios p/ teste C4 (limitado)
    this._sentLogMax = 100;

    // Reconexão
    this._reconnectAttempts = 0;
    this._reconnectTimer = null;

    // Clock offset (serverTime - localTime) — mediana das amostras
    this._clockSamples = [];
    this.clockOffsetMs = 0;

    // Ping/pong
    this._pingTimer = null;
    this.lastPongAt = 0;
  }

  // ===== Ciclo de vida =====

  connect() {
    if (this.connected || this._reconnectTimer) return;
    this.closedByUser = false;
    this._openSocket();
  }

  disconnect() {
    // Fechamento explícito do usuário: NÃO reconecta
    this.closedByUser = true;
    this._stopPing();
    if (this._reconnectTimer) { clearTimeout(this._reconnectTimer); this._reconnectTimer = null; }
    if (this.ws) { this.ws.close(); this.ws = null; }
    this.connected = false;
  }

  _openSocket() {
    const ws = new WebSocket(this.url);
    this.ws = ws;

    ws.onopen = () => {
      if (this.ws !== ws) return; // socket obsoleto
      this.connected = true;
      this._reconnectAttempts = 0;
      this._emit('ws.open', {});
      this._startPing();
    };

    ws.onmessage = (event) => {
      if (this.ws !== ws) return;
      try {
        const msg = JSON.parse(event.data);
        if (msg && typeof msg.type === 'string') {
          // Compat de envelope: servidor real manda {type, payload, ...} (§5);
          // mock legado manda flat {type, ...campos}. Achatamos payload na raiz
          // UM nível — handlers leem sempre msg.<campo>. Payloads não-dict
          // (strings, arrays) são ignorados com segurança.
          if (msg.payload !== undefined && typeof msg.payload === 'object' && msg.payload !== null && !Array.isArray(msg.payload)) {
            Object.assign(msg, msg.payload);
          }
          this._updateClockFromMessage(msg);
          this._emit(msg.type, msg);
        }
      } catch {
        // JSON inválido: ignora silenciosamente (não derruba a sessão)
      }
    };

    ws.onclose = () => {
      if (this.ws !== ws) return;
      this.connected = false;
      this._stopPing();
      this._emit('ws.close', {});
      this._scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose vem em seguida; reconexão é tratada lá
    };
  }

  _scheduleReconnect() {
    if (this.closedByUser || this._reconnectTimer) return;
    if (this._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return;

    const delay = Math.min(
      BASE_RECONNECT_DELAY_MS * Math.pow(2, this._reconnectAttempts),
      MAX_RECONNECT_DELAY_MS
    ) + Math.random() * JITTER_MS;
    this._reconnectAttempts++;

    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      if (!this.connected && !this.closedByUser) this._openSocket();
    }, delay);
  }

  // ===== Ping/pong =====

  _startPing() {
    this._stopPing();
    this._pingTimer = setInterval(() => {
      this.send(CLIENT_TO_SERVER.PING, {});
    }, PING_INTERVAL_MS);
  }

  _stopPing() {
    if (this._pingTimer) { clearInterval(this._pingTimer); this._pingTimer = null; }
  }

  // ===== Clock offset (§5.3: serverTime em toda msg de movimento/estado) =====

  _updateClockFromMessage(msg) {
    // Amostra offset em welcome, pong e move.path (mensagens que carregam serverTime/startedAt)
    const serverTime = msg.serverTime ?? (msg.type === SERVER_TO_CLIENT.MOVE_PATH ? msg.startedAt : undefined);
    if (typeof serverTime !== 'number') return;
    const sample = serverTime - Date.now();
    this._clockSamples.push(sample);
    if (this._clockSamples.length > CLOCK_SAMPLES) this._clockSamples.shift();
    // Mediana: robusta contra spikes de latência
    const sorted = [...this._clockSamples].sort((a, b) => a - b);
    this.clockOffsetMs = sorted[Math.floor(sorted.length / 2)];
  }

  // Converte hora local → hora do servidor (para interpolação §3.3)
  localToServerTime(localMs) {
    return localMs + this.clockOffsetMs;
  }

  // Hora do servidor "agora" — base da interpolação de move.path
  nowServerTime() {
    return Date.now() + this.clockOffsetMs;
  }

  // ===== Envio =====

  send(type, payload = {}) {
    if (!this.connected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    // Envelope §5: { type, ...payload } — chamas ao nível raiz
    const msg = { type, ...payload };
    this._logSent(type, payload);
    this.ws.send(JSON.stringify(msg));
    return true;
  }

  _logSent(type, payload) {
    this._sentLog.push({ type, payload, ts: Date.now() });
    if (this._sentLog.length > this._sentLogMax) this._sentLog.shift();
  }

  // Últimos N envios de um tipo — usado pelo teste C4 (um move.request por clique)
  sentOfType(type, sinceTs = 0) {
    return this._sentLog.filter(s => s.type === type && s.ts >= sinceTs);
  }

  // Helpers de envio (§5.1)
  sendHello(name, characterKey = 'avatar_player') { // chave REAL do manifest (43 entradas)
    return this.send(CLIENT_TO_SERVER.CLIENT_HELLO, { name, characterKey });
  }

  sendMoveRequest(entityId, targetCol, targetRow) {
    return this.send(CLIENT_TO_SERVER.MOVE_REQUEST, { entityId, targetCol, targetRow });
  }

  sendChatMessage(content) {
    return this.send(CLIENT_TO_SERVER.CHAT_MESSAGE, { content });
  }

  // Repasse genérico p/ meeting.* e npc.dialogue.* (payloads intactos, §5.3)
  sendRaw(type, payload) {
    return this.send(type, payload);
  }

  // ===== Eventos =====

  on(type, handler) {
    if (!this._handlers.has(type)) this._handlers.set(type, new Set());
    this._handlers.get(type).add(handler);
    return () => this.off(type, handler);
  }

  off(type, handler) {
    this._handlers.get(type)?.delete(handler);
  }

  _emit(type, msg) {
    const set = this._handlers.get(type);
    if (!set) return;
    // Cópia: handler pode se remover durante o dispatch
    for (const h of [...set]) {
      try { h(msg); } catch (e) { console.error(`Handler error p/ ${type}:`, e); }
    }
  }
}
