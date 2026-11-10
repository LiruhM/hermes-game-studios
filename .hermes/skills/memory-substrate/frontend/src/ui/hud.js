// HUD - Heads Up Display for Hermes-Corp
// Canvas-based overlay with real-time metrics from Memory Substrate and Supervisor

export class HUD {
  constructor(wsClient = null) {
    this.wsClient = wsClient;
    
    // Canvas setup
    this.canvas = document.getElementById('hud-canvas');
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    
    // Metrics state
    this.tokens = 0;
    this.maxTokens = 500000;
    this.tokenBurnRate = 0;
    this.tokenHistory = [];
    this.maxHistoryPoints = 60; // 1 minute at 1Hz
    
    this.circuitBreakers = {
      'headroom-proxy': { state: 'closed', failures: 0, lastChange: 0 },
      'headroom-mcp': { state: 'closed', failures: 0, lastChange: 0 },
      'mempalace-mcp': { state: 'closed', failures: 0, lastChange: 0 },
      'system-tray': { state: 'closed', failures: 0, lastChange: 0 }
    };
    
    this.watchdogStatus = 'active';
    this.watchdogLastCheck = 0;
    this.watchdogServices = {};
    
    this.activeTasks = [];
    this.maxTasksShown = 5;
    
    this.agents = {
      'dev': { status: 'idle', lastSeen: 0, currentTask: null },
      'devops': { status: 'idle', lastSeen: 0, currentTask: null },
      'researcher': { status: 'idle', lastSeen: 0, currentTask: null },
      'watchdog': { status: 'active', lastSeen: 0, currentTask: null },
      'ceo': { status: 'idle', lastSeen: 0, currentTask: null }
    };
    
    // Current room display
    this.currentRoom = null;
    this.lastRoomUpdate = 0;
    
    // Toast system
    this.toasts = [];
    this.maxToasts = 5;
    this.toastContainer = document.getElementById('toast-container');
    
    // Chat/log panel
    this.logMessages = [];
    this.maxLogMessages = 50;
    this.logViewportStart = 0;
    this.logViewportSize = 25;
    this.logMessageHeight = 30;
    this.logPanel = document.getElementById('log-panel');
    this.logMessagesEl = document.getElementById('log-messages');

    // Floating Terminal Panel (Ops Room only)
    this.terminalPanel = null;
    this.terminalMessagesEl = null;
    this.terminalVisible = false;
    this.terminalExpanded = false;
    this.terminalHistory = []; // Full history for modal
    this.maxVisibleTerminalEntries = 3;
    this.terminalFadeTimeout = 10000; // 10 seconds
    
    // Animation
    this.animFrame = null;
    this.lastUpdate = 0;
    this.updateInterval = 1000; // 1Hz for metrics
    
    // Data fetching
    this.memorySubstrateUrl = 'http://127.0.0.1:8081'; // game_server has /metrics endpoint
    this.supervisorUrl = 'http://127.0.0.1:3120';
    this.watchdogUrl = 'http://127.0.0.1:3120'; // watchdog runs on same port as supervisor
    this.isFetching = false;
    
    // Style constants
    this.colors = {
      bg: 'rgba(13, 17, 23, 0.95)',
      border: '#30363d',
      text: '#e6edf3',
      textMuted: '#8b949e',
      accent: '#1f6feb',
      accentGlow: 'rgba(31, 111, 235, 0.3)',
      success: '#3fb950',
      warning: '#d29922',
      danger: '#f85149',
      tokenBurn: '#f85149',
      tokenEarn: '#3fb950'
    };
    
    this.fonts = {
      small: '11px "IBM Plex Mono", monospace',
      normal: '12px "IBM Plex Mono", monospace',
      medium: '13px "IBM Plex Mono", monospace',
      large: '16px "IBM Plex Mono", monospace',
      xl: '20px "IBM Plex Mono", monospace'
    };
    
    this.init();
  }
  
  init() {
    this.setupCanvas();
    this.createToastContainer();
    this.createLogPanel();
    this.bindWebSocketEvents();
    this.startAnimationLoop();
    this.startMetricsPolling();
    this.suppressCspErrors();
  }

  addTerminalMessage(msg) {
    // Add to full history
    this.terminalHistory.push(msg);
    
    // Keep history manageable (last 500 entries)
    if (this.terminalHistory.length > 500) {
      this.terminalHistory.shift();
    }
    
    // If terminal is visible, add to visible messages
    if (this.terminalVisible && this.terminalMessagesEl) {
      this.renderTerminalPanel();
    }
    
    // If modal is open, update it
    if (this.terminalExpanded) {
      this.renderTerminalFullHistory();
    }
  }

  // Show/hide terminal based on room
  setTerminalVisibility(roomId) {
    const isOpsRoom = roomId === 'server_room'; // Server room is the "Ops Room"
    
    if (isOpsRoom && !this.terminalVisible) {
      this.terminalVisible = true;
      this.terminalPanel.style.display = 'flex';
      this.renderTerminalPanel();
      
      // Auto-hide after a while if no new messages
      if (this.terminalAutoHideTimer) {
        clearTimeout(this.terminalAutoHideTimer);
      }
      this.terminalAutoHideTimer = setTimeout(() => {
        if (this.terminalVisible && !this.terminalExpanded) {
          this.terminalVisible = false;
          this.terminalPanel.style.display = 'none';
        }
      }, 30000); // 30 seconds
    } else if (!isOpsRoom && this.terminalVisible && !this.terminalExpanded) {
      this.terminalVisible = false;
      this.terminalPanel.style.display = 'none';
      if (this.terminalAutoHideTimer) {
        clearTimeout(this.terminalAutoHideTimer);
      }
    }
    
    // Update badge
    const badge = document.getElementById('terminal-room-badge');
    if (badge) {
      badge.textContent = isOpsRoom ? 'OPS ROOM' : 'HIDDEN';
      badge.style.background = isOpsRoom ? '#1f6feb' : '#30363d';
    }
  }

