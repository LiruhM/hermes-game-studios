// main.js — Bootstrap do Hermes-Corp (§6.2)
// Reduzido ao mínimo: monta câmera, registra handlers, inicia wsClient e o
// gameLoop. Movimento/estado moram em world/, rede em net/, render em render/.
// ZERO pathfinding aqui (§3.4) — clique vira UM move.request (§3.2).

import { WsClient } from './net/wsClient.js';
import { registerHandlers } from './net/handlers.js';
import { WorldState } from './world/worldState.js';
import * as Movement from './world/movement.js';
import { Renderer } from './render/renderer.js';
import { HUD } from './ui/hud.js';
import { Chat } from './ui/chat.js';
import { MeetingPanel } from './ui/meeting.js';
import { NPCDialogue } from './ui/npcDialogue.js';
import { ConversationState, SpeechBubbles, ConversationIndicators } from './ui/speechBubbles.js';
import { AssetLoader } from './assets/loader.js';
import { Camera } from './render/camera.js';
import { Iso } from './render/iso.js';

class HermesCorpApp {
  constructor() {
    this.canvas = document.getElementById('game-canvas');
    this.ctx = this.canvas.getContext('2d');
    this.loadingEl = document.getElementById('loading');
    this.gameContainer = document.getElementById('game-container');

    // Core (posse de C: net/world; B: render; intactos: ui)
    this.wsClient = new WsClient('ws://127.0.0.1:8080/ws');
    this.worldState = new WorldState();
    this.renderer = null;
    this.camera = null;
    this.iso = new Iso();
    this.hud = null;
    this.chat = null;
    this.meetingPanel = null;
    this.npcDialogue = null;
    this.assetLoader = null;

    this.running = false;
    this.lastFrame = 0;
    this.interactionDistance = 1; // tiles p/ diálogo NPC (intacto)
  }

  async init() {
    try {
      this.showLoading('Carregando assets...');
      this.assetLoader = new AssetLoader();
      await this.assetLoader.loadManifest();

      this.showLoading('Iniciando renderização...');
      // Renderer B: new Renderer(ctx, getSprite, {manifest}) (§7.2)
      // getSprite: ponte com o AssetLoader — carrega a imagem on-demand
      // e devolve o <img> (ou null p/ fallback procedural).
      const loader = this.assetLoader;
      const getSprite = (key) => loader.getImage(key);
      this.renderer = new Renderer(this.ctx, getSprite, {
        manifest: loader.manifest || {},
      });
      // Pré-carrega os sprites usados pelo mundo — chaves REAIS do manifest
      // (43 entradas): tile_wall_north/east, tile_door, avatares, pisos.
      const spriteKeys = new Set(['tile_floor_office', 'tile_floor_meeting',
        'tile_wall_north', 'tile_wall_east', 'tile_door']);
      for (const e of Object.keys(loader.manifest || {})) spriteKeys.add(e);
      await Promise.all([...spriteKeys].map((k) => loader.loadImage(k)));

      const rect = this.gameContainer.getBoundingClientRect();
      this.camera = new Camera(rect.width, rect.height);

      // UI (intactos §6.3) — recebem o wsClient como antes
      this.hud = new HUD(this.wsClient);
      this.chat = new Chat(this.wsClient);
      this.meetingPanel = new MeetingPanel(this.wsClient);
      this.npcDialogue = new NPCDialogue(this.wsClient);
      this.hud.createTerminalPanel();

      // Conversa NPC↔NPC (P1 cliente): estado + bolhas + indicadores —
      // canal SEPARADO, fala ambiente em bolha sobre o sprite (§7)
      this.conversations = new ConversationState();
      this.speechBubbles = new SpeechBubbles(this.worldState, this.camera, null);
      this.conversationIndicators = new ConversationIndicators(
        this.worldState, this.camera, this.conversations);

      // Handlers §5: aplicam estado em worldState e alimentam a UI intacta
      registerHandlers(this.wsClient, this.worldState, {
        chat: this.chat,
        npcDialogue: this.npcDialogue,
        meetingPanel: this.meetingPanel,
        hud: this.hud,
        // P1: conversa NPC↔NPC (novos handlers em handlers.js)
        conversations: this.conversations,
        speechBubbles: this.speechBubbles,
        onWelcome: (msg) => {
          // Camera.follow(fn) do B — provedor de posição de tela do self
          this.camera.follow(() => {
            const self = this.worldState.getSelfEntity();
            if (!self) return null;
            return this.iso.tileToScreen(self.x + 0.5, self.y + 0.5);
          });
          this.hud.updateRoomInfo(this.worldState.room);
        },
        onWorldSync: () => {
          // Reconciliação pós-reconnect: câmera segue o jogador de novo
          if (this.worldState.selfEntityId) this.camera.follow(() => {
            const self = this.worldState.getSelfEntity();
            if (!self) return null;
            return this.iso.tileToScreen(self.x + 0.5, self.y + 0.5);
          });
        },
      });

      this.resizeCanvas();
      window.addEventListener('resize', () => this.resizeCanvas());
      this.setupInput();
      this.setupChatInput();

      this.showLoading('Conectando ao servidor...');
      this.wsClient.connect(); // hello é enviado no ws.open pelo handlers.js

      this.hideLoading();
      this.running = true;
      this.lastFrame = performance.now();
      requestAnimationFrame(this.gameLoop.bind(this));
      console.log('Hermes-Corp bootstrap ok');
    } catch (error) {
      console.error('Falha ao inicializar:', error);
      this.showLoading('Erro ao inicializar: ' + error.message);
    }
  }

