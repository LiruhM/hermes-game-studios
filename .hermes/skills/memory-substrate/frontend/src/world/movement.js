// movement.js — Interpolação de movimento do cliente (§3.3, §3.4)
// O servidor é autoritativo: envia move.path UMA vez; o cliente anima a
// travessia tile a tile por delta-time na MESMA velocidade (moveTimeMs/tile).
// entity.move por tile = ÂNCORA de correção: divergência > ½ tile → snap suave.
// NUNCA calcula path, NUNCA decide caminhabilidade (§3.4).

const DEFAULT_MOVE_TIME_MS = 350;
const ANCHOR_MAX_DIVERGENCE = 0.5;  // tiles — tolerância antes do snap (§3.3)
const SNAP_LERP = 0.15;             // fator de snap suave por frame (C5: < 300ms)

// Caminho ativo de uma entidade: { path, segIndex, startedAt, moveTimeMs }
const activePaths = new Map();      // Map<entityId, walkState>

// ===== move.path (§5.2): { entityId, path, startedAt, moveTimeMs } =====
export function onMovePath(worldState, msg) {
  const { entityId, path, startedAt, moveTimeMs } = msg;
  if (!entityId || !Array.isArray(path) || path.length < 2) return;

  const ent = worldState.getEntity(entityId);
  if (!ent) return;

  // moveTimeMs pode vir na msg; senão usa o do welcome
  const perTileMs = (typeof moveTimeMs === 'number' && moveTimeMs > 0)
    ? moveTimeMs : worldState.moveTimeMs;

  // Segundo clique substitui o path atual (C6) — mesmo Map, mesma chave
  activePaths.set(entityId, {
    path,
    segIndex: 0,                 // segmento atual: path[0] → path[1]
    startedAt,
    moveTimeMs: perTileMs,
  });

  // Se a entidade ainda não está no início do path (âncora inicial),
  // alinha a posição lógica
  const [c0, r0] = path[0];
  ent.col = c0; ent.row = r0;
  ent.moving = true;
  _updateDir(ent, path[0], path[1]);
}

// Normaliza direção: protocolo §5 usa n/s/e/w; servidor legado já enviou
// "down"/"up"/"left"/"right" em entity.move. Converte p/ não quebrar o render.
const _DIR_ALIAS = { down: 's', up: 'n', left: 'w', right: 'e' };
function _normDir(dir) {
  return _DIR_ALIAS[dir] ?? dir;
}

// ===== entity.move (§5.2): âncora por tile =====
// { entityId, col, row, moving, dir, serverTime }
export function onEntityMove(worldState, msg) {
  const { entityId, col, row, moving } = msg;
  const ent = worldState.getEntity(entityId);
  if (!ent) return;

  ent.col = col;
  ent.row = row;
  ent.dir = _normDir(msg.dir) ?? ent.dir;
  ent.moving = !!moving;

  if (!moving) {
    // Chegou ao destino (§3.3): limpa path ativo e fixa posição
    activePaths.delete(entityId);
    ent.x = col; ent.y = row;
    return;
  }

  // Âncora durante caminhada: verifica divergência da interpolação local
  const walk = activePaths.get(entityId);
  const dist = Math.hypot(ent.x - col, ent.y - row);
  if (dist > ANCHOR_MAX_DIVERGENCE) {
    // Divergiu > ½ tile: snap suave — reposiciona o path a partir da âncora (C5)
    if (walk) {
      const idx = _findNearestPathIndex(walk.path, col, row);
      walk.path = walk.path.slice(idx);
      walk.segIndex = 0;
      // Reinicia o relógio do segmento a partir da âncora (serverTime da própria msg)
      walk.startedAt = (typeof msg.serverTime === 'number')
        ? msg.serverTime : Date.now();
    }
    // Snap suave: a posição render converge p/ âncora no próximo update
    ent.x = ent.x + (col - ent.x) * SNAP_LERP;
    ent.y = ent.y + (row - ent.y) * SNAP_LERP;
  }
  // Divergência ≤ ½ tile: interpolação local continua — nada a fazer
}

// ===== Avanço por frame (delta-time) — chamado no gameLoop =====
export function update(worldState, nowServerMs) {
  for (const [entityId, walk] of activePaths) {
    const ent = worldState.getEntity(entityId);
    if (!ent) { activePaths.delete(entityId); continue; }

    const elapsed = nowServerMs - walk.startedAt;
    if (elapsed < 0) continue; // clock ainda sincronizando

    // Quantos segmentos completos + fração do atual (velocidade = 1 tile/moveTimeMs)
    const segF = Math.max(0, elapsed) / walk.moveTimeMs;
    const segInt = Math.floor(segF);
    const frac = segF - segInt;

    const seg = Math.min(walk.segIndex + segInt, walk.path.length - 1);
    if (seg >= walk.path.length - 1) {
      // Fim do path: fixa no último tile (âncora final moving:false chega em seguida)
      const [c, r] = walk.path[walk.path.length - 1];
      ent.x = c; ent.y = r;
      ent.moving = true;
      activePaths.delete(entityId);
      continue;
    }

    const [c0, r0] = walk.path[seg];
    const [c1, r1] = walk.path[seg + 1];
    ent.x = c0 + (c1 - c0) * frac;
    ent.y = r0 + (r1 - r0) * frac;
    _updateDir(ent, [c0, r0], [c1, r1]);

    // Consome segmentos completos: avança a base do relógio p/ o próximo seg
    if (segInt > 0) {
      walk.segIndex = seg;
      walk.startedAt += segInt * walk.moveTimeMs;
    }
  }
}

// ===== utilidades internas =====

function _updateDir(ent, from, to) {
  if (!from || !to) return;
  const dc = to[0] - from[0];
  const dr = to[1] - from[1];
  if (dc > 0) ent.dir = 'e';
  else if (dc < 0) ent.dir = 'w';
  else if (dr > 0) ent.dir = 's';
  else if (dr < 0) ent.dir = 'n';
}

function _findNearestPathIndex(path, col, row) {
  let best = 0, bestD = Infinity;
  for (let i = 0; i < path.length; i++) {
    const d = Math.hypot(path[i][0] - col, path[i][1] - row);
    if (d < bestD) { bestD = d; best = i; }
  }
  return best;
}

// Estado p/ inspeção nos testes (C6: um path ativo por entidade)
export function getActivePath(entityId) {
  return activePaths.get(entityId) ?? null;
}

// Remove o path ativo de UMA entidade (usado no despawn)
export function clearActivePath(entityId) {
  activePaths.delete(entityId);
}

export function clearActivePaths() {
  activePaths.clear();
}
