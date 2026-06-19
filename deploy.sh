#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  J.A.R.V.I.S. Deploy Script — Run on AWS EC2
#  Usage: bash deploy.sh
# ═══════════════════════════════════════════════════════════

set -e

REPO_DIR="$HOME/J.A.R.V.I.S_Server"
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║     J.A.R.V.I.S. v3.1 — Deploy Script       ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

cd "$REPO_DIR"

# ── Step 1: Pull latest code ──
echo -e "${YELLOW}[1/5] Pulling latest code...${NC}"
git pull origin main 2>/dev/null || echo "  (skipped — not a git repo or no remote)"

# ── Step 2: Check .env file ──
echo -e "${YELLOW}[2/5] Checking .env...${NC}"
if [ ! -f .env ]; then
    echo -e "  ${YELLOW}⚠ No .env file found! Creating from template...${NC}"
    cp .env.example .env 2>/dev/null || echo "AI_PROVIDER=groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
JARVIS_PASSWORD=jarvis
JWT_SECRET=$(openssl rand -hex 16)
WEATHER_CITY=Delhi" > .env
    echo "  Please edit .env with your API keys: nano .env"
    exit 1
fi
echo -e "  ${GREEN}✅ .env found${NC}"

# ── Step 3: Rebuild Docker ──
echo -e "${YELLOW}[3/5] Rebuilding Docker container...${NC}"
docker compose down 2>/dev/null || true
docker compose up -d --build
echo -e "  ${GREEN}✅ Container started${NC}"

# ── Step 4: Wait for health check ──
echo -e "${YELLOW}[4/5] Waiting for server to be ready...${NC}"
for i in {1..15}; do
    if curl -s -f http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Server is healthy!${NC}"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "  ${YELLOW}⚠ Server may still be starting. Check: docker logs jarvis-server${NC}"
    fi
    sleep 2
done

# ── Step 5: Restart Cloudflare tunnel ──
echo -e "${YELLOW}[5/5] Restarting Cloudflare tunnel...${NC}"
if systemctl is-active --quiet cloudflared 2>/dev/null; then
    sudo systemctl restart cloudflared
    sleep 3
    TUNNEL_URL=$(sudo journalctl -u cloudflared --no-pager -n 50 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
    if [ -n "$TUNNEL_URL" ]; then
        echo -e "  ${GREEN}✅ Tunnel URL: ${CYAN}${TUNNEL_URL}${NC}"
    else
        echo "  Getting tunnel URL... (may take a few seconds)"
        sleep 5
        TUNNEL_URL=$(sudo journalctl -u cloudflared --no-pager -n 50 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
        echo -e "  ${GREEN}Tunnel URL: ${CYAN}${TUNNEL_URL:-'Check: sudo journalctl -u cloudflared --no-pager | grep trycloudflare.com'}${NC}"
    fi
else
    echo "  Cloudflare tunnel service not found. Start it manually:"
    echo "  nohup ./cloudflared tunnel --url http://localhost:8000 &"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ J.A.R.V.I.S. v3.1 deployed successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "  Local:  http://localhost:8000"
if [ -n "$TUNNEL_URL" ]; then
    echo "  Public: $TUNNEL_URL"
fi
echo ""
echo "  Useful commands:"
echo "    docker logs jarvis-server -f    # Live logs"
echo "    docker compose restart          # Restart server"
echo "    docker compose down             # Stop server"
echo ""
