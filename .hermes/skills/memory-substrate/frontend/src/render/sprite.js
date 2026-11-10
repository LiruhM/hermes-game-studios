// Sprite and Animation system
export class SpriteAtlas {
  constructor(image, frameWidth, frameHeight, columns, rows) {
    this.image = image;
    this.frameWidth = frameWidth;
    this.frameHeight = frameHeight;
    this.columns = columns;
    this.rows = rows;
    this.totalFrames = columns * rows;
  }
  
  drawFrame(ctx, frameIndex, x, y, zoom = 1) {
    if (frameIndex < 0 || frameIndex >= this.totalFrames) return;
    
    const col = frameIndex % this.columns;
    const row = Math.floor(frameIndex / this.columns);
    
    const sx = col * this.frameWidth;
    const sy = row * this.frameHeight;
    const sw = this.frameWidth;
    const sh = this.frameHeight;
    
    ctx.drawImage(
      this.image,
      sx, sy, sw, sh,
      0, 0,
      sw * zoom, sh * zoom
    );
  }
}

export class Animation {
  constructor(frames, frameRate = 8, loop = true) {
    this.frames = frames; // array of frame indices
    this.frameRate = frameRate;
    this.loop = loop;
    this.currentFrame = 0;
    this.timeAccumulator = 0;
    this.playing = true;
  }
  
  update(dt) {
    if (!this.playing || this.frames.length <= 1) return;
    
    this.timeAccumulator += dt;
    const frameTime = 1 / this.frameRate;
    
    while (this.timeAccumulator >= frameTime) {
      this.timeAccumulator -= frameTime;
      this.currentFrame++;
      
      if (this.currentFrame >= this.frames.length) {
        if (this.loop) {
          this.currentFrame = 0;
        } else {
          this.currentFrame = this.frames.length - 1;
          this.playing = false;
        }
      }
    }
  }
  
  getCurrentFrame() {
    return this.frames[this.currentFrame];
  }
  
  reset() {
    this.currentFrame = 0;
    this.timeAccumulator = 0;
  }
}

export class Sprite {
  constructor(atlas, animations = {}) {
    this.atlas = atlas;
    this.animations = animations;
    this.currentAnimation = 'idle';
    this.animation = animations.idle || null;
  }
  
  play(animationName) {
    if (this.animations[animationName]) {
      this.currentAnimation = animationName;
      this.animation = this.animations[animationName];
      this.animation.reset();
    }
  }
  
  update(dt) {
    if (this.animation) {
      this.animation.update(dt);
    }
  }
  
  draw(ctx, x, y, zoom = 1) {
    if (!this.animation) return;
    
    const frameIndex = this.animation.getCurrentFrame();
    this.atlas.drawFrame(ctx, frameIndex, x, y, zoom);
  }
}

