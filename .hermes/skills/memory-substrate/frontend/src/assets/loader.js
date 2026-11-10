// Asset Loader - loads manifest, images, audio
export class AssetLoader {
  constructor() {
    this.manifest = null;
    this.images = new Map();
    this.audio = new Map();
    this.loaded = false;
  }
  
  async loadManifest() {
    try {
      const response = await fetch('/manifest.json');
      if (!response.ok) throw new Error('Failed to load manifest');
      this.manifest = await response.json();
      console.log('Manifest loaded:', Object.keys(this.manifest).length, 'assets');
    } catch (e) {
      console.warn('Manifest not found, using defaults:', e);
      this.manifest = {};
    }
  }
  
  async loadImage(key) {
    if (this.images.has(key)) return this.images.get(key);
    
    const asset = this.manifest[key];
    if (!asset) {
      console.warn(`Asset not found in manifest: ${key}`);
      return this.createPlaceholder();
    }
    
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        this.images.set(key, img);
        resolve(img);
      };
      img.onerror = () => {
        console.warn(`Failed to load image: ${key}`);
        resolve(this.createPlaceholder());
      };
      img.src = asset.path ? `/assets/${asset.path}` : `/assets/${key}`;
    });
  }
  
  async loadAudio(key) {
    if (this.audio.has(key)) return this.audio.get(key);
    
    const asset = this.manifest[key];
    if (!asset) return null;
    
    return new Promise((resolve) => {
      const audio = new Audio();
      audio.oncanplaythrough = () => {
        this.audio.set(key, audio);
        resolve(audio);
      };
      audio.onerror = () => resolve(null);
      audio.src = asset.path ? `/assets/${asset.path}` : `/assets/${key}`;
      audio.load();
    });
  }
  
  createPlaceholder() {
    const canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ff00ff';
    ctx.fillRect(0, 0, 32, 32);
    ctx.fillStyle = '#000';
    ctx.font = '10px monospace';
    ctx.fillText('?', 10, 20);
    const img = new Image();
    img.src = canvas.toDataURL();
    return img;
  }
  
  getImage(key) {
    return this.images.get(key);
  }
  
  getAudio(key) {
    return this.audio.get(key);
  }
}

