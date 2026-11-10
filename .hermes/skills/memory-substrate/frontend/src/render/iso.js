// iso.js — Projeção isométrica pura (tile 32×16), BLUEPRINT §4/§6.2.
// Nenhuma dependência; funções puras compartilhadas por todo o pipeline.

// Dimensões do tile isométrico (§4: "Isometric: tile 32×16")
export const TILE_W = 32;
export const TILE_H = 16;

/**
 * Iso — utilitário de projeção isométrica.
 * Convenção de eixos: col cresce para sudeste (tela: +x), row cresce
 * para sudoeste (tela: +y). screenY depende de col E row — é a chave do
 * sort unificado da §4.2 (ordenar por tile.y puro é causa nº 2 das
 * sobreposições).
 */
export class Iso {
  constructor(tileW = TILE_W, tileH = TILE_H) {
    this.TILE_W = tileW;
    this.TILE_H = tileH;
  }

  /**
   * Converte coordenadas de tile (contínuas) para coordenadas de tela
   * (espaço de mundo, ANTES da transformação da câmera).
   * O centro do tile (col,row) é tileToScreen(col+0.5, row+0.5) — §4.2.
   */
  tileToScreen(tx, ty) {
    return {
      x: (tx - ty) * (this.TILE_W / 2),
      y: (tx + ty) * (this.TILE_H / 2)
    };
  }

  /**
   * Inversa exata de tileToScreen (coordenadas contínuas).
   * Usada para culling: cantos do viewport → range de tiles visíveis.
   */
  screenToTileFloat(sx, sy) {
    const a = sx / this.TILE_W;      // (tx - ty) / 2
    const b = sy / this.TILE_H;      // (tx + ty) / 2
    return { x: a + b, y: b - a };
  }

  /**
   * Inversa arredondada — clique do mouse → tile lógico.
   * (O cursor em si é desenhado por B, mas a decisão de validade é do C,
   * §7.3 — aqui é só matemática.)
   */
  screenToTile(sx, sy) {
    const f = this.screenToTileFloat(sx, sy);
    return { x: Math.floor(f.x), y: Math.floor(f.y) };
  }

  /**
   * Chave de sort padrão de um drawable (§4.2):
   * screenY do CENTRO do tile (x+0.5, y+0.5).
   * Toda entidade / móvel-per-tile / porta usa exatamente esta chave.
   */
  sortKey(tileX, tileY) {
    return this.tileToScreen(tileX + 0.5, tileY + 0.5).y;
  }

  /** Centro do tile em coordenadas de tela (espaço de mundo). */
  tileCenter(tx, ty) {
    return this.tileToScreen(tx + 0.5, ty + 0.5);
  }
}

// Instância única compartilhada (tile 32×16 é fixo no projeto)
export const iso = new Iso();
