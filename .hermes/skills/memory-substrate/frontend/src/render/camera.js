// camera.js — Câmera com culling por viewport, BLUEPRINT §4.1 fase 1.
//
// A câmera é responsável por: pan/zoom, e por calcular o RANGE DE
// TILES VISÍVEIS (culling) — apenas tiles/móveis/entidades dentro do
// range entram na lista de drawables (§4.7: ≤ ~600 drawables em 40×40).

import { iso } from './iso.js';

export class Camera {
  constructor(viewportW = 800, viewportH = 600) {
    this.viewportW = viewportW;
    this.viewportH = viewportH;
    // Posição da câmera no espaço de mundo (canto sup. esquerdo do viewport)
    this.x = 0;
    this.y = 0;
    this.targetX = 0;
    this.targetY = 0;
    this.zoom = 1;
    this.minZoom = 0.5;
    this.maxZoom = 2.0;
    this.lerpFactor = 0.12;
    this.followTarget = null; // { getScreenPos(): {x,y} } — injetado pelo main
  }

  resize(w, h) {
    this.viewportW = w;
    this.viewportH = h;
  }

  /** Centraliza a câmera num ponto do espaço de mundo (sem lerp). */
  centerOn(wx, wy) {
    this.x = wx - this.viewportW / (2 * this.zoom);
    this.y = wy - this.viewportH / (2 * this.zoom);
    this.targetX = this.x;
    this.targetY = this.y;
  }

  /** Define alvo de seguimento suave (posição de tela de uma entidade). */
  follow(screenPosProvider) {
    this.followTarget = screenPosProvider;
  }

  /** Avanço por frame — lerp em direção ao alvo. */
  update(dt) {
    if (this.followTarget && typeof this.followTarget === 'function') {
      const p = this.followTarget();
      if (p) {
        this.targetX = p.x - this.viewportW / (2 * this.zoom);
        this.targetY = p.y - this.viewportH / (2 * this.zoom);
      }
    }
    // dt em segundos; fator independente de framerate (clamp p/ não explodir)
    const t = Math.min(1, this.lerpFactor * (dt * 60));
    this.x += (this.targetX - this.x) * t;
    this.y += (this.targetY - this.y) * t;
    this.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.zoom));
  }

  /** Coordenada de tela (px do canvas) → espaço de mundo. */
  screenToWorld(sx, sy) {
    return { x: sx / this.zoom + this.x, y: sy / this.zoom + this.y };
  }

  /** Espaço de mundo → coordenada de tela (px do canvas). */
  worldToScreen(wx, wy) {
    return { x: (wx - this.x) * this.zoom, y: (wy - this.y) * this.zoom };
  }

  /**
   * CULLING (§4.1 fase 1): range de tiles visíveis no viewport atual.
   * Projeta os 4 cantos da tela de volta ao espaço de tile e toma o
   * bounding box, com margem de segurança (muros altos entram por cima:
   * margem vertical extra proporcional à altura máxima de parede).
   * Retorna {minCol, maxCol, minRow, maxRow} — inclusivo.
   */
  visibleTileRange(margin = 2) {
    const halfW = this.viewportW / this.zoom;
    const halfH = this.viewportH / this.zoom;
    // Cantos do viewport no espaço de mundo
    const corners = [
      [this.x, this.y],
      [this.x + halfW, this.y],
      [this.x, this.y + halfH],
      [this.x + halfW, this.y + halfH]
    ];
    let minTx = Infinity, maxTx = -Infinity;
    let minTy = Infinity, maxTy = -Infinity;
    for (const [wx, wy] of corners) {
      const t = iso.screenToTileFloat(wx, wy);
      if (t.x < minTx) minTx = t.x;
      if (t.x > maxTx) maxTx = t.x;
      if (t.y < minTy) minTy = t.y;
      if (t.y > maxTy) maxTy = t.y;
    }
    // Margem: 2 tiles laterais + 5 tiles verticais (paredes de 128px
    // descem sobre tiles "acima" do viewport — sem isso a parede some
    // quando o tile dela ainda não está visível).
    return {
      minCol: Math.floor(minTx) - margin,
      maxCol: Math.ceil(maxTx) + margin,
      minRow: Math.floor(minTy) - margin - 4,
      maxRow: Math.ceil(maxTy) + margin
    };
  }

  /** Um tile (inteiro) está dentro do range visível? */
  isTileVisible(range, col, row) {
    return col >= range.minCol && col <= range.maxCol &&
           row >= range.minRow && row <= range.maxRow;
  }
}
