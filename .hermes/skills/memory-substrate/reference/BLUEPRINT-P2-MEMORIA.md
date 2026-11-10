# BLUEPRINT P2 — MEMÓRIA DE CONVERSAS NPC ↔ NPC (Nephy)

> Fase P2 do protocolo §5. Depende de P1 (conversas 2 membros, BLUEPRINT-P1-CONVERSA.md).
> Base auditada: conversation.py, memory_substrate/api_gateway.py (~linha 559),
> retriever /dialogue, EmbeddingEngine all-MiniLM-L6-v2 (384 dims), vector_store.py
> com persist. Regra de ouro: NADA disto pode travar o tick de 10 Hz.

## 1. Objetivo e escopo

Ao encerrar, a conversa vira memória; conversa nova entre o mesmo par → NPCs lembram
e citam a anterior. Memória = resumo estruturado + embedding no Memory Substrate (8767).

**MUDA (novo):** resumo no encerramento (ambos `left`); endpoints `POST /memory/store`
e `POST /memory/recall`; cache de embedding por hash (dia 1 — inegociável); bloco de
memória no prompt LLM junto com o SOUL.

**NÃO MUDA (inalterado):** máquina de estados da conversa (P1); tick 10 Hz (resumo e
store são assíncronos, fora do tick); SOULs em C:/Users/mathe/Hermes_Brain/90-Sistema/Setores/
(só lidos); /dialogue player↔NPC intocado; sem grupos, sem render novo, sem protocolo novo.

## 2. Pipeline e formatos JSON

```
encerramento (ambos left) → RESUMO estruturado → hash(resumo) → cache embedding
  → POST /memory/store (8767) → [conversa nova, mesmo par]
  → POST /memory/recall → top-3 memórias → bloco no prompt + SOUL → LLM
```

### 2.1 Resumo estruturado (gerado no servidor do jogo, no encerramento)

```json
{
  "participants": ["npc_anna", "npc_boris"],
  "room": "room_market",
  "topic": "mercado abriu cedo",
  "facts": ["O mercado abriu mais cedo hoje", "Boris reclamou do preço do trigo"],
  "ended_at": 1758200123.456
}
```

- `topic`: 1 frase curta; `facts`: 1-2 fatos marcantes (limite duro: 2).
- Gerado por LLM assíncrono com fallback: LLM fora → resumo degenerado =
  concatenação das 2 últimas falas (nunca bloqueia o encerramento).

### 2.2 Registro de memória (o que o /memory/store grava no Substrate)

```json
{
  "id": "mem_conv_7f3a_1758200123",
  "text": "Anna e Boris conversaram sobre o mercado abriu cedo. Fatos: O mercado abriu mais cedo hoje; Boris reclamou do preço do trigo.",
  "embedding": [0.021, "...384 dims"],
  "metadata": {
    "participants": ["npc_anna", "npc_boris"],
    "timestamp": 1758200123.456,
    "room": "room_market",
    "topic": "mercado abriu cedo",
    "type": "conversation"
  }
}
```

- `text` é o que é embeddado (via cache por hash, §5) e recuperado; persist =
  mecanismo existente do vector_store.py.

## 3. Endpoints novos em memory_substrate/api_gateway.py

### 3.1 POST /memory/store

```json
// MemoryStoreRequest
{ "text": "string (obrigatório, não vazio)", "participants": ["string"],
  "room": "string", "topic": "string", "timestamp": 1758200123.456 }
// MemoryStoreResponse
{ "id": "mem_conv_7f3a_1758200123", "cached": true, "stored": true }
```

- `cached`: true se o embedding veio do cache por hash (§5). Falha de gravação →
  `stored: false` + `reason` no corpo (texto vazio → 422 Pydantic padrão).

### 3.2 POST /memory/recall

```json
// MemoryRecallRequest
{ "query": "string", "participants": ["npc_anna", "npc_boris"], "top_k": 3 }
// MemoryRecallResponse
{ "memories": [ { "text": "string", "topic": "string", "timestamp": 1758200123.456,
    "participants": ["npc_anna", "npc_boris"], "score": 0.78 } ] }
```

- Recall = retrieve por similaridade com filtro: só retorna memórias em que TODOS
  os participantes consultados participaram. `top_k` default 3, máx 3 (hard cap).

