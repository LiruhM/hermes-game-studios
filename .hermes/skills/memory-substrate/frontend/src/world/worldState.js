// worldState.js — Estado local do mundo (§2, §7.3)
// Cópia de leitura do estado autoritativo do servidor: entidades, tileMap,
// blockedTiles, móveis, portas, carpetTiles. NUNCA calcula path (§3.4).
// Expõe getDrawables() (API do renderer B) e isTileLikelyWalkable() (só cursor).

import { isFloorTile } from '../net/messageTypes.js';

export class WorldState {
  constructor() {
    // Sala atual (a§5.2 welcome) — tileMap imutável pós-build, cópia de leitura
    this.room = null;              // { id, name, width, height, tileMap, doors, furniture, carpetTiles }
    this.blockedTiles = new Set(); // Set<"col,row"> — cópia de leitura (§2.2)

    // Entidades autoritativas: Map<id, entidade>
    this.entities = new Map();

    // Config de movimento do servidor (welcome.moveTimeMs, §3.3)
    this.moveTimeMs = 350;
    this.selfEntityId = null;

    // Última atualização de estado (para debug/telemetria)
    this.lastSyncAt = 0;
  }

  // ===== Carregamento (welcome / world.sync — §5.2) =====

  // welcome: { entityId, name, room: {...}, entities: [...], moveTimeMs, serverTime }
  applyWelcome(msg) {
    // Envelope §5/legado compat: servidor real manda {type, payload, ...};
    // mock manda flat. Normaliza uma vez aqui — handlers downstream só veem flat.
    const p = (msg.payload && typeof msg.payload === 'object' && (msg.entityId === undefined))
      ? msg.payload : msg;
    this.selfEntityId = p.entityId ?? this.selfEntityId;
    if (typeof p.moveTimeMs === 'number' && p.moveTimeMs > 0) {
      this.moveTimeMs = p.moveTimeMs;
    }
    if (p.room) this._applyRoom(p.room);
    if (Array.isArray(p.entities)) this._replaceEntities(p.entities);
    this.lastSyncAt = Date.now();
  }

  // world.sync: { entities, serverTime } — snapshot completo na (re)conexão (C2)
  applyWorldSync(msg) {
    const p = (msg.payload && typeof msg.payload === 'object' && (msg.entities === undefined))
      ? msg.payload : msg;
    if (Array.isArray(p.entities)) this._replaceEntities(p.entities);
    this.lastSyncAt = Date.now();
  }

  _applyRoom(roomData) {
    this.room = {
      id: roomData.id ?? 'main_office',
      name: roomData.name ?? '',
      width: roomData.width ?? 0,
      height: roomData.height ?? 0,
      is_meeting: roomData.is_meeting ?? false,   // hud.renderCurrentRoom lê
      capacity: roomData.capacity ?? 0,
      tileMap: roomData.tileMap || [],       // int[][] — TileType, §2.1
      doors: roomData.doors || [],
      furniture: roomData.furniture || [],
      carpetTiles: roomData.carpetTiles || [],
    };
    // blockedTiles chega como array de "col,row" (§2.2) — vira Set local
    this.blockedTiles = new Set(roomData.blockedTiles || []);
  }

  _replaceEntities(list) {
    // Snapshot substitui todo o estado — sem órfãos após reconnect (C2)
    this.entities.clear();
    for (const e of list) this.upsertEntity(e);
  }

  // ===== Entidades =====

  // entity.spawn / item de lista: { id, type, name, col, row, characterKey, meta }
  upsertEntity(e) {
    if (!e || typeof e.id !== 'string') return null;
    const cur = this.entities.get(e.id);
    const ent = {
      id: e.id,
      type: e.type ?? (cur?.type ?? 'player'),
      name: e.name ?? (cur?.name ?? e.meta?.name ?? ''),
      characterKey: e.characterKey ?? (cur?.characterKey ?? e.sprite ?? 'player_default'),
      // Posição render — sobrescrita por movement.js a cada frame
      x: (cur && cur.x !== undefined && e.col === undefined) ? cur.x : (e.col ?? cur?.col ?? 0),
      y: (cur && cur.y !== undefined && e.row === undefined) ? cur.y : (e.row ?? cur?.row ?? 0),
      // Posição autoritativa (tile) — âncoras entity.move
      col: e.col ?? cur?.col,
      row: e.row ?? cur?.row,
      dir: e.dir ?? (cur?.dir ?? 's'),
      moving: e.moving ?? (cur?.moving ?? false),
      meta: e.meta ?? (cur?.meta ?? {}),
    };
    this.entities.set(e.id, ent);
    return ent;
  }

