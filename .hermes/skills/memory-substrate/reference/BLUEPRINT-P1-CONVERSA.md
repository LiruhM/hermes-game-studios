# BLUEPRINT P1 — CONVERSA NPC ↔ NPC (Nephy, 2ª tentativa)

> Fase P1 do protocolo §5 (BLUEPRINT_CORE.md). Base técnica: RESEARCH-AI-TOWN.md seções 4-5
> e código real (protocol.py, rooms.py, entities.py, npc_behaviors.py) já auditado na 1ª tentativa.
> Regra de ouro: NADA disto pode travar o tick de 10 Hz.

## 1. Objetivo

Dois NPCs iniciam e sustentam uma conversa entre si, sem intervenção do player,
usando o pathfinding existente e o LLM com fallback local. Escopo mínimo: conversas
de exatamente 2 membros, alternância de falas, despedida automática.

## 2. Escopo — o que muda e o que NÃO muda

**MUDA (novo):**
- Conversa NPC ↔ NPC autônoma (convite, caminhada, falas, despedida).
- Duas mensagens novas no protocolo (seção 3).

**NÃO MUDA (inalterado):**
- Diálogo player ↔ NPC (fluxo existente).
- Chat do player (chat.send / broadcast existente).
- Movimento: usa `move.path`/pathfinding já existente — nenhum código novo de path.
- Render: NPCs em conversa não ganham overlay/sprite novo (v1).

## 3. Mensagens novas do protocolo

### 3.1 `npc.conversation.state`
Estado/delta da conversa. Emitido a cada mudança de estado de membro.

```json
{
  "type": "npc.conversation.state",
  "conversationId": "conv_7f3a",
  "members": [
    { "entityId": "npc_anna",  "status": "participating" },
    { "entityId": "npc_boris", "status": "walkingOver" }
  ]
}
```

`status` ∈ `invited` | `walkingOver` | `participating` | `left`.

Semântica:
- `invited` — B recebeu o convite, ainda não decidiu/começou a andar.
- `walkingOver` — B aceitou e está andando até A (pathfinding em curso).
- `participating` — NPC está no tile de conversa, apto a falar.
- `left` — NPC saiu da conversa (despedida, timeout, ou cancelamento).

### 3.2 `npc.conversation.line`
Uma fala emitida dentro da conversa.

```json
{
  "type": "npc.conversation.line",
  "conversationId": "conv_7f3a",
  "authorId": "npc_anna",
  "text": "Ei Boris, viu o que aconteceu na fazenda ontem?",
  "ts": 1758200000.123
}
```

## 4. Regras fixas (invariáveis)

- **R1 — Cooldown ≥ 10 s** entre falas DE UM MESMO NPC (por NPC, não por conversa).
- **R2 — Alcance 2 tiles**: convite só é enviado se B está a ≤ 2 tiles de distância
  euclidiana; a conversa em si acontece cara a cara (1 tile) após A chegar perto de B.
- **R3 — 1 conversa por NPC**: NPC em `participating` não responde a novos convites
  e não emite convites.
- **R4 — Exatamente 2 membros**: sem grupos. Convite para NPC ocupado → recusado.
- **R5 — Nunca travar o tick**: chamada LLM NUNCA é síncrona no tick; ver gate §6.

## 5. Fluxo de vida da conversa

```
A decide conversar → invite → A path até B → chegou → participating
  → falas alternadas (LLM, gate 1-op-por-NPC, fallback reserva)
  → despedida → ambos emitem members[].status = left
```

Passo a passo (servidor):

1. **Decisão** — No tick comportamental (não a cada frame), NPC A avalia gatilhos:
   tédio/tempo sem interação, proximidade de B (≤ 2 tiles, R2), ambos idle,
   nenhum dos dois em conversa (R3/R4). Se ok, cria `conversationId` e emite
   `npc.conversation.state` com B em `invited` e A em `invited`/`walkingOver`.
2. **Convite** — B "aceita" se está idle e sem conversa. Ao aceitar: A entra em
   `walkingOver` e emite `move.path` destino = tile adjacente a B (pathfinding
   existente — zero código novo de path).
3. **Caminhada** — Reutiliza move.request/move.path já existentes. Se o path falhar
   ou demorar > 30 s → cancela conversa (ambos → `left`), libera NPCs.
4. **Chegada** — Quando A fica a ≤ 1 tile de B (e parado): ambos → `participating`,
   novo `npc.conversation.state` emitido. Neste ponto o estado persiste no
   servidor (mapa `conversationId → {members, turn, lastSpoke}`).
