// Chat component
export class Chat {
  constructor(wsClient) {
    this.wsClient = wsClient;
    this.messages = [];
    this.maxMessages = 50;
    this.viewportStart = 0;
    this.viewportSize = 25; // Virtual scrolling: render only visible messages
    this.messageHeight = 40; // Estimated height per message in pixels
  }

  addMessage(data) {
    this.messages.push({
      id: data.msg_id,
      sender: data.sender_name,
      senderId: data.sender_id,
      content: data.content,
      timestamp: data.ts,
      // self: comparado contra o entityId do estado (worldState), não do wsClient
      own: data.sender_id === window.app?.worldState?.selfEntityId
    });

    if (this.messages.length > this.maxMessages) {
      this.messages.shift();
    }

    this.render();
  }

  render() {
    const messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;

    // Virtual scrolling: calculate visible range
    const container = document.getElementById('chat-messages');
    const scrollTop = container?.scrollTop || 0;
    const containerHeight = container?.clientHeight || 300;
    
    // Calculate which messages are visible
    const startIdx = Math.max(0, Math.floor(scrollTop / this.messageHeight) - 5); // Buffer of 5
    const visibleCount = Math.ceil(containerHeight / this.messageHeight) + 10; // Buffer of 5 top/bottom
    const endIdx = Math.min(this.messages.length, startIdx + visibleCount);
    
    this.viewportStart = startIdx;
    this.viewportSize = endIdx - startIdx;

    // Create spacer elements for virtual scrolling
    const spacerTopHeight = startIdx * this.messageHeight;
    const spacerBottomHeight = (this.messages.length - endIdx) * this.messageHeight;

    messagesEl.innerHTML = `
      <div class="virtual-spacer-top" style="height: ${spacerTopHeight}px;"></div>
      ${this.messages.slice(startIdx, endIdx).map(msg => `
        <div class="chat-msg ${msg.own ? 'own' : 'other'}">
          <span class="sender">${msg.sender}:</span>
          <span>${this.escapeHtml(msg.content)}</span>
          <span class="time">${new Date(msg.timestamp).toLocaleTimeString()}</span>
        </div>
      `).join('')}
      <div class="virtual-spacer-bottom" style="height: ${spacerBottomHeight}px;"></div>
    `;

    // Auto-scroll to bottom only if user was already at bottom
    if (container) {
      const wasAtBottom = container.scrollTop + containerHeight >= container.scrollHeight - 20;
      if (wasAtBottom) {
        container.scrollTop = container.scrollHeight;
      }
    }
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  sendMessage(content) {
    if (this.wsClient && this.wsClient.connected) {
      this.wsClient.sendChatMessage(content);
    }
  }
}