  resizeCanvas() {
    const rect = this.gameContainer.getBoundingClientRect();
    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = rect.height * window.devicePixelRatio;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = rect.height + 'px';
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    if (this.camera) this.camera.resize(rect.width, rect.height);
    // Renderer B não tem resize (ctx fixo no construtor) — o canvas
    // redimensionado já propaga; nada a fazer aqui.
  }

  setupInput() {
    this.canvas.addEventListener('click', (e) => this.onCanvasClick(e));
    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      this.camera.mousePos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    });
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.camera.zoom = Math.max(0.5, Math.min(2.0,
        this.camera.zoom * (e.deltaY > 0 ? 0.9 : 1.1)));
    }, { passive: false });
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.npcDialogue.close();
      const speed = 20 / this.camera.zoom;
      switch (e.key.toLowerCase()) {
        case 'w': this.camera.targetY -= speed; break;
        case 's': this.camera.targetY += speed; break;
        case 'a': this.camera.targetX -= speed; break;
        case 'd': this.camera.targetX += speed; break;
      }
    });
  }

  // Chat input (index.html #chat-input-field) → chat.message (§5.1)
  setupChatInput() {
    const input = document.getElementById('chat-input-field');
    if (!input) return;
    input.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const content = input.value.trim();
      if (!content) return;
      this.chat.sendMessage(content);
      input.value = '';
    });
  }

  // Clique → screen→tile → UM move.request (§3.2.1, critério C4)
  onCanvasClick(e) {
    const rect = this.canvas.getBoundingClientRect();
    const world = this.camera.screenToWorld(e.clientX - rect.left, e.clientY - rect.top);
    const tile = this.iso.screenToTile(world.x, world.y);

    const self = this.worldState.getSelfEntity();
    if (!self) return;

    // Interação com NPC (comportamento intacto): clique no/adjacente ao NPC
    // com jogador perto → diálogo, sem mover
    const npc = this._findNearbyNPC(self, tile.x, tile.y);
    if (npc) {
      this.wsClient.sendRaw('npc.dialogue.request', { npcId: npc.id });
      return;
    }

    // Movimento: UM pedido, UMA vez. O servidor valida e responde
    // move.path ou move.rejected (§3.2). Nenhum path calculado aqui.
    this.wsClient.sendMoveRequest(self.id, tile.x, tile.y);
  }

  _findNearbyNPC(self, tx, ty) {
    for (const ent of this.worldState.entities.values()) {
      if (ent.type !== 'npc') continue;
      const clickDist = Math.max(Math.abs(tx - ent.col), Math.abs(ty - ent.row));
      const playerDist = Math.max(Math.abs(self.col - ent.col), Math.abs(self.row - ent.row));
      if (playerDist <= this.interactionDistance && clickDist <= 1) return ent;
    }
    return null;
  }

  gameLoop(timestamp) {
    if (!this.running) return;
    const dt = (timestamp - this.lastFrame) / 1000;
    this.lastFrame = timestamp;

    // Interpolação delta-time com âncoras do servidor (§3.3/3.4)
    Movement.update(this.worldState, this.wsClient.nowServerTime());
    this.camera.update(dt);

    // Render: B lê o mundo via worldState.getDrawables() (API congelada §7.2)
    // renderScene(worldData, camera) — clear embutido no frame (fundo CSS).
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.renderer.renderScene(this.worldState.getDrawablesData(), this.camera, timestamp);

    // UI overlays (intactos)
    this.hud.render(timestamp);
    if (this.npcDialogue.visible) this.npcDialogue.render?.(this.ctx);

    // P1: bolhas de fala + indicadores de conversa (reposiciona/auto-dismiss)
    this.speechBubbles?.update();
    this.conversationIndicators?.update();

    requestAnimationFrame(this.gameLoop.bind(this));
  }

  showLoading(message) {
    this.loadingEl.querySelector('span').textContent = message;
    this.loadingEl.style.display = 'flex';
  }

  hideLoading() {
    this.loadingEl.style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.app = new HermesCorpApp();
  window.app.init();
  // Botão ✕ do diálogo NPC (index.html onclick="closeNPCDialogue()")
  window.closeNPCDialogue = () => window.app?.npcDialogue?.close();
});