  removeEntity(entityId) {
    this.entities.delete(entityId);
  }

  getEntity(id) { return this.entities.get(id); }

  // Jogador local (para move.request — §3.2)
  getSelfEntity() {
    if (this.selfEntityId) return this.entities.get(this.selfEntityId);
    return null;
  }

  // ===== Deltas de estado (world.state.delta — §5.2) =====

  // changes: [{ op: "add"|"remove"|"update", kind: "blockedTile", col, row }]
  applyDelta(changes) {
    for (const ch of (changes || [])) {
      if (ch?.kind !== 'blockedTile') continue; // kinds futuros: ignora (rollout incremental)
      const key = `${ch.col},${ch.row}`;
      if (ch.op === 'add') this.blockedTiles.add(key);
      else if (ch.op === 'remove') this.blockedTiles.delete(key);
      // "update" em blockedTile: no-op (mesma chave)
    }
  }

  // ===== API de leitura p/ RENDERER B (§7.2 — congelada na integração) =====

  // TODOS os drawables do mundo: entidades, móveis, portas, carpetTiles.
  // B nunca abre WebSocket — só chama isto por frame.
  getDrawables() {
    const out = [];
    const room = this.room;

    if (room) {
      for (const carpet of room.carpetTiles) {
        out.push({ kind: 'carpet', col: carpet.col ?? carpet[0], row: carpet.row ?? carpet[1] });
      }
      for (const furn of room.furniture) {
        out.push({ kind: 'furniture', ...furn });
      }
      for (const door of room.doors) {
        out.push({ kind: 'door', ...door });
      }
    }

    for (const ent of this.entities.values()) {
      out.push({
        kind: 'entity',
        id: ent.id,
        type: ent.type,
        x: ent.x,           // posição contínua (interpolada por movement.js)
        y: ent.y,
        col: ent.col,
        row: ent.row,
        dir: ent.dir,
        moving: ent.moving,
        characterKey: ent.characterKey,
        name: ent.name,
        meta: ent.meta,
      });
    }
    return out;
  }

  // getDrawablesData — visão estruturada p/ Renderer.renderScene (§7.2):
  // {room, entities, furniture, doors, carpetTiles}. Entidades usam a
  // posição contínua interpolada (x/y) — o renderer converte p/ screenY.
  getDrawablesData() {
    const room = this.room || { id: '', name: '', width: 0, height: 0, tileMap: [], doors: [], furniture: [], carpetTiles: [] };
    const entities = [];
    for (const ent of this.entities.values()) {
      entities.push({
        id: ent.id,
        type: ent.type,
        x: ent.x,
        y: ent.y,
        col: ent.col,
        row: ent.row,
        dir: ent.dir,
        moving: ent.moving,
        characterKey: ent.characterKey,
        name: ent.name,
        meta: ent.meta,
      });
    }
    return {
      room,
      entities,
      furniture: room.furniture || [],
      doors: room.doors || [],
      carpetTiles: room.carpetTiles || [],
    };
  }

  // ===== Cursor de destino (§3.4 — feedback visual, NUNCA decisão) =====

  // isTileLikelyWalkable: "provavelmente caminhável" p/ cursor válido/inválido.
  // NÃO é um check de decisão — a autoridade é o servidor (§1.1).
  isTileLikelyWalkable(col, row) {
    const room = this.room;
    if (!room || !room.tileMap || !room.tileMap[row]) return false;
    if (col < 0 || col >= room.width || row < 0 || row >= room.height) return false;
    if (!isFloorTile(room.tileMap[row][col])) return false;       // WALL/VOID → inválido
    if (this.blockedTiles.has(`${col},${row}`)) return false;     // móvel/NPC parado
    return true;
  }
}
