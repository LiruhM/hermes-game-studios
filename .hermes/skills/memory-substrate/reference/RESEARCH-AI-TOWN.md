# RESEARCH — AI Town (a16z-infra) × Hermes-Corp

> **Autora:** Nephy (Setor Arquitetura). **Data:** 17/09/2026.
> **Fontes primárias:** artigo do CEO (prompts.brightcoding.dev), README.md e ARCHITECTURE.md oficiais do repo a16z-infra/ai-town (raw.githubusercontent.com), LICENSE do repo, páginas de licença dos assets no OpenGameArt. **Fonte secundária:** Grokipedia (só para confirmação, não usada como fato).
> **Objetivo:** estudo profundo do AI Town, verificação de licenças de assets/código, cruzamento mecanismo a mecanismo com o núcleo Hermes-Corp reconstruído (BLUEPRINT_CORE.md), e recomendações priorizadas respeitando hardware fraco (Ryzen 5700U, 12GB), servidor autoritativo já implementado e souls dos chefes já escritas (90-Sistema/Setores/).

---

## 1. O QUE É O AI TOWN

### 1.1 Definição

AI Town é um **starter kit open source, licenciado MIT, deployável** para construir uma versão própria de uma "vila virtual onde personagens de IA vivem, conversam e socializam". Criado pelo time de infraestrutura da **a16z** (a16z-infra), é inspirado diretamente no paper *Generative Agents: Interactive Simulacra of Human Behavior* (arXiv 2304.03442, Stanford/Google — o experimento de Smallville com 25 agentes ChatGPT que organizaram uma festa do Valentine's Day sozinhos).

O objetivo declarado no README: fornecer uma plataforma com base sólida "para ser estendida", e trazer esse tipo de simulação (que historicamente vivia em Python) para **JS/TS**, abrindo a porta para desenvolvedores web.

### 1.2 O que o artigo do CEO diz (e o que a fonte primária confirma)

O artigo (prompts.brightcoding.dev, 18 min) é um deep-dive de divulgação — preciso nos fatos principais, checados abaixo contra o repo oficial:

| Afirmação do artigo | Verificado na fonte primária? |
|---|---|
| MIT-licensed, deployable starter kit | ✅ LICENSE do repo: "MIT License, Copyright (c) 2023 a16z-infra" |
| Backend: Convex (engine + DB + vector search) | ✅ README: "Game engine, database, and vector search: Convex" |
| Default: Llama3 local via Ollama; embeddings mxbai-embed-large | ✅ README idem |
| Render: PixiJS (pixi-react) | ✅ README: interações/música/render no `<Game/>` via PixiJS |
| Auth opcional: Clerk | ✅ README |
| Música: Replicate/MusicGen; pixel art: Replicate/Fal.ai | ✅ README ("Other credits") |
| Deploy: Convex cloud, Docker Compose self-host, Fly.io, fork Pinokio | ✅ README (4 caminhos) |
| ~10.4k stars, 1.2k forks | ✅ GitTrend (set/2026) |

O artigo adiciona posicionamento de marketing ("production-ready", "revolutionary") que deve ser lido com cautela — o próprio ARCHITECTURE.md do projeto lista limitações sérias (§2.5 abaixo).

### 1.3 Open source vs serviço

- **Código 100% open source (MIT)** — sem pegadinha de licença dual.
- **Convex é o ponto de atrito:** o "game engine" roda DENTRO do Convex (plataforma proprietária da Convex Inc.). Há três modos: (a) conta cloud Convex (freemium), (b) **self-host via Docker oficial** (backend em localhost:3210, dashboard 6791) e (c) comunidade Pinokio. O modo Docker é o que interessa para quem quer independência — funciona sem conta Convex.
- **Serviços de ML são todos opcionais:** Ollama (local, grátis), OpenAI/Together (pago), Replicate/Fal (geração de assets, opcional), Clerk (auth, opcional). O núcleo da simulação não depende de nenhum deles além de UM LLM qualquer.

### 1.4 Como os agentes funcionam (o coração do projeto)

Do ARCHITECTURE.md oficial, os agentes combinam **sistemas de regras simples + LLM**:

1. **Loop do agente (`Agent.tick`):** roda dentro do game loop; pode ler/modificar estado do jogo direto (ex.: esperar estar perto de outro player para começar a conversar).
2. **Operações assíncronas (`startOperation`):** tarefas longas (chamar LLM, ler tabelas externas) são agendadas como funções Convex separadas — o agente nunca fica bloqueado esperando a resposta.
3. **Uma operação por vez:** cada agente tem um único `inProgressOperation`; ao terminar, deleta-o antes de decidir o próximo passo. Garante determinismo simples.
4. **Conversas (`convex/agent/conversations.ts`):** prompt engineering injeta personalidade + memórias. Estados: `invited` → `walkingOver` → `participating`; funções start/continue/leave (sair educadamente é tratado explicitamente).
5. **Memória (`convex/agent/memory.ts`):** após cada conversa, o LLM **resume** o histórico; o resumo ganha um **embedding** salvo no vector DB do Convex. Ao iniciar conversa com alguém, o sistema embedda *"What you think about Danny?"*, busca as **3 memórias mais similares** e injeta os resumos no prompt. Há **cache de embeddings por hash de texto** para não recomputar.
6. **Agenda/decisão:** no AI Town a "agenda" é mais fraca que no paper original — o agente escolhe o que fazer a cada tick (regras + LLM), não há o cronograma diário completo de Smallville. Movimento: agente submete `moveTo` como qualquer player humano.

**Insight-chave:** agentes e humanos usam **exatamente os mesmos inputs** (`moveTo`, `startConversation`, …) — desacoplamento explícito entre comportamento do agente e engine. É a mesma filosofia do nosso protocolo §5 (NPC usa `move.request` como qualquer entidade).

---

## 2. ARQUITETURA E STACK

### 2.1 Camadas (ARCHITECTURE.md oficial)

```
convex/aiTown   → lógica de jogo server-side (world, players, conversations, inputs)
convex/engine   → game engine genérico (tick, steps, inputs, load/save de estado)
convex/agent    → agentes: loop assíncrono, memória, conversas (LLM)
src/            → UI cliente: pixi-react renderizando o estado do jogo
data/           → characters.ts (nomes, descrições, spritesheets) + gentle.js (mapa)
```

- **Modelo de dados:** Worlds → Players (nome, descrição, posição, pathfinding) → Conversations → Memberships (`invited`/`walkingOver`/`participating`; 1 conversa por player, exatamente 2 membros).
- **Inputs:** tudo passa por uma tabela `inputs` processada pela engine (`join`, `leave`, `moveTo`, `startConversation`, `acceptInvite`, `rejectInvite`, `leaveConversation`, `startTyping`, `finishSendingMessage`, inputs de agente). Validação declarativa por Convex validator — análogo ao nosso `HANDLERS` do protocol.py com checagem de invariantes (ex.: `moveTo` nega se o player está em conversa).
- **Tabelas separadas de chat:** mensagens NÃO ficam no estado da engine (atualizadas demais, prejudicam o engine) — ficam em tabelas Convex normais. Lição direta para nós: chat/diálogo não precisa poluir o snapshot de mundo.

### 2.2 Engine: ticks e steps (o design mais interessante)

- **tick = 60/s** (movimento suave), mas o Convex não roda 60 mutações/s — a engine **batcha muitos ticks num "step" de 1s**: carrega o estado em memória → processa inputs + ticks → grava de volta.
- **Single-threaded por mundo:** nunca há dois steps simultâneos; controle de corrida via **número de geração monotônico** (runs agendadas carregam a geração esperada; cancelar = bump da geração). É a solução elegante deles para o problema "input chega exatamente quando o timeout de idle expira" — tema que teremos no nosso tick 10 Hz quando entrarem operações async de NPC (LLM).
- **HistoricalObject:** posição/orientação/velocidade por player são objetos "históricos"; o cliente recebe um buffer de história e **replaya o tempo para frente** para movimento fluido (`useHistoricalValue`/`useHistoricalTime`). Equivalente conceitual ao nosso `move.path` + interpolação delta-time, mas deles o buffer guarda diffs.

### 2.3 Limitações declaradas (ARCHITECTURE.md — importante para não copiar cegamente)

- Estado de jogo deve caber em **alguns dezenas de KB** (tudo é carregado em memória por step) — não serve para simulações gigantes.
- **Latência de input ≈ 1,5s** (1 RTT + ½ step + ½ step histórico). Inadequado para jogos competitivos; ok para simulacra social. **Nosso design WS direto é mais rápido** (~1 RTT + âncora por tile).
- Inputs passam todos pela tabela `inputs` (via banco) — pesado para input de alta frequência.
- Single-threaded: simulação computacionalmente cara não cabe.

### 2.4 Stack resumida

| Componente | Tecnologia | Paralelo Hermes-Corp |
|---|---|---|
| Engine + DB + vector search | Convex (TypeScript, runtime v8) | server.py + rooms.py (Python puro) |
| Transporte | WebSocket (client React do Convex) | WS nosso (protocolo §5) |
| Render | pixi-react (WebGL) | Canvas 2D puro + camadas LAYER_* |
| LLM | Ollama (llama3) / OpenAI / Together / qualquer OpenAI-compatível | Hermes AI Gateway / provedor local |
| Embeddings | mxbai-embed-large (Ollama) | Memory Substrate (FAISS + lexical.db) |
| Auth | Clerk (opcional) | não temos (não precisamos p/ MVP) |
| Deploy | Convex cloud / Docker / Fly.io | localhost (start_stack.sh) |

### 2.5 Lições de engenharia que valem ouro

1. **Estado de jogo pequeno e separado de mensagens** — engine carrega poucos KB; chat fora da engine.
2. **Batch de ticks por step** com invariante single-threaded por mundo + geração monotônica anti-race.
3. **Operação assíncrona única por agente** (`inProgressOperation`) — nunca dois LLM calls concorrentes do mesmo NPC.
4. **Cache de embeddings por hash** — economia direta em hardware fraco.
5. **Mecânica de conversa em 3 estados com walkingOver** — convidar alguém = ela caminha até você; só conversa quando perto. Natural, e casa perfeitamente com nosso pathfinding autoritativo.

---

## 3. LICENÇAS (CÓDIGO E ASSETS) — verificação primária

### 3.1 Código

- **Repo a16z-infra/ai-town: MIT License, Copyright (c) 2023 a16z-infra** — lido direto do `LICENSE` no branch main. Uso comercial permitido, sem copyleft. ✅ **LIMPO.**
- Convex (plataforma) é proprietário, mas o backend self-host oficial via Docker Compose elimina dependência de conta/serviço cloud para rodar.

### 3.2 Assets do AI Town — cada um com licença própria (CUIDADO: o MIT do código NÃO cobre os assets)

Créditos declarados no README oficial, com a licença verificada na fonte de cada asset:

| Asset | Autor | Fonte | Licença verificada | Comercial? | Atribuição obrigatória? |
|---|---|---|---|---|---|
| Tilesheet "16x16 Game Assets" | George Bailey | opengameart.org/content/16x16-game-assets | **CC-BY 4.0** | ✅ SIM | **SIM** — creditar "George Bailey" + link da página |
| Tilesheet "16x16 RPG Tileset" | hilau | opengameart.org/content/16x16-rpg-tileset | **CC-BY** (deriv. de George Bailey + LPC Thatched-roof de bluecarrot16) | ✅ SIM | **SIM** — texto de crédito com cadeia completa |
| "Tiny RPG — Forest" | ansimuz (Luis Zuno) | opengameart.org/content/tiny-rpg-forest | **Domínio público (CC0)** — "free to use on whatever you want, personal or commercial. Credit is not required" | ✅ SIM | NÃO (apreciada) |
| Pixel Art GUI Elements | Mounir Tohami | mounirtohami.itch.io/pixel-art-gui-elements | **CC0** (Creative Commons Zero v1.0 Universal — confirmado por páginas de terceiros que o atribuem como CC0; a página do itch.io não abriu no extrator) | ✅ SIM | NÃO |
| Música do Tiny RPG | Pascal Belisle | patreon/soundcloud thetoadz | **CC-BY** ("free to use as long as you give appropriate credit") | ✅ SIM | SIM |
| Sprites dos personagens (spritesheets 32x32folk) | misto nos forks | ver por spritesheet | não verificável como conjunto único | — | — |

### 3.3 Veredito de licença para o CEO ("sem problema de nada")

- **O conjunto de assets do AI Town É utilizável comercialmente**, mas **não é 100% "sem fazer nada"**: dois tilesheets são **CC-BY** — exigem linha de créditos (trivial, coloca no README + tela de créditos do jogo). UI (Mounir Tohami) e tiles do ansimuz são **CC0/domínio público** — zero obrigação.
- **O QUE NÃO RESOLVE nossa busca:** o AI Town é **top-down ortogonal 16×16**, NÃO isométrico estilo Habbo. Os tiles de floresta/RPG medieval não servem para um escritório corporativo isométrico. **A valia real é a UI CC0 (Mounir Tohami) e o padrão de licenciamento** — o caminho certo é procurar assets isométricos de escritório no OpenGameArt/itch.io filtrando por **CC0** (como: Kenney — CC0, tem packs isométricos; LPC isometric; e5-cyber / "Modern Interiors" de Limezu é CC-BY).
- **Recomendação prática:** usar **Kenney (kenney.nl, 100% CC0)** como base isométrica (ele tem "Isometric Blocks", "Isometric Interior" etc.) — licença limpa de verdade, sem obrigação de atribuição, estilo adequado a escritório. AI Town serve de referência de *organização de spritesheets/manifest*, não de fonte direta de tiles.
- **Asset provenance hygiene:** manter `ASSETS-CREDITS.md` no frontend listando cada sprite → origem → licença. Regra da carta de Arquitetura: fonte primária sempre.

---

## 4. CRUZAMENTO COM O HERMES-CORP (temos / falta / valeria portar)

Base do nosso lado: BLUEPRINT_CORE.md (protocolo §5 congelado) + TOMORROW.md (estado real 17/09: núcleo reconstruído, A1-A7 9/9, B1-B7 41/41, C1-C7 7/7, E1-E3 OK) + Memory Substrate (FastAPI 8767, FAISS + lexical.db) + Supervisor RPC (3120) + souls em 90-Sistema/Setores/ + npc_behaviors.py (behavior trees Dev/DevOps/Researcher/Watchdog/CEO).

| Mecanismo AI Town | Nós JÁ TEMOS (equivalente) | Nós NÃO TEMOS (falta) | Vale portar? |
|---|---|---|---|
| **Engine autoritativa (tick, inputs validados)** | ✅ server.py tick 10 Hz, HANDLERS §5, move.path/âncoras; latência nossa < a deles (~1 RTT vs 1,5s deles) | geração monotônica anti-race para ops async de NPC | ⚪ Parcial — só o padrão de geração, quando o NPC ganhar chamadas LLM async |
| **Movimento BFS + colisão tileMap/blocked** | ✅ pathfinding.py BFS 4-dir, rooms.py, backgroundTiles, bug "No path found" extinto por construção | — | ⚪ Nada a portar; nosso design é igual ou melhor p/ nosso caso |
| **Mapa/cenário** | ✅ rooms com tileMap + manifest de móveis per-tile; culling; camadas LAYER_* | — | ⚪ Idem |
| **Agentes com mesma interface de player** | ✅ NPCs usam move.request unificado (pendência 3 do TOMORROW: wander ainda no movimento legado — migrar) | wander unificado | ✅ Portar a FILOSOFIA já está no blueprint; concluir a migração |
| **Loop de agente com operação assíncrona única** (`inProgressOperation`) | ⚠️ npc_behaviors.py tem BehaviorTree com RUNNING, mas sem gate "1 op LLM por NPC por vez" | gate de operação única + fila de jobs LLM | ✅ **PORTAR** — barato, evita tempestade de LLM calls no 5700U |
| **Conversa NPC↔NPC (convite → walkingOver → participando)** | ⚠️ temos npc.dialogue.* (player↔NPC, intacto §5) e meeting.* | conversa NPC↔NPC iniciada por NPC; estados invited/walkingOver/participating | ✅ **PORTAR** — é O mecanismo que faz o escritório "vivo": chefes se procuram no mapa, caminham (nosso pathfinding já resolve), conversam com bolhas de fala |
| **Memória persistente de conversas (resumo → embedding → busca top-3)** | ⚠️ Memory Substrate indexa vault (FAISS), mas NPCs não lembram conversas do jogo | pipeline: resumir diálogo → embeddar → gravar → recuperar "o que acha do CEO?" no próximo prompt | ✅ **PORTAR** — e nossa vantagem: o Substrate JÁ existe (8767); falta o adapter jogo→memória + cache por hash |
| **Cache de embeddings por hash** | ❌ | — | ✅ Portar junto com o item acima (trivial: dict sqlite hash→vector) |
| **Personalidade no prompt (soul)** | ✅ souls dos chefes já escritas (Nephy, Morgana, Debora, Alice, Liruh) — o AI Town usa description em characters.ts; nós temos material MELHOR | injetar soul no prompt do diálogo | ✅ Só o fio (soul → prompt) |
| **Agenda/cronograma de atividades** | ❌ (AI Town também é fraco aqui: decide por tick, sem cronograma de Smallville) | agenda diária por setor (reunião às X, code review às Y) | ✅ Mas NÃO copiar do AI Town — implementar agenda simples server-side (clock + tabela de eventos por NPC); casa com behavior tree existente |
| **Observador/serenade (música ambiente gerada)** | ❌ | — | ❌ **NÃO portar** — Replicate/MusicGen é serviço pago/cloud, pesado e desnecessário; ruído no 5700U. Se quiser som, asset CC0 estático |
| **Auth (Clerk)** | ❌ | — | ❌ NÃO portar — MVP single-tenant, sem necessidade |
| **Convex (engine/DB/vector)** | ❌ e não queremos — acoplamento a plataforma | — | ❌ NÃO portar — nosso Python puro + Substrate cobre com menos peso e sem lock-in |
| **PixiJS render** | ✅ Canvas 2D puro (decisão de leveza deliberada) | — | ❌ Não trocar; WebGL do Pixi não ganha nada em sala 40×40 |

**Síntese do cruzamento:** nossa fundação (engine autoritativo, pathfinding, render em camadas, protocolo congelado) já é equivalente ou superior para o caso Hermes-Corp. O que o AI Town tem que nos falta está TODO na camada **"vida social"**: conversas NPC↔NPC com memória. É exatamente a camada que o CEO quer (chefes de setor trabalhando) e a que melhor reaproveita nossos dois ativos únicos: souls prontas + Memory Substrate rodando.

---

## 5. RECOMENDAÇÕES PRIORIZADAS (roadmap)

Critérios de priorização: valor para o objetivo do CEO (escritório vivo com chefes trabalhando) × esforço × risco no hardware fraco × reaproveitamento do que já existe. Todas respeitam o servidor autoritativo e o protocolo §5 (mudanças de protocolo = nova entrada congelada no blueprint, nunca remendo).

### P1 — Conversa NPC↔NPC com estados invited/walkingOver/participating
- **O que:** NPC chefe decide procurar outro chefe → envia convite (mensagens novas §5: `npc.conversation.invite/accept/decline` S→S interno + broadcast de estado) → anda até perto (pathfinding existente) → troca 2-4 falas com bolha de fala sobre a sala (`chat.message` já cobre o transporte com `from` = NPC).
- **Por que primeiro:** é o mecanismo central do AI Town e o que gera o efeito "escritório vivo" com o menor toque na engine — núcleo, colisão e pathfinding NÃO mudam; só nasce um módulo `npc_conversations.py` acima do tick existente.
- **Esforço:** 2-3 sessões (1 blueprint complementar de ~100 linhas com a extensão de protocolo + 1-2 de implementação).
- **Risco:** BAIXO. Reusa tudo que já foi testado (A1-A7, E2/E3). Risco real único: temporização das falas — mitigar com cooldowns generosos (≥ 10s entre trocas).

### P2 — Gate "uma operação LLM por NPC" (padrão inProgressOperation)
- **O que:** antes de P1 virar LLM-driven, cada NPC tem no máximo 1 operação assíncrona em curso; fila simples em memória no server; chamadas ao gateway com timeout e fallback para fala de reserva do behavior tree.
- **Por quê:** no 5700U/12GB, 5 chefes + CEO disparando LLM livremente = travada. O AI Town resolve isso por design; nós devemos copiar ANTES do problema existir.
- **Esforço:** 1 sessão. **Risco:** BAIXO — é contenção, não feature.

### P3 — Memória de conversas via Memory Substrate (resumo → embedding → top-3 no prompt)
- **O que:** após cada conversa, resumir (LLM barato) → embeddar via Substrate (8767) → gravar com metadados `npc_id, about, ts` → na próxima conversa, query "o que {NPC} acha de {interlocutor}?" top-3 → injetar no prompt. + Cache de embeddings por hash de texto (sqlite, já temos lexical.db como padrão).
- **Por quê:** é o diferencial do AI Town e nosso disse-off: o Substrate JÁ existe e indexa — só falta o adapter jogo→memória. Nenhum novo serviço.
- **Esforço:** 2-3 sessões (adapter + schema de memórias de jogo + injeção no prompt). **Risco:** MÉDIO — embeddings no 5700U custam; mitigar com cache por hash (P3 inclui) e modelos pequenos (mxbai-embed-large é leve, o mesmo default do AI Town).

### P4 — Agenda diária server-side por setor (não copiar do AI Town)
- **O que:** relógio do jogo + tabela de eventos por NPC (09:00 reunião de setor, 14:00 review…). Behavior tree existente ganha um nó `ScheduledEvent` de prioridade alta; o wander/agenda decide o destino, o movimento já é move.request unificado (pendência 3 do TOMORROW).
- **Por quê:** AI Town NÃO tem isso (decide a cada tick) — o paper original (Smallville) tinha e é o que dá sensação de rotina corporativa. Não é "portar do AI Town", é completar o que nenhum dos dois dá pronto.
- **Esforço:** 1-2 sessões. **Risco:** BAIXO — puro server-side, sem protocolo novo (agenda só influencia destinos).

### P5 — Assets isométricos CC0 (Kenney Isometric Interior) + ASSETS-CREDITS.md
- **O que:** adotar pack isométrico CC0 de escritório (Kenney: kenney.nl, licença CC0, sem atribuição obrigatória) → mapear ao formato de manifest per-tile que o render já consome; criar `frontend/public/assets/ASSETS-CREDITS.md` com provenance de cada sprite.
- **Por quê:** resolve a demanda do CEO ("licença limpa") com licença MELHOR que a do AI Town (que mistura CC-BY 4.0 exigindo créditos). AI Town fica como referência de organização de spritesheet, não de fonte de tiles (é top-down 16×16, não isométrico).
- **Esforço:** 1-2 sessões (recorte/mapeamento é o custo). **Risco:** BAIXO — trocar arte não muda colisão (Princípio 1.3 do blueprint).

### Ordem de execução sugerida
P1 → P2 (juntos fecham o "espetáculo" com segurança) → P3 (memória, o diferencial duradouro) → P4 (rotina) → P5 (assets, independente — pode rodar em paralelo com qualquer um, fronteira de arquivo separada).

### O que explicitamente NÃO adotar (registro de decisão)
- **Convex** — lock-in de plataforma; nosso Python puro + Substrate cobre o mesmo terreno sem novo serviço.
- **PixiJS** — Canvas 2D puro é decisão de leveza deliberada (Princípio 1.4); WebGL não agrega em sala 40×40.
- **MusicGen/Replicate/Fal/Clerk** — serviços cloud pagos, ruído no hardware alvo, fora do MVP.
- **Os tilesheets do AI Town** — licença ok mas estilo errado (top-down medieval/floresta × nosso escritório isométrico Habbo-like).

---

## 6. CONCLUSÃO

O AI Town vale para o Hermes-Corp como **referência de design da camada social** (loop de agente com 1 operação async, conversas com walkingOver, memória resumida+embedada, cache de hash) — não como base de código (stack Convex/TypeScript é desnecessária e lockante) nem como fonte de assets (top-down, CC-BY em parte). O timing é favorável: tudo que o AI Town tem de essencial e nós não temos (vida social com memória) constrói em CIMA do núcleo recém-reconstruído e testado, sem tocar em colisão, pathfinding ou render — exatamente o tipo de extensão que o blueprint prevê (§5 intacto, mensagens novas apenas).

---

*Fontes (verificadas 17/09/2026): LICENSE + README.md + ARCHITECTURE.md de github.com/a16z-infra/ai-town (main); artigo do CEO prompts.brightcoding.dev/blog/ai-town-build-your-own-autonomous-ai-agent-society; páginas de licença opengameart.org (16x16-game-assets, 16x16-rpg-tileset, tiny-rpg-forest); atribuições CC0 de mounirtohami.itch.io/pixel-art-gui-elements em jogos terceiros; BLUEPRINT_CORE.md e TOMORROW.md (reference/ do memory-substrate); CARTA-ARQUITETURA.md e souls (Hermes_Brain/90-Sistema/Setores/).*
