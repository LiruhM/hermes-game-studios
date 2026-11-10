#!/usr/bin/env python3
"""
Build script for frontend assets
Generates placeholder sprites and validates manifest
"""

import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).parent.parent / "public" / "assets"
MANIFEST_PATH = Path(__file__).parent.parent / "public" / "manifest.json"

# Colors for different entity types
COLORS = {
    'player': '#1f6feb',
    'dev': '#a371f7',
    'devops': '#39d353',
    'researcher': '#d29922',
    'watchdog': '#da3633',
    'ceo': '#ff7b00',
    'npc': '#8b949e',
    'furniture': '#484f58',
    'tile': '#161b22',
    'wall': '#30363d',
    'ui': '#d29922'
}

def create_sprite(path, width, height, color, label=None, frames=1):
    """Create a sprite image with optional multiple frames"""
    img = Image.new('RGBA', (width * frames, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    for frame in range(frames):
        x = frame * width
        # Base shape
        draw.rectangle([x, 0, x + width, height], fill=color, outline='#30363d')
        
        # Add label if provided
        if label:
            try:
                font = ImageFont.truetype("arial.ttf", 8)
            except:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.text((x + (width - text_w) // 2, (height - text_h) // 2), label, fill='#e6edf3', font=font)
    
    path = ASSETS_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print(f"Created: {path}")

def generate_assets():
    """Generate all assets from manifest"""
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    
    print("Generating assets...")
    
    # Avatars
    create_sprite("sprites/avatars/avatar_dev.png", 32, 32, COLORS['dev'], "DEV", 4)
    create_sprite("sprites/avatars/avatar_devops.png", 32, 32, COLORS['devops'], "OPS", 4)
    create_sprite("sprites/avatars/avatar_ceo.png", 32, 32, COLORS['ceo'], "CEO", 4)
    create_sprite("sprites/avatars/avatar_watchdog.png", 32, 32, COLORS['watchdog'], "WATCH", 4)
    create_sprite("sprites/avatars/avatar_player.png", 32, 32, COLORS['player'], "YOU", 4)
    create_sprite("sprites/avatars/avatar_researcher.png", 32, 32, COLORS['researcher'], "R&D", 4)
    
    # Tiles
    create_sprite("tiles/floor_office.png", 32, 32, COLORS['tile'], "FLOOR")
    create_sprite("tiles/floor_meeting.png", 32, 32, '#1c2128', "MEET")
    create_sprite("tiles/wall_north.png", 32, 32, COLORS['wall'], "WALL")
    create_sprite("tiles/wall_east.png", 32, 32, COLORS['wall'], "WALL")
    
    # Furniture
    create_sprite("sprites/furniture/desk.png", 64, 64, COLORS['furniture'], "DESK")
    create_sprite("sprites/furniture/chair.png", 32, 32, COLORS['furniture'], "CHAIR")
    create_sprite("sprites/furniture/whiteboard.png", 64, 64, '#ffffff', "BOARD")
    create_sprite("sprites/furniture/server_rack.png", 64, 128, '#21262d', "RACK")
    
    # UI icons
    create_sprite("sprites/ui/hud_tokens.png", 24, 24, COLORS['ui'], "$")
    create_sprite("sprites/ui/hud_circuit_breaker.png", 24, 24, '#da3633', "CB")
    create_sprite("sprites/ui/hud_watchdog.png", 24, 24, '#39d353', "WD")
    
    print("All assets generated!")

if __name__ == "__main__":
    generate_assets()