  renderTerminalPanel() {
    if (!this.terminalMessagesEl) return;
    
    const typeStyles = {
      system: { color: '#1f6feb', prefix: '[SYS]' },
      chat: { color: '#e6edf3', prefix: '[CHAT]' },
      npc: { color: '#a371f7', prefix: '[NPC]' },
      entity: { color: '#79c0ff', prefix: '[ENT]' },
      error: { color: '#f85149', prefix: '[ERR]' },
      warning: { color: '#d29922', prefix: '[WARN]' },
      command: { color: '#3fb950', prefix: '[CMD]' },
      info: { color: '#8b949e', prefix: '[INFO]' },
      debug: { color: '#79c0ff', prefix: '[DBG]' },
      metric: { color: '#d29922', prefix: '[MET]' }
    };
    
    // Get last N messages for visible panel (newest first since flex-direction: column-reverse)
    const visibleMessages = this.terminalHistory.slice(-this.maxVisibleTerminalEntries).reverse();
    
    this.terminalMessagesEl.innerHTML = visibleMessages.map((msg, idx) => {
      const style = typeStyles[msg.type] || typeStyles.info;
      const time = new Date(msg.timestamp).toLocaleTimeString();
      const age = Date.now() - msg.timestamp;
      const fading = age > this.terminalFadeTimeout;
      const fadeStyle = fading ? 'opacity: 0.4; transition: opacity 0.5s;' : '';
      return `
        <div style="display: flex; gap: 8px; line-height: 1.4; ${fadeStyle}" data-timestamp="${msg.timestamp}">
          <span style="color: ${style.color}; flex-shrink: 0;">${style.prefix}</span>
          <span style="color: #8b949e; flex-shrink: 0;">${time}</span>
          <span style="color: ${style.color}; flex: 1; word-break: break-word;">${this.escapeHtml(msg.content)}</span>
        </div>
      `;
    }).join('') || '<div style="color: #8b949e; text-align: center; padding: 20px;">No messages</div>';
  }

  suppressCspErrors() {
    // Suppress CSP violation reports from console spam
    const originalError = console.error;
    console.error = (...args) => {
      // Safely stringify all arguments to handle objects
      const message = args.map(arg => {
        if (typeof arg === 'string') return arg;
        try { return JSON.stringify(arg); } catch { return String(arg); }
      }).join(' ');
      
      if (message.includes('Content Security Policy') || 
          message.includes('CSP') || 
          message.includes('csp') ||
          message.includes('violates the following Content Security Policy')) {
        return; // Suppress CSP errors
      }
      originalError.apply(console, args);
    };
  }