5. **Falas alternadas** — Turno inicial: quem convidou (A). Servidor alterna A→B→A.
   Cada fala passa pelo gate do §6. Texto sai via `npc.conversation.line` para
   todos os clientes visíveis (mesmo mapa/sala).
6. **Despedida** — Três gatilhos, qualquer um encerra: (a) N trocas completas
   (default 4-6 falas), (b) um dos NPCs recebe move.request externo/urgência
   comportamental, (c) cooldown global de conversa (evita loop A↔B infinito).
   Encerramento: última fala de despedida (fallback ok) + `npc.conversation.state`
   com ambos `left`. NPCs ganham cooldown ~60 s antes de nova conversa entre si.

## 6. Gate LLM: 1 operação por NPC, nunca no tick

- Fila **por NPC**: cada NPC tem no máximo 1 operação LLM pendente (fala da
  conversa OU tarefa comportamental existente — nunca ambas). Nova solicitação
  enquanto uma pende → vai para a fila, não para o tick.
- A geração é **assíncrona** (worker/thread pool fora do loop de 10 Hz); o tick
  só consome resultados prontos. Tick NUNCA espera LLM.
- **Fallback de reserva**: se LLM indisponível/timeout (> 5 s)/erro → o worker
  escolhe uma fala de reserva de pool local (ex.: "Ouvi dizer que o mercado
  abriu cedo hoje."), marca `fromFallback: true` no log interno, emite a fala
  normalmente. Conversa continua; nunca trava, nunca silencia o turno.

## 7. Interações com sistemas existentes (o que fica inalterado na prática)

| Sistema | Comportamento com conversa ativa |
|---|---|
| Diálogo player ↔ NPC | Intocado. Se player inicia diálogo com NPC em conversa, NPC recusa com "estou conversando" (v1) — fluxo original não é tocado. |
| Chat do player | Intocado. `npc.conversation.line` é canal separado; clientes renderizam como fala ambiente, não no chat do player. |
| Movimento | 100% reutilizado: `move.path` para `walkingOver` (§5.2). NPC em `participating` responde a `move.request` externo — isso ENCERRA a conversa (despedida curta + `left`), não bloqueia o pedido. |
| Render | Nenhuma mudança obrigatória. Cliente pode mostrar balão de fala se já tem esse recurso; servidor não exige. |
| Tick 10 Hz | Só ler filas prontas; zero espera de I/O. Conversa vive no tick comportamental (~1 Hz) + callbacks assíncronos. |

## 8. Critérios de aceite D1–D6

- **D1 — Conversa autônoma**: dois NPCs idle a ≤ 2 tiles iniciam conversa,
  caminham, trocam ≥ 4 falas e encerram, SEM nenhuma intervenção do player
  (server rodando só com bots).
- **D2 — Sem regressão**: os 57 testes existentes re-executam verdes, sem
  alteração de nenhum teste existente (novos testes entram em arquivo novo).
- **D3 — Teste de corrida (race)**: carga simultânea de (i) uma conversa NPC↔NPC
  ativa, (ii) input do player (move.request + chat), (iii) NPCs idle com tick
  comportamental — 60 s de execução sem deadlock, sem tick > 100 ms.
- **D4 — Fallback LLM**: com o LLM fora (endpoint derrubado), a conversa
  completa inteiramente com falas de reserva; nenhum erro propagado ao cliente.
- **D5 — Cooldown respeitado**: teste de tempo mede timestamps de
  `npc.conversation.line` por autor: intervalo entre falas do MESMO NPC
  ≥ 10 s (R1), tolerância 0 ms abaixo do limite.
- **D6 — NPC móvel durante conversa**: `move.request` para NPC em
  `participating` é aceito e executado; conversa encerra com despedida +
  `left`; NPC volta a aceitar convites após cooldown (~60 s).

## 9. Plano de implementação (ordem de commits)

1. Mensagens no protocolo (schema + validação) — arquivo de teste novo.
2. Estado da conversa no servidor (mapa, máquina de estados dos membros).
3. Decisão + convite + caminhada (reusa move.path).
4. Falas alternadas + gate LLM por NPC + pool de fallback.
5. Despedida + cooldown pós-conversa.
6. Testes D1–D6 (novos, sem tocar nos 57 existentes).

**Estado**: P1 blueprint pronto para implementação. Escopo travado: 2 membros,
sem grupos, sem render novo. P2 (grupos, memória de conversa) fica fora.
