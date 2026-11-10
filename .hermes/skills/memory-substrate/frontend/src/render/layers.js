// layers.js — Constantes de camada explícitas, BLUEPRINT §4 (exato).
//
// Princípio 1.2: nada de painter's algorithm implícito com uma única
// lista por Y. Todo drawable tem uma camada EXPLÍCITA; DENTRO da
// camada os itens são ordenados por screenY.
//
// Critério B5: `grep -c "LAYER_" layers.js` deve achar as 8 constantes
// exatamente com os valores da §4: 0,1,2,3,4,5,6,10.

// Pisos, tapetes e overlays de área. Tapete é VISUAL, nunca colide (§2.3).
export const LAYER_FLOOR = 0;

// Paredes norte/oeste — desenhadas ANTES das entidades (§4.3).
export const LAYER_WALLS_BEHIND = 1;

// Móveis de altura visual 1 (cadeiras, plantas, mesas baixas) — §4.4.
export const LAYER_FURNITURE_LOW = 2;

// Móveis de altura visual 2+ (estantes, armários) — §4.4.
// Altura afeta apenas camada visual; NUNCA colisão (Princípio 1.3).
export const LAYER_FURNITURE_HIGH = 3;

// Jogadores e NPCs — sort por screenY dentro da lista unificada (§4.6).
export const LAYER_ENTITIES = 4;

// Paredes sul/leste — desenhadas DEPOIS das entidades (§4.3).
export const LAYER_WALLS_FRONT = 5;

// Portas — participam da lista unificada com sort por screenY (§4.5).
export const LAYER_DOORS = 6;

// Cursores, tooltips, headicons — sempre por último (§4.1 fase 5).
export const LAYER_UI = 10;

// Mapa nome→valor, usado pelo smoke test para conferir §4 (critério B5).
// (nome sem prefixo LAYER_ para não poluir a contagem do grep do B5)
export const ALL_LAYERS = {
  LAYER_FLOOR,
  LAYER_WALLS_BEHIND,
  LAYER_FURNITURE_LOW,
  LAYER_FURNITURE_HIGH,
  LAYER_ENTITIES,
  LAYER_WALLS_FRONT,
  LAYER_DOORS,
  LAYER_UI
};

/**
 * Validação das constantes contra a §4 (critério B5).
 * Retorna true se os 8 valores estão exatamente como no BLUEPRINT.
 */
export function validateLayers() {
  const expected = {
    LAYER_FLOOR: 0,
    LAYER_WALLS_BEHIND: 1,
    LAYER_FURNITURE_LOW: 2,
    LAYER_FURNITURE_HIGH: 3,
    LAYER_ENTITIES: 4,
    LAYER_WALLS_FRONT: 5,
    LAYER_DOORS: 6,
    LAYER_UI: 10
  };
  const keys = Object.keys(expected);
  for (const k of keys) {
    if (ALL_LAYERS[k] !== expected[k]) return false;
  }
  return Object.keys(ALL_LAYERS).length === 8;
}
