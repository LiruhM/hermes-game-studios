// Meeting Panel UI
export class MeetingPanel {
  constructor(wsClient) {
    this.wsClient = wsClient;
    this.meetings = [];
    this.visible = false;
  }
  
  addMeeting(meeting) {
    this.meetings.push(meeting);
    this.render();
  }
  
  removeMeeting(meetingId) {
    this.meetings = this.meetings.filter(m => m.id !== meetingId);
    this.render();
  }
  
  toggle() {
    this.visible = !this.visible;
    const panel = document.getElementById('meeting-panel');
    if (panel) panel.classList.toggle('active', this.visible);
    if (this.visible) this.render();
  }
  
  close() {
    this.visible = false;
    const panel = document.getElementById('meeting-panel');
    if (panel) panel.classList.remove('active');
  }
  
  render() {
    const list = document.getElementById('meeting-list');
    if (!list) return;
    
    if (this.meetings.length === 0) {
      list.innerHTML = '<div style="padding: 16px; color: #8b949e; text-align: center;">Nenhuma reunião agendada</div>';
      return;
    }
    
    list.innerHTML = this.meetings.map(m => `
      <div class="meeting-item" onclick="window.app?.meetingPanel?.joinMeeting('${m.id}')">
        <div class="meeting-topic">${m.topic}</div>
        <div class="meeting-meta">${m.participants?.length || 0} participantes • ${new Date(m.starts_at).toLocaleTimeString()}</div>
      </div>
    `).join('');
  }
  
  joinMeeting(meetingId) {
    if (this.wsClient) {
      this.wsClient.send('meeting.join', { meeting_id: meetingId });
    }
  }
}

