// NPC Dialogue UI
export class NPCDialogue {
  constructor(wsClient) {
    this.wsClient = wsClient;
    this.visible = false;
    this.currentNPC = null;
  }
  
  show(data) {
    this.currentNPC = data.npc_id ?? data.npcId;
    this.visible = true;
    
    const dialogue = document.getElementById('npc-dialogue');
    if (!dialogue) return;
    
    dialogue.classList.add('active');
    
    // Update header
    const nameEl = document.getElementById('npc-dialogue-name');
    const emotionEl = document.getElementById('npc-dialogue-emotion');
    const textEl = document.getElementById('npc-dialogue-text');
    const actionsEl = document.getElementById('npc-dialogue-actions');
    
    // Nome: servidor manda npc_id/npcId (sem npc_name) — resolve via worldState
    let npcName = data.npc_name;
    if (!npcName) {
      const ent = window.app?.worldState?.getEntity?.(this.currentNPC);
      npcName = ent?.name || ent?.meta?.name || 'NPC';
    }
    if (nameEl) nameEl.textContent = npcName;
    if (emotionEl) emotionEl.textContent = data.emotion || 'neutral';
    if (textEl) textEl.textContent = data.text || '';
    
    // Render actions
    if (actionsEl && data.actions && data.actions.length > 0) {
      actionsEl.innerHTML = data.actions.map(action => `
        <button class="btn ${action.primary ? 'btn-primary' : ''}" 
                onclick="window.app?.npcDialogue?.executeAction('${this.currentNPC}', '${action.type}', ${JSON.stringify(action.params || {})})">
          ${action.label || action.type}
        </button>
      `).join('');
    } else if (actionsEl) {
      actionsEl.innerHTML = '';
    }
    
    this.visible = true;
  }
  
  close() {
    this.visible = false;
    const dialogue = document.getElementById('npc-dialogue');
    if (dialogue) dialogue.classList.remove('active');
    this.currentNPC = null;
  }
  
  executeAction(npcId, actionType, params) {
    if (this.wsClient) {
      this.wsClient.send('npc.dialogue.action', {
        npc_id: npcId,
        action: actionType,
        params
      });
    }
  }
}