## 4. Como conversation.py chama os endpoints

- **Store (encerramento)**: no último `left`, monta o resumo (§2.1) e dispara
  `POST /memory/store` em worker assíncrono (mesmo pool do gate LLM da P1).
  Fire-and-forget: encerramento NÃO espera resposta; erro → log silencioso.
- **Recall (início)**: par entra em `participating` → `POST /memory/recall`
  (`query` = fala de abertura ou topic da sala) com `timeout=5s`. Respondeu a
  tempo → injeta no prompt da primeira fala; timeout/erro → `memories = []`.
- **Fallback silencioso**: Substrate fora ou resposta inválida → lista vazia,
  conversa segue, zero exceção propagada ao tick. 1 tentativa, sem retry.
- Mesma base URL do /dialogue existente (porta 8767).

## 5. Cache de embedding por hash — onde mora

**Decisão: dentro do EmbeddingEngine do Memory Substrate (não no gateway).**
O EmbeddingEngine é o único dono do modelo; o cache (`sha256(texto_normalizado)`
→ embedding 384, em disco junto ao persist do vector_store.py) protege TODOS os
consumidores (store, /dialogue, recall), não só o caminho novo. O gateway só
consulta `get_embedding(text)` e repassa `cached` na resposta. O hit é checado
ANTES de qualquer inferência; persistente entre restarts.

## 6. Bloco de memória no prompt + SOUL

Na primeira fala da conversa (v1: só a primeira), o prompt recebe nesta ordem:

```
[SOUL do NPC — lido de C:/Users/mathe/Hermes_Brain/90-Sistema/Setores/]
[MEMÓRIAS COM <partner_id>]
1. (2026-09-17, room_market) mercado abriu cedo — O mercado abriu mais cedo; Boris reclamou do preço do trigo.
[/MEMÓRIAS]
[Instrução: Você já conversou com <partner_id> antes. Referencie naturalmente
 uma memória acima se fizer sentido. Não repita fato por fato.]
```

- Máx 3 memórias, cada ≤ 2 linhas; bloco inteiro sai do prompt se `memories = []`.
- SOUL vem sempre primeiro; memórias são contexto, nunca substituem o SOUL.

## 7. Critérios de aceite M1–M6

- **M1 — Persistência**: conversa encerrada → store → restart do jogo E do
  Substrate → recall retorna a memória (persist do vector_store.py provado).
- **M2 — Recall correto**: memórias por score desc; a mais recente/relevante do
  par primeiro; máximo 3 itens.
- **M3 — Zero vazamento**: anna↔boris NUNCA recebem via recall memória de
  carlos↔dora; recall sem match de participants → lista vazia.
- **M4 — Cache por hash**: texto idêntico armazenado 2× → segunda resposta
  `cached=true` e o EmbeddingEngine não roda inferência (hit provado por
  contador em log ou instrumento de teste).
- **M5 — Milestone — NPC cita conversa anterior**: mesma dupla conversa 2×; na
  2ª, a primeira fala do LLM referencia o assunto da 1ª (ex.: "De novo falando
  do mercado?") — verificado por inspeção de transcript.
- **M6 — Robustez**: Substrate derrubado → jogo inicia conversas normalmente,
  recall vira [], tick 10 Hz sem degradação, zero crash; Substrate volta →
  recall funciona sem restart do jogo.

## 8. Plano de commits

1. Cache por hash no EmbeddingEngine (+persist) com teste de hit — ANTES de tudo.
2. Schemas Pydantic + `POST /memory/store` no api_gateway.py (+teste novo).
3. Schemas Pydantic + `POST /memory/recall` com filtro participants (+teste).
4. conversation.py: resumo no encerramento + store assíncrono fire-and-forget.
5. conversation.py: recall no início + bloco de memória no prompt + SOUL.
6. Testes M1–M6 (arquivo novo; os 57 existentes intocados) + transcript do M5.

**Estado**: blueprint P2 pronto. Cache por hash é dia-1. Incertezas: [Morgana
decide na implementação] — formato exato do texto embeddado (§2.2) e limiar
mínimo de score no recall. Escopo: só NPC↔NPC (P1); player↔NPC fica para P3.