  createTerminalPanel() {
    if (this.terminalPanel) return;
    
    this.terminalPanel = document.createElement('div');
    this.terminalPanel.id = 'terminal-panel';
    this.terminalPanel.style.cssText = `
      position: fixed;
      bottom: 16px;
      left: 16px;
      width: 420px;
      max-height: 220px;
      background: rgba(13, 17, 23, 0.98);
      border: 1px solid #30363d;
      border-radius: 6px;
      display: none;
      flex-direction: column;
      z-index: 1000;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 11px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    `;
    this.terminalPanel.innerHTML = `
      <div id="terminal-header" style="
        padding: 8px 12px;
        border-bottom: 1px solid #30363d;
        font-weight: 600;
        display: flex;
        justify-content: space-between;
        align-items: center;
        cursor: pointer;
      ">
        <span style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 12px;">▶</span>
          <span>System Terminal</span>
          <span id="terminal-room-badge" style="
            background: #1f6feb;
            color: white;
            padding: 1px 6px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: 500;
          ">OPS ROOM</span>
        </span>
        <div style="display: flex; align-items: center; gap: 6px;">
          <button id="terminal-expand" style="
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            font-family: inherit;
            font-size: 10px;
            padding: 2px 6px;
          ">Expand</button>
          <button id="terminal-close" style="
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            font-family: inherit;
            font-size: 10px;
            padding: 2px 6px;
          ">×</button>
        </div>
      </div>
      <div id="terminal-messages" style="
        flex: 1;
        overflow-y: auto;
        padding: 8px;
        display: flex;
        flex-direction: column-reverse;
        gap: 4px;
      "></div>
      <div id="terminal-expanded-modal" style="
        display: none;
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 700px;
        max-height: 500px;
        background: rgba(13, 17, 23, 0.99);
        border: 1px solid #30363d;
        border-radius: 8px;
        z-index: 2000;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 11px;
        box-shadow: 0 16px 48px rgba(0,0,0,0.6);
        flex-direction: column;
      ">
        <div style="
          padding: 12px 16px;
          border-bottom: 1px solid #30363d;
          display: flex;
          justify-content: space-between;
          align-items: center;
        ">
          <span style="font-weight: 600;">Terminal History</span>
          <button id="terminal-modal-close" style="
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            font-family: inherit;
            font-size: 16px;
            padding: 4px 8px;
          ">×</button>
        </div>
        <div id="terminal-full-history" style="
          flex: 1;
          overflow-y: auto;
          padding: 12px 16px;
          display: flex;
          flex-direction: column;
          gap: 3px;
        "></div>
      </div>
    `;
    document.body.appendChild(this.terminalPanel);
    
    this.terminalMessagesEl = document.getElementById('terminal-messages');
    const modal = document.getElementById('terminal-expanded-modal');
    const fullHistoryEl = document.getElementById('terminal-full-history');
    
    // Toggle expand modal
    document.getElementById('terminal-expand')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleTerminalModal();
    });
    
    // Close modal
    document.getElementById('terminal-modal-close')?.addEventListener('click', () => {
      this.closeTerminalModal();
    });
    
    // Close panel (just hide, keep history)
    document.getElementById('terminal-close')?.addEventListener('click', () => {
      this.terminalVisible = false;
      this.terminalPanel.style.display = 'none';
    });
    
    // Click header to expand
    document.getElementById('terminal-header')?.addEventListener('click', (e) => {
      if (e.target.id !== 'terminal-expand' && e.target.id !== 'terminal-close') {
        this.toggleTerminalModal();
      }
    });
    
    // Close modal on outside click
    modal?.addEventListener('click', (e) => {
      if (e.target === modal) {
        this.closeTerminalModal();
      }
    });
  }

  toggleTerminalModal() {
    const modal = document.getElementById('terminal-expanded-modal');
    const fullHistoryEl = document.getElementById('terminal-full-history');
    
    if (this.terminalExpanded) {
      this.closeTerminalModal();
    } else {
      this.terminalExpanded = true;
      modal.style.display = 'flex';
      this.renderTerminalFullHistory();
    }
  }

  closeTerminalModal() {
    const modal = document.getElementById('terminal-expanded-modal');
    this.terminalExpanded = false;
    modal.style.display = 'none';
  }

  renderTerminalFullHistory() {
    const fullHistoryEl = document.getElementById('terminal-full-history');
    if (!fullHistoryEl) return;
    
    const typeStyles = {
      system: { color: '#1f6feb', prefix: '[SYS]' },
      chat: { color: '#e6edf3', prefix: '[CHAT]' },
      npc: { color: '#a371f7', prefix: '[NPC]' },
      entity: { color: '#79c0ff', prefix: '[ENT]' },
      error: { color: '#f85149', prefix: '[ERR]' },
      warning: { color: '#d29922', prefix: '[WARN]' },
      command: { color: '#3fb950', prefix: '[CMD]' },
      info: { color: '#8b949e', prefix: '[INFO]' },
      debug: { color: '#79c0ff', prefix: '[DBG]' },
      metric: { color: '#d29922', prefix: '[MET]' }
    };
    
    fullHistoryEl.innerHTML = this.terminalHistory.map((msg, idx) => {
      const style = typeStyles[msg.type] || typeStyles.info;
      const time = new Date(msg.timestamp).toLocaleTimeString();
      const fadeStyle = msg.fading ? 'opacity: 0.4; transition: opacity 0.5s;' : '';
      return `
        <div style="display: flex; gap: 8px; line-height: 1.4; ${fadeStyle}">
          <span style="color: ${style.color}; flex-shrink: 0;">${style.prefix}</span>
          <span style="color: #8b949e; flex-shrink: 0;">${time}</span>
          <span style="color: ${style.color}; flex: 1; word-break: break-word;">${this.escapeHtml(msg.content)}</span>
        </div>
      `;
    }).join('') || '<div style="color: #8b949e; text-align: center; padding: 20px;">No terminal history</div>';
    
    // Auto-scroll to bottom
    fullHistoryEl.scrollTop = fullHistoryEl.scrollHeight;
  }

  setupCanvas() {
    if (!this.canvas) {
      this.canvas = document.createElement('canvas');
      this.canvas.id = 'hud-canvas';
      this.canvas.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: 1000;
      `;
      document.body.appendChild(this.canvas);
    }
    
    this.ctx = this.canvas.getContext('2d');
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());
  }
  
  resizeCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.parentElement?.getBoundingClientRect() || 
                 { width: window.innerWidth, height: window.innerHeight };
    
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = rect.height + 'px';
    
    if (this.ctx) {
      this.ctx.scale(dpr, dpr);
    }
  }
  
  createToastContainer() {
    if (!this.toastContainer) {
      this.toastContainer = document.createElement('div');
      this.toastContainer.id = 'toast-container';
      this.toastContainer.style.cssText = `
        position: fixed;
        top: 80px;
        right: 16px;
        width: 360px;
        max-height: calc(100vh - 100px);
        pointer-events: none;
        z-index: 1100;
        display: flex;
        flex-direction: column;
        gap: 8px;
      `;
      document.body.appendChild(this.toastContainer);
    }
  }
  
  createLogPanel() {
    if (!this.logPanel) {
      this.logPanel = document.createElement('div');
      this.logPanel.id = 'log-panel';
      this.logPanel.style.cssText = `
        position: fixed;
        bottom: 16px;
        right: 16px;
        width: 400px;
        max-height: 350px;
        background: rgba(13, 17, 23, 0.98);
        border: 1px solid #30363d;
        border-radius: 6px;
        display: flex;
        flex-direction: column;
        z-index: 1000;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 11px;
      `;
      this.logPanel.innerHTML = `
        <div id="log-header" style="
          padding: 8px 12px;
          border-bottom: 1px solid #30363d;
          font-weight: 600;
          display: flex;
          justify-content: space-between;
          align-items: center;
        ">
          <span>System Log</span>
          <button id="log-toggle" style="
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            font-family: inherit;
            font-size: 10px;
            padding: 2px 6px;
          ">Minimize</button>
        </div>
        <div id="log-messages" style="
          flex: 1;
          overflow-y: auto;
          padding: 8px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        "></div>
        <div id="log-input" style="
          padding: 8px;
          border-top: 1px solid #30363d;
          display: flex;
          gap: 8px;
        ">
          <input type="text" id="log-input-field" placeholder="Command..." style="
            flex: 1;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 6px 10px;
            color: #e6edf3;
            font-family: inherit;
            font-size: 11px;
            outline: none;
          ">
        </div>
      `;
      document.body.appendChild(this.logPanel);
      
      this.logMessagesEl = document.getElementById('log-messages');
      
      // Toggle log panel
      document.getElementById('log-toggle')?.addEventListener('click', () => {
        const messages = document.getElementById('log-messages');
        const input = document.getElementById('log-input');
        const btn = document.getElementById('log-toggle');
        if (messages.style.display === 'none') {
          messages.style.display = 'flex';
          input.style.display = 'flex';
          btn.textContent = 'Minimize';
          this.logPanel.style.maxHeight = '350px';
        } else {
          messages.style.display = 'none';
          input.style.display = 'none';
          btn.textContent = 'Expand';
          this.logPanel.style.maxHeight = '50px';
        }
      });
      
      // Handle command input
      document.getElementById('log-input-field')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const input = e.target;
          const cmd = input.value.trim();
          if (cmd) {
            this.addLogMessage({ type: 'command', content: `> ${cmd}`, timestamp: Date.now() });
            this.handleCommand(cmd);
            input.value = '';
          }
        }
      });
    }
  }
  
  bindWebSocketEvents() {
        if (!this.wsClient) return;

        this.wsClient.on('server.welcome', (data) => this.onWelcome(data));
        this.wsClient.on('entity.spawn', (data) => this.onEntitySpawn(data));
        this.wsClient.on('entity.move', (data) => this.onEntityMove(data));
        this.wsClient.on('entity.despawn', (data) => this.onEntityDespawn(data));
        this.wsClient.on('chat.message', (data) => this.onChatMessage(data));
        this.wsClient.on('npc.dialogue.response', (data) => this.onNPCDialogueResponse(data));
        this.wsClient.on('world.state.delta', (data) => this.onWorldDelta(data));
        this.wsClient.on('error', (data) => this.onError(data));
        this.wsClient.on('hud.metrics', (data) => this.updateMetrics(data));
        this.wsClient.on('hud.circuit', (data) => this.updateCircuitBreaker(data));
        this.wsClient.on('hud.watchdog', (data) => this.updateWatchdog(data));
        this.wsClient.on('hud.tasks', (data) => this.updateTasks(data));
        this.wsClient.on('hud.agents', (data) => this.updateAgents(data));
      }

    // WebSocket handlers
    onWelcome(data) {
      this.addLogMessage({ 
        type: 'system', 
        content: `Connected to Hermes-Corp. Welcome ${data.entityId ?? data.entity_id ?? ''}`, 
        timestamp: Date.now() 
      });
      this.addTerminalMessage({
        type: 'system',
        content: `Connected to Hermes-Corp. Welcome ${data.entityId ?? data.entity_id ?? ''}`,
        timestamp: Date.now()
      });
    }

    onEntitySpawn(data) {
      this.addLogMessage({ 
        type: 'entity', 
        content: `Entity spawned: ${data.entity.type} (${data.entity.id})`, 
        timestamp: Date.now() 
      });
      this.addTerminalMessage({
        type: 'entity',
        content: `Entity spawned: ${data.entity.type} (${data.entity.id})`,
        timestamp: Date.now()
      });
    }

    onEntityMove(data) {
      // Could add movement tracking
    }

    onEntityDespawn(data) {
      this.addLogMessage({ 
        type: 'entity', 
        content: `Entity despawned: ${data.entityId ?? data.entity_id} (${data.reason})`, 
        timestamp: Date.now() 
      });
      this.addTerminalMessage({
        type: 'entity',
        content: `Entity despawned: ${data.entityId ?? data.entity_id} (${data.reason})`,
        timestamp: Date.now()
      });
    }

    onChatMessage(data) {
        const name = data.sender_name ?? data.fromName ?? data.from ?? '???';
        const content = data.content ?? '';
        const ts = data.ts ?? data.timestamp ?? Date.now();
        this.addLogMessage({ type: 'chat', content: `${name}: ${content}`, timestamp: ts });
        this.addTerminalMessage({ type: 'chat', content: `${name}: ${content}`, timestamp: ts });
      }

      onNPCDialogueResponse(data) {
        const npcId = data.npc_id ?? data.npcId ?? 'npc';
        const text = data.text ?? '';
        this.addLogMessage({ 
          type: 'npc', 
          content: `[${npcId}] ${text}`, 
          timestamp: Date.now() 
        });
        this.addTerminalMessage({
          type: 'npc',
          content: `[${npcId}] ${text}`,
          timestamp: Date.now()
        });
        this.showToast('NPC Dialogue', (text.length > 80 ? text.substring(0, 80) + '...' : text) || '...', 'info');
      }

      onWorldDelta(data) {
        // Handle delta updates silently
      }

      onError(data) {
        this.addLogMessage({ 
          type: 'error', 
          content: `Error: ${data.code} - ${data.message}`, 
          timestamp: Date.now() 
        });
        this.addTerminalMessage({
          type: 'error',
          content: `Error: ${data.code} - ${data.message}`,
          timestamp: Date.now()
        });
        this.showToast('Error', `${data.code}: ${data.message}`, 'error');
      }
  
  // Metrics polling
  async startMetricsPolling() {
    // Initial fetch
    await this.fetchAllMetrics();
    
    // Poll every second
    setInterval(() => this.fetchAllMetrics(), this.updateInterval);
  }
  
  async fetchAllMetrics() {
      if (this.isFetching) return;
      this.isFetching = true;

      try {
        // Fetch from Memory Substrate /metrics
        await this.fetchMemorySubstrateMetrics();

        // Fetch from Supervisor /rpc
        await this.fetchSupervisorMetrics();

        // Fetch Watchdog status
        await this.fetchWatchdogStatus();
      } catch (e) {
        // Silently fail
      } finally {
        this.isFetching = false;
      }
    }

    async fetchMemorySubstrateMetrics() {
      try {
        const response = await fetch(`${this.memorySubstrateUrl}/metrics`, {
          method: 'GET',
          headers: { 'Accept': 'text/plain' }
        });

        if (response.ok) {
          const text = await response.text();
          this.parsePrometheusMetrics(text);
        }
      } catch (e) {
        // Silently fail - service might not be running
      }
    }

    async fetchSupervisorMetrics() {
      try {
        // Supervisor uses JSON-RPC, we'll call the watch method
        const response = await fetch(`${this.supervisorUrl}/rpc`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'watch',
            params: {},
            id: Date.now()
          })
        });

        if (response.ok) {
          const data = await response.json();
          if (data.result) {
            this.parseSupervisorStatus(data.result);
          }
        }
      } catch (e) {
        // Silently fail
      }
    }

    async fetchWatchdogStatus() {
      try {
        const response = await fetch(`${this.watchdogUrl}/health`, {
          method: 'GET'
        });

        if (response.ok) {
          const data = await response.json();
          this.parseWatchdogHealth(data);
        }
      } catch (e) {
        // Watchdog might not be running
        this.watchdogStatus = 'inactive';
      }
    }
  
  parsePrometheusMetrics(text) {
    const lines = text.split('\n');
    for (const line of lines) {
      if (line.startsWith('#') || !line.trim()) continue;
      
      const match = line.match(/^(\w+)(?:\{([^}]*)\})?\s+(.+)$/);
      if (!match) continue;
      
      const [, metricName, labels, value] = match;
      const val = parseFloat(value);
      
      switch (metricName) {
        case 'finops_tokens_current':
          this.tokens = val;
          break;
        case 'finops_tokens_max':
          this.maxTokens = val;
          break;
        case 'finops_burn_rate_tokens_per_minute':
          this.tokenBurnRate = val;
          break;
        case 'circuit_breaker_state':
          // labels contain service name and state
          const labelMatch = labels.match(/service="([^"]+)"/);
          const stateMatch = labels.match(/state="([^"]+)"/);
          if (labelMatch && stateMatch) {
            const service = labelMatch[1];
            if (this.circuitBreakers[service]) {
              this.circuitBreakers[service].state = stateMatch[1];
            }
          }
          break;
        case 'circuit_breaker_failures':
          const labelMatch2 = labels.match(/service="([^"]+)"/);
          if (labelMatch2 && this.circuitBreakers[labelMatch2[1]]) {
            this.circuitBreakers[labelMatch2[1]].failures = val;
          }
          break;
      }
    }
    
    // Add to history
    this.tokenHistory.push({ tokens: this.tokens, timestamp: Date.now() });
    if (this.tokenHistory.length > this.maxHistoryPoints) {
      this.tokenHistory.shift();
    }
  }
  
  parseSupervisorStatus(data) {
    // Parse supervisor status
    if (data.tasks) {
      this.activeTasks = data.tasks.slice(0, this.maxTasksShown);
    }
    if (data.agents) {
      for (const [id, agent] of Object.entries(data.agents)) {
        if (this.agents[id]) {
          this.agents[id] = { ...this.agents[id], ...agent };
        }
      }
    }
  }
  
  parseWatchdogHealth(data) {
    this.watchdogStatus = data.status || 'unknown';
    this.watchdogLastCheck = Date.now();
    this.watchdogServices = data.services || {};
    
    // Check for circuit breaker states in watchdog
    if (data.circuit_breakers) {
      for (const [name, cb] of Object.entries(data.circuit_breakers)) {
        if (this.circuitBreakers[name]) {
          const prevState = this.circuitBreakers[name].state;
          this.circuitBreakers[name].state = cb.state;
          this.circuitBreakers[name].failures = cb.failures || 0;
          
          // Alert on state change to OPEN
          if (prevState !== 'open' && cb.state === 'open') {
            this.showToast('Circuit Breaker Open', `${name} circuit breaker opened`, 'danger');
          } else if (prevState === 'open' && cb.state === 'closed') {
            this.showToast('Circuit Breaker Closed', `${name} circuit breaker recovered`, 'success');
          }
        }
      }
    }
  }
  
  // Push updates from WebSocket
  updateMetrics(data) {
    if (data.tokens !== undefined) this.tokens = data.tokens;
    if (data.maxTokens !== undefined) this.maxTokens = data.maxTokens;
    if (data.burnRate !== undefined) this.tokenBurnRate = data.burnRate;
    this.addTerminalMessage({
      type: 'metric',
      content: `Tokens: ${this.formatNumber(this.tokens)}/${this.formatNumber(this.maxTokens)} | Burn: ${this.formatNumber(this.tokenBurnRate)}/min`,
      timestamp: Date.now()
    });
  }

  updateCircuitBreaker(data) {
    const { service, state, failures } = data;
    if (this.circuitBreakers[service]) {
      const prevState = this.circuitBreakers[service].state;
      this.circuitBreakers[service].state = state;
      this.circuitBreakers[service].failures = failures || 0;
      this.circuitBreakers[service].lastChange = Date.now();

      if (prevState !== 'open' && state === 'open') {
        this.showToast('Circuit Breaker Open', `${service} circuit breaker opened`, 'danger');
        this.addTerminalMessage({
          type: 'warning',
          content: `Circuit breaker OPEN: ${service} (failures: ${failures})`,
          timestamp: Date.now()
        });
      } else if (prevState === 'open' && state === 'closed') {
        this.showToast('Circuit Breaker Closed', `${service} circuit breaker recovered`, 'success');
        this.addTerminalMessage({
          type: 'info',
          content: `Circuit breaker CLOSED: ${service} recovered`,
          timestamp: Date.now()
        });
      } else {
        this.addTerminalMessage({
          type: 'info',
          content: `Circuit breaker ${service}: ${state.toUpperCase()} (failures: ${failures})`,
          timestamp: Date.now()
        });
      }
    }
  }

  updateWatchdog(data) {
      this.watchdogStatus = data.status || this.watchdogStatus;
      this.watchdogLastCheck = Date.now();
      if (data.services) this.watchdogServices = data.services;
      this.addTerminalMessage({
        type: 'info',
        content: `Watchdog status: ${this.watchdogStatus}`,
        timestamp: Date.now()
      });
    }

    updateTasks(data) {
      if (data.tasks) {
        this.activeTasks = data.tasks.slice(0, this.maxTasksShown);
        this.addTerminalMessage({
          type: 'info',
          content: `Tasks updated: ${data.tasks.length} active`,
          timestamp: Date.now()
        });
      }
    }

    updateAgents(data) {
      if (data.agents) {
        for (const [id, agent] of Object.entries(data.agents)) {
          if (this.agents[id]) {
            this.agents[id] = { ...this.agents[id], ...agent };
          }
        }
        this.addTerminalMessage({
          type: 'info',
          content: `Agent status sync: ${Object.keys(data.agents).length} agents`,
          timestamp: Date.now()
        });
      }
  }

  // Toast system
  showToast(title, message, type = 'info') {
    const toast = document.createElement('div');
    const colors = {
      info: { bg: '#1f6feb', border: '#1f6feb', icon: 'ℹ️' },
      success: { bg: '#3fb950', border: '#3fb950', icon: '✅' },
      warning: { bg: '#d29922', border: '#d29922', icon: '⚠️' },
      danger: { bg: '#f85149', border: '#f85149', icon: '🔴' }
    };
    
    const style = colors[type] || colors.info;
    
    toast.style.cssText = `
      background: ${style.bg};
      border: 1px solid ${style.border};
      border-radius: 6px;
      padding: 10px 12px;
      color: white;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 11px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.4);
      animation: slideIn 0.3s ease-out;
      pointer-events: auto;
      max-width: 360px;
    `;
    
    toast.innerHTML = `
      <div style="display: flex; align-items: flex-start; gap: 8px;">
        <span style="font-size: 14px; flex-shrink: 0;">${style.icon}</span>
        <div style="flex: 1; min-width: 0;">
          <div style="font-weight: 600; margin-bottom: 2px;">${title}</div>
          <div style="opacity: 0.9; white-space: pre-wrap; word-break: break-word;">${message}</div>
        </div>
        <button onclick="this.parentElement.parentElement.remove()" style="
          background: none;
          border: none;
          color: white;
          cursor: pointer;
          font-size: 14px;
          padding: 0;
          line-height: 1;
          opacity: 0.7;
        ">✕</button>
      </div>
    `;
    
    this.toastContainer.appendChild(toast);
    this.toasts.push(toast);
    
    // Remove oldest if over limit
    if (this.toasts.length > this.maxToasts) {
      const oldest = this.toasts.shift();
      oldest.remove();
    }
    
    // Auto-remove after 8 seconds
    setTimeout(() => {
      if (toast.parentElement) {
        toast.style.animation = 'slideOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
        this.toasts = this.toasts.filter(t => t !== toast);
      }
    }, 8000);
  }
  
  // Log panel
  addLogMessage(msg) {
    this.logMessages.push(msg);
    if (this.logMessages.length > this.maxLogMessages) {
      this.logMessages.shift();
    }
    this.renderLogPanel();
  }
  
  renderLogPanel() {
      if (!this.logMessagesEl) return;

      const typeStyles = {
        system: { color: '#1f6feb', prefix: '[SYS]' },
        chat: { color: '#e6edf3', prefix: '[CHAT]' },
        npc: { color: '#a371f7', prefix: '[NPC]' },
        entity: { color: '#79c0ff', prefix: '[ENT]' },
        error: { color: '#f85149', prefix: '[ERR]' },
        warning: { color: '#d29922', prefix: '[WARN]' },
        command: { color: '#3fb950', prefix: '[CMD]' },
        info: { color: '#8b949e', prefix: '[INFO]' }
      };

      // Virtual scrolling: calculate visible range
      const container = this.logMessagesEl;
      const scrollTop = container?.scrollTop || 0;
      const containerHeight = container?.clientHeight || 300;

      const startIdx = Math.max(0, Math.floor(scrollTop / this.logMessageHeight) - 5);
      const visibleCount = Math.ceil(containerHeight / this.logMessageHeight) + 10;
      const endIdx = Math.min(this.logMessages.length, startIdx + visibleCount);

      this.logViewportStart = startIdx;
      this.logViewportSize = endIdx - startIdx;

      // Create spacer elements for virtual scrolling
      const spacerTopHeight = startIdx * this.logMessageHeight;
      const spacerBottomHeight = (this.logMessages.length - endIdx) * this.logMessageHeight;

      this.logMessagesEl.innerHTML = `
        <div class="virtual-spacer-top" style="height: ${spacerTopHeight}px;"></div>
        ${this.logMessages.slice(startIdx, endIdx).map(msg => {
          const style = typeStyles[msg.type] || typeStyles.info;
          const time = new Date(msg.timestamp).toLocaleTimeString();
          return `
            <div style="display: flex; gap: 8px; line-height: 1.4; opacity: 0.9; height: ${this.logMessageHeight}px;">
              <span style="color: ${style.color}; flex-shrink: 0;">${style.prefix}</span>
              <span style="color: #8b949e; flex-shrink: 0;">${time}</span>
              <span style="color: ${style.color}; flex: 1; word-break: break-word;">${this.escapeHtml(msg.content)}</span>
            </div>
          `;
        }).join('')}
        <div class="virtual-spacer-bottom" style="height: ${spacerBottomHeight}px;"></div>
      `;

      // Auto-scroll to bottom only if user was already at bottom
      const wasAtBottom = container.scrollTop + containerHeight >= container.scrollHeight - 20;
      if (wasAtBottom) {
        container.scrollTop = container.scrollHeight;
      }
  }
  
  handleCommand(cmd) {
    const parts = cmd.split(' ');
    const command = parts[0].toLowerCase();
    const args = parts.slice(1);
    
    switch (command) {
      case 'help':
        this.addLogMessage({ type: 'info', content: 'Commands: help, clear, status, agents, tasks, tokens, circuit, watchdog', timestamp: Date.now() });
        break;
      case 'clear':
        this.logMessages = [];
        this.renderLogPanel();
        break;
      case 'status':
        this.addLogMessage({ type: 'info', content: `Tokens: ${this.tokens}/${this.maxTokens} | Burn: ${this.tokenBurnRate}/min | Watchdog: ${this.watchdogStatus}`, timestamp: Date.now() });
        break;
      case 'agents':
        for (const [id, agent] of Object.entries(this.agents)) {
          this.addLogMessage({ type: 'info', content: `${id}: ${agent.status} ${agent.currentTask ? `- ${agent.currentTask}` : ''}`, timestamp: Date.now() });
        }
        break;
      case 'tasks':
        if (this.activeTasks.length === 0) {
          this.addLogMessage({ type: 'info', content: 'No active tasks', timestamp: Date.now() });
        } else {
          for (const task of this.activeTasks) {
            this.addLogMessage({ type: 'info', content: `Task: ${task.title} (${task.status}) - ${task.assignee}`, timestamp: Date.now() });
          }
        }
        break;
      case 'circuit':
        for (const [name, cb] of Object.entries(this.circuitBreakers)) {
          this.addLogMessage({ type: 'info', content: `${name}: ${cb.state} (failures: ${cb.failures})`, timestamp: Date.now() });
        }
        break;
      case 'watchdog':
        this.addLogMessage({ type: 'info', content: `Watchdog: ${this.watchdogStatus} | Last check: ${this.watchdogLastCheck ? new Date(this.watchdogLastCheck).toLocaleTimeString() : 'never'}`, timestamp: Date.now() });
        for (const [svc, status] of Object.entries(this.watchdogServices)) {
          this.addLogMessage({ type: 'info', content: `  ${svc}: ${status}`, timestamp: Date.now() });
        }
        break;
      default:
        this.addLogMessage({ type: 'error', content: `Unknown command: ${command}. Type 'help' for commands.`, timestamp: Date.now() });
    }
  }
  
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  // Animation loop
  startAnimationLoop() {
    const loop = (timestamp) => {
      this.render(timestamp);
      this.animFrame = requestAnimationFrame(loop);
    };
    this.animFrame = requestAnimationFrame(loop);
  }
  
  stopAnimationLoop() {
    if (this.animFrame) {
      cancelAnimationFrame(this.animFrame);
      this.animFrame = null;
    }
  }
  
  render(timestamp) {
    if (!this.ctx) return;
    
    const ctx = this.ctx;
    const width = this.canvas.width / (window.devicePixelRatio || 1);
    const height = this.canvas.height / (window.devicePixelRatio || 1);
    
    // Clear
    ctx.clearRect(0, 0, width, height);
    
    // Render HUD components
    this.renderTopBar(ctx, width);
    this.renderRightPanel(ctx, width, height);
    this.renderTokenGraph(ctx, width, height);
  }
  
  renderTopBar(ctx, width) {
    const barHeight = 48;
    const padding = 16;
    const panelGap = 12;
    
    // Background bar
    ctx.fillStyle = this.colors.bg;
    ctx.fillRect(0, 0, width, barHeight);
    
    // Border bottom
    ctx.strokeStyle = this.colors.border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, barHeight);
    ctx.lineTo(width, barHeight);
    ctx.stroke();
    
    let x = padding;
    
    // Token counter with animation
    x = this.renderTokenCounter(ctx, x, padding, barHeight);
    
    // Circuit breakers
    x += panelGap;
    x = this.renderCircuitBreakers(ctx, x, padding, barHeight);
    
    // Watchdog
    x += panelGap;
    x = this.renderWatchdog(ctx, x, padding, barHeight);
    
    // Task count
    x += panelGap;
    x = this.renderTaskCount(ctx, x, padding, barHeight);
    
    // Current Room
    x += panelGap;
    x = this.renderCurrentRoom(ctx, x, padding, barHeight);
  }
  
  renderCurrentRoom(ctx, x, y, height) {
    const panelWidth = 180;
    const centerY = y + height / 2;
    const room = this.currentRoom;
    
    if (!room) return x + panelWidth;
    
    this.drawRoundedRect(ctx, x, y + 4, panelWidth, height - 8, 6, this.colors.bg, this.colors.border);
    
    // Room icon
    const roomIcons = {
      'lobby': '🏢',
      'main_office': '💼',
      'meeting_room_1': '📋',
      'cafe': '☕',
      'vault': '🔐',
      'lab': '🔬',
      'server_room': '🖥️'
    };
    
    ctx.font = '16px "IBM Plex Mono", monospace';
    ctx.fillStyle = this.colors.text;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(roomIcons[room.id] || '📍', x + 10, centerY - 6);
    
    // Room name
    ctx.font = this.fonts.medium;
    ctx.fillStyle = this.colors.text;
    const shortName = room.name.length > 18 ? room.name.substring(0, 18) + '…' : room.name;
    ctx.fillText(shortName, x + 32, centerY - 6);
    
    // Room status
    ctx.font = this.fonts.small;
    ctx.fillStyle = room.is_meeting ? this.colors.warning : this.colors.success;
    ctx.fillText(room.is_meeting ? 'MEETING' : 'OPEN', x + 32, centerY + 10);
    
    return x + panelWidth;
  }
  
  renderTokenCounter(ctx, x, y, height) {
    const panelWidth = 220;
    const centerY = y + height / 2;
    
    // Panel background
    this.drawRoundedRect(ctx, x, y + 4, panelWidth, height - 8, 6, this.colors.bg, this.colors.border);
    
    // Label
    ctx.font = this.fonts.small;
    ctx.fillStyle = this.colors.textMuted;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText('TOKENS', x + 12, centerY - 8);
    
    // Animated token value
    ctx.font = this.fonts.xl;
    ctx.fillStyle = this.colors.text;
    const tokenText = this.formatNumber(this.tokens) + ' / ' + this.formatNumber(this.maxTokens);
    ctx.fillText(tokenText, x + 12, centerY + 8);
    
    // Burn rate indicator
    if (this.tokenBurnRate > 0) {
      ctx.font = this.fonts.small;
      const burnColor = this.tokenBurnRate > 1000 ? this.colors.danger : this.colors.warning;
      ctx.fillStyle = burnColor;
      const burnText = `▼ ${this.formatNumber(this.tokenBurnRate)}/min`;
      ctx.fillText(burnText, x + 12, centerY + 24);
    }
    
    // Mini sparkline
    this.drawTokenSparkline(ctx, x + panelWidth - 80, y + 6, 70, height - 12);
    
    return x + panelWidth;
  }
  
  drawTokenSparkline(ctx, x, y, w, h) {
    if (this.tokenHistory.length < 2) return;
    
    const maxTokens = Math.max(...this.tokenHistory.map(p => p.tokens), this.maxTokens);
    const minTokens = Math.min(...this.tokenHistory.map(p => p.tokens));
    const range = maxTokens - minTokens || 1;
    
    ctx.strokeStyle = this.colors.tokenBurn;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    
    this.tokenHistory.forEach((point, i) => {
      const px = x + (i / (this.tokenHistory.length - 1)) * w;
      const py = y + h - ((point.tokens - minTokens) / range) * h;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    
    ctx.stroke();
    
    // Gradient fill under line
    const gradient = ctx.createLinearGradient(0, y, 0, y + h);
    gradient.addColorStop(0, 'rgba(248, 81, 73, 0.15)');
    gradient.addColorStop(1, 'rgba(248, 81, 73, 0)');
    ctx.fillStyle = gradient;
    ctx.lineTo(x + w, y + h);
    ctx.lineTo(x, y + h);
    ctx.closePath();
    ctx.fill();
  }
  
  renderCircuitBreakers(ctx, x, y, height) {
    const services = Object.keys(this.circuitBreakers);
    const panelWidth = services.length * 80;
    const centerY = y + height / 2;
    
    this.drawRoundedRect(ctx, x, y + 4, panelWidth, height - 8, 6, this.colors.bg, this.colors.border);
    
    ctx.font = this.fonts.small;
    ctx.fillStyle = this.colors.textMuted;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('CIRCUITS', x + panelWidth / 2, centerY - 10);
    
    services.forEach((service, i) => {
      const cb = this.circuitBreakers[service];
      const cx = x + i * 80 + 40;
      
      // Status dot
      const colors = {
        closed: this.colors.success,
        half_open: this.colors.warning,
        open: this.colors.danger
      };
      
      const color = colors[cb.state] || this.colors.textMuted;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(cx, centerY + 2, 5, 0, Math.PI * 2);
      ctx.fill();
      
      // Pulsing effect for open/half-open
      if (cb.state !== 'closed') {
        const pulse = Math.sin(Date.now() / 200) * 0.5 + 0.5;
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.3 + pulse * 0.3;
        ctx.beginPath();
        ctx.arc(cx, centerY + 2, 8 + pulse * 4, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      
      // Service name
      ctx.font = '9px "IBM Plex Mono", monospace';
      ctx.fillStyle = this.colors.textMuted;
      ctx.textAlign = 'center';
      const shortName = service.replace('headroom-', 'hr-').replace('mempalace-', 'mp-');
      ctx.fillText(shortName, cx, centerY + 18);
    });
    
    return x + panelWidth;
  }
  
  renderWatchdog(ctx, x, y, height) {
    const panelWidth = 100;
    const centerY = y + height / 2;
    const isActive = this.watchdogStatus === 'active';
    
    this.drawRoundedRect(ctx, x, y + 4, panelWidth, height - 8, 6, this.colors.bg, this.colors.border);
    
    // Status indicator
    ctx.fillStyle = isActive ? this.colors.success : this.colors.danger;
    ctx.beginPath();
    ctx.arc(x + 18, centerY, 6, 0, Math.PI * 2);
    ctx.fill();
    
    // Pulsing for active
    if (isActive) {
      const pulse = Math.sin(Date.now() / 500) * 0.5 + 0.5;
      ctx.strokeStyle = this.colors.success;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.3 + pulse * 0.3;
      ctx.beginPath();
      ctx.arc(x + 18, centerY, 10 + pulse * 5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    
    ctx.font = this.fonts.medium;
    ctx.fillStyle = this.colors.text;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(isActive ? 'WATCHDOG' : 'WATCHDOG', x + 32, centerY - 6);
    
    ctx.font = this.fonts.small;
    ctx.fillStyle = this.colors.textMuted;
    ctx.fillText(isActive ? 'ACTIVE' : 'INACTIVE', x + 32, centerY + 10);
    
    return x + panelWidth;
  }
  
  renderTaskCount(ctx, x, y, height) {
    const panelWidth = 100;
    const centerY = y + height / 2;
    const taskCount = this.activeTasks.length;
    
    this.drawRoundedRect(ctx, x, y + 4, panelWidth, height - 8, 6, this.colors.bg, this.colors.border);
    
    ctx.font = this.fonts.xl;
    ctx.fillStyle = taskCount > 0 ? this.colors.accent : this.colors.textMuted;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(taskCount.toString(), x + panelWidth / 2, centerY - 2);
    
    ctx.font = this.fonts.small;
    ctx.fillStyle = this.colors.textMuted;
    ctx.fillText('TASKS', x + panelWidth / 2, centerY + 16);
    
    return x + panelWidth;
  }
  
  renderRightPanel(ctx, width, height) {
    const panelWidth = 220;
    const x = width - panelWidth - 16;
    const y = 64;
    const panelHeight = Math.min(400, height - 80);
    
    // Panel background
    this.drawRoundedRect(ctx, x, y, panelWidth, panelHeight, 8, this.colors.bg, this.colors.border);
    
    let cy = y + 16;
    
    // Title
    ctx.font = this.fonts.medium;
    ctx.fillStyle = this.colors.text;
    ctx.textAlign = 'left';
    ctx.fillText('AGENT STATUS', x + 16, cy);
    cy += 24;
    
    // Agent badges
    for (const [id, agent] of Object.entries(this.agents)) {
      cy = this.renderAgentBadge(ctx, x + 12, cy, panelWidth - 24, id, agent);
      cy += 8;
    }
    
    // Active tasks
    if (this.activeTasks.length > 0) {
      cy += 8;
      ctx.font = this.fonts.medium;
      ctx.fillStyle = this.colors.text;
      ctx.fillText('ACTIVE TASKS', x + 16, cy);
      cy += 20;
      
      for (const task of this.activeTasks.slice(0, 5)) {
        cy = this.renderTaskItem(ctx, x + 12, cy, panelWidth - 24, task);
        cy += 6;
      }
    }
  }
  
  renderAgentBadge(ctx, x, y, width, id, agent) {
    const statusColors = {
      active: this.colors.success,
      idle: this.colors.textMuted,
      busy: this.colors.accent,
      offline: this.colors.danger,
      moving: this.colors.warning
    };
    
    const color = statusColors[agent.status] || this.colors.textMuted;
    const badgeHeight = 28;
    
    // Background
    this.drawRoundedRect(ctx, x, y, width, badgeHeight, 4, 'rgba(255,255,255,0.03)', 'rgba(255,255,255,0.05)');
    
    // Status dot
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x + 10, y + badgeHeight / 2, 5, 0, Math.PI * 2);
    ctx.fill();
    
    // Pulsing for active/busy
    if (agent.status === 'active' || agent.status === 'busy') {
      const pulse = Math.sin(Date.now() / 400) * 0.5 + 0.5;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.4 + pulse * 0.3;
      ctx.beginPath();
      ctx.arc(x + 10, y + badgeHeight / 2, 8 + pulse * 3, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    
    // Agent name
    ctx.font = this.fonts.normal;
    ctx.fillStyle = this.colors.text;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    const displayName = id.charAt(0).toUpperCase() + id.slice(1);
    ctx.fillText(displayName, x + 22, y + badgeHeight / 2 - 6);
    
    // Status
    ctx.font = this.fonts.small;
    ctx.fillStyle = color;
    ctx.fillText(agent.status.toUpperCase(), x + 22, y + badgeHeight / 2 + 8);
    
    // Current task
    if (agent.currentTask) {
      ctx.font = '10px "IBM Plex Mono", monospace';
      ctx.fillStyle = this.colors.textMuted;
      const taskText = agent.currentTask.length > 25 ? agent.currentTask.substring(0, 25) + '…' : agent.currentTask;
      ctx.fillText(taskText, x + 80, y + badgeHeight / 2);
    }
    
    return y + badgeHeight;
  }
  
  renderTaskItem(ctx, x, y, width, task) {
    const itemHeight = 24;
    
    // Background
    this.drawRoundedRect(ctx, x, y, width, itemHeight, 3, 'rgba(255,255,255,0.02)', 'none');
    
    // Priority indicator
    const priorityColors = { high: this.colors.danger, medium: this.colors.warning, low: this.colors.success };
    const pColor = priorityColors[task.priority] || this.colors.textMuted;
    ctx.fillStyle = pColor;
    ctx.fillRect(x, y, 3, itemHeight);
    
    // Task title
    ctx.font = this.fonts.small;
    ctx.fillStyle = this.colors.text;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    const title = task.title.length > 28 ? task.title.substring(0, 28) + '…' : task.title;
    ctx.fillText(title, x + 8, y + itemHeight / 2);
    
    // Assignee
    ctx.font = '9px "IBM Plex Mono", monospace';
    ctx.fillStyle = this.colors.textMuted;
    ctx.textAlign = 'right';
    ctx.fillText(task.assignee || 'unassigned', x + width - 4, y + itemHeight / 2);
    
    return y + itemHeight;
  }
  
  renderTokenGraph(ctx, width, height) {
    // Small token burn graph at bottom left
    const graphWidth = 280;
    const graphHeight = 80;
    const x = 16;
    const y = height - graphHeight - 16;
    
    if (this.tokenHistory.length < 2) return;
    
    this.drawRoundedRect(ctx, x, y, graphWidth, graphHeight, 6, this.colors.bg, this.colors.border);
    
    // Title
    ctx.font = this.fonts.small;
    ctx.fillStyle = this.colors.textMuted;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText('TOKEN BURN RATE (1m)', x + 10, y + 6);
    
    // Graph area
    const gx = x + 10;
    const gy = y + 24;
    const gw = graphWidth - 20;
    const gh = graphHeight - 34;
    
    // Grid lines
    ctx.strokeStyle = 'rgba(48, 54, 61, 0.5)';
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
      const gyLine = gy + (i / 4) * gh;
      ctx.beginPath();
      ctx.moveTo(gx, gyLine);
      ctx.lineTo(gx + gw, gyLine);
      ctx.stroke();
    }
    
    // Data line
    const maxRate = Math.max(...this.tokenHistory.map(p => p.tokens), 1000);
    const minRate = Math.min(...this.tokenHistory.map(p => p.tokens));
    const range = maxRate - minRate || 1;
    
    ctx.strokeStyle = this.colors.tokenBurn;
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    this.tokenHistory.forEach((point, i) => {
      const px = gx + (i / (this.tokenHistory.length - 1)) * gw;
      const py = gy + gh - ((point.tokens - minRate) / range) * gh;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    
    ctx.stroke();
    
    // Fill
    const gradient = ctx.createLinearGradient(0, gy, 0, gy + gh);
    gradient.addColorStop(0, 'rgba(248, 81, 73, 0.2)');
    gradient.addColorStop(1, 'rgba(248, 81, 73, 0)');
    ctx.fillStyle = gradient;
    ctx.lineTo(gx + gw, gy + gh);
    ctx.lineTo(gx, gy + gh);
    ctx.closePath();
    ctx.fill();
    
    // Current value
    ctx.font = this.fonts.medium;
    ctx.fillStyle = this.colors.tokenBurn;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillText(this.formatNumber(this.tokenBurnRate) + '/min', x + graphWidth - 10, y + graphHeight - 8);
  }
  
  // Utility methods
  drawRoundedRect(ctx, x, y, w, h, r, fillColor, strokeColor) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
    
    if (fillColor) {
      ctx.fillStyle = fillColor;
      ctx.fill();
    }
    
    if (strokeColor && strokeColor !== 'none') {
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }
  
  formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return Math.floor(num).toString();
  }
  
  // Public API
  setWebSocketClient(wsClient) {
    this.wsClient = wsClient;
    this.bindWebSocketEvents();
  }

  updateRoomInfo(room) {
    this.currentRoom = room;
    this.lastRoomUpdate = Date.now();
    if (room && room.id) {
      this.setTerminalVisibility(room.id);
    }
  }

  destroy() {
    this.stopAnimationLoop();
    this.canvas?.remove();
    this.toastContainer?.remove();
    this.logPanel?.remove();
    this.terminalPanel?.remove();
    const modal = document.getElementById('terminal-expanded-modal');
    modal?.remove();
  }
}

// CSS for toast animations (injected via JS)
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
  }
`;
document.head.appendChild(style);