#!/usr/bin/env bash
# Hermes-Corp Stack - Start All Services
# Run this script to start the full stack

set -e

echo "🚀 Starting Hermes-Corp Stack..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

HERMES_DIR="$HOME/AppData/Local/hermes"
SKILLS_DIR="$HERMES_DIR/skills/memory-substrate"
FRONTEND_DIR="$SKILLS_DIR/frontend"
PYTHON="$HOME/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"

echo -e "${YELLOW}📍 Starting services...${NC}"

# 1. Start Supervisor (port 3120) - MUST start first for other services
echo -e "${YELLOW}🤖 Starting Supervisor RPC (3120)...${NC}"
cd "$HERMES_DIR/scripts"
$PYTHON squad_supervisor.py --daemon > /dev/null 2>&1 &
SUPERVISOR_PID=$!
echo "Supervisor PID: $SUPERVISOR_PID"

# 2. Memory Substrate API (port 8767) — agora OPCIONAL (lazy):
#    pesa ~1GB RAM (índice de 467k chunks) e o jogo só usa em diálogo NPC.
#    Por padrão NÃO sobe — o game server o acorda sozinho no primeiro
#    npc.dialogue.request (protocol.py: _ensure_memory_substrate).
#    Use "./start_stack.sh --com-memoria" para bootá-lo adiantado.
MEM_PID=""
if [ "$1" == "--com-memoria" ]; then
    echo -e "${YELLOW}🔧 Starting Memory Substrate (8767) [modo adiantado]...${NC}"
    cd "$SKILLS_DIR"
    $PYTHON -c "
import uvicorn
from memory_substrate.api_gateway import app
uvicorn.run(app, host='127.0.0.1', port=8767, log_level='info', reload=False)
" > /dev/null 2>&1 &
    MEM_PID=$!
    echo "Memory Substrate PID: $MEM_PID"
else
    echo -e "${YELLOW}🔧 Memory Substrate: lazy (acorda no primeiro diálogo NPC — economiza ~1GB RAM)${NC}"
fi

# 3. Start Game Server (port 8081)
echo -e "${YELLOW}🎮 Starting Game Server (8081)...${NC}"
cd "$SKILLS_DIR"
$PYTHON server.py > /dev/null 2>&1 &
GAME_PID=$!
echo "Game Server PID: $GAME_PID"

# 4. Start Frontend (port 8080)
echo -e "${YELLOW}🌐 Starting Frontend (8080)...${NC}"
cd "$FRONTEND_DIR"
npm run dev -- --host 127.0.0.1 --port 8080 > /dev/null 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services...${NC}"
sleep 5

# Health checks
echo -e "${YELLOW}🏥 Health checks...${NC}"

check_service() {
    local url=$1
    local name=$2
    for i in {1..10}; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ $name OK${NC}"
            return 0
        fi
        sleep 1
    done
    echo -e "${RED}❌ $name FAILED${NC}"
    return 1
}

check_service "http://127.0.0.1:8081/health" "Game Server (8081)"
check_service "http://127.0.0.1:8080" "Frontend (8080)"
check_service "http://127.0.0.1:3120/health" "Supervisor RPC (3120)"
if [ -n "$MEM_PID" ]; then
    check_service "http://127.0.0.1:8767/health" "Memory Substrate (8767)"
else
    echo -e "${GREEN}✅ Memory Substrate (8767) LAZY — sobe sozinho no primeiro diálogo${NC}"
fi

# Test WebSocket
echo -e "${YELLOW}🔌 Testing WebSocket...${NC}"
cd /c/Users/mathe/AppData/Local/hermes/skills/memory-substrate/frontend
$HOME/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe -c "
import asyncio, websockets, json
async def test():
    try:
        async with websockets.connect('ws://127.0.0.1:8081/ws') as ws:
            import json
            await ws.send('{\"type\":\"client.hello\",\"payload\":{\"token\":\"test\"},\"msg_id\":\"startup-test\"}')
            resp = await __import__('asyncio').wait_for(ws.recv(), timeout=5)
            print('✅ WebSocket OK')
    except Exception as e:
        print(f'WS Error: {e}')
import asyncio, websockets
asyncio.run(test())
" 2>&1 | head -5

echo ""
echo -e "${GREEN}✅ Stack running!${NC}"
echo ""
echo "📋 Access points:"
echo "  🌐 Frontend:     http://127.0.0.1:8080"
echo "  🎮 Game Server:  ws://127.0.0.1:8081/ws (health: http://127.0.0.1:8081/health)"
echo "  🧠 Memory:       http://127.0.0.1:8767/health"
echo "  🤖 Supervisor:   http://127.0.0.1:3120/health (RPC: http://127.0.0.1:3120/rpc)"
echo "  🐕 Watchdog:     NSSM service 'HermesWatchdog'"
echo ""
echo "PIDs saved to /tmp/hermes-pids.txt"
echo "SUPERVISOR_PID=$SUPERVISOR_PID" > /tmp/hermes-pids.txt
echo "MEM_PID=$MEM_PID" >> /tmp/hermes-pids.txt
echo "GAME_PID=$GAME_PID" >> /tmp/hermes-pids.txt
echo "FRONTEND_PID=$FRONTEND_PID" >> /tmp/hermes-pids.txt

echo -e "${GREEN}🎮 Ready to play! Open http://127.0.0.1:8080${NC}"