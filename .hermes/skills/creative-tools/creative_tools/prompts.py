"""
Prompt Optimizer - Optimize prompts for image generation (Midjourney, DALL-E, Stable Diffusion)
"""

from typing import Dict, List, Any, Optional

class PromptOptimizer:
    """Optimize prompts for AI image generation."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.models = {
            "midjourney": {
                "style_keywords": ["--v 6", "--ar 16:9", "--stylize 250", "--chaos 10"],
                "quality_boost": ["highly detailed", "8k", "masterpiece", "sharp focus"]
            },
            "dalle3": {
                "style_keywords": [],
                "quality_boost": ["highly detailed", "photorealistic", "cinematic lighting"]
            },
            "stable-diffusion": {
                "style_keywords": ["--steps 30", "--cfg 7", "--sampler euler_a"],
                "quality_boost": ["masterpiece", "best quality", "ultra detailed", "8k"]
            }
        }
    
    def optimize(self, prompt: str, model: str = "midjourney", style: str = "photorealistic") -> str:
        """Optimize a prompt for a specific model."""
        model_config = self.models.get(model, self.models["midjourney"])
        
        # Add quality boosters
        quality = " ".join(model_config["quality_boost"])
        
        # Add style keywords
        style_kw = " ".join(model_config["style_keywords"])
        
        # Combine
        optimized = f"{prompt}, {quality}"
        if style_kw:
            optimized += f" {style_kw}"
        
        return optimized
    
    def enhance(self, prompt: str, enhancements: List[str]) -> str:
        """Add specific enhancements to prompt."""
        return f"{prompt}, {', '.join(enhancements)}"
    
    def negative_prompt(self, model: str = "stable-diffusion") -> str:
        """Get recommended negative prompt for model."""
        negatives = {
            "stable-diffusion": "ugly, deformed, noisy, blurry, low quality, distorted, bad anatomy, extra limbs",
            "midjourney": "--no ugly, deformed, noisy, blurry, low quality",
            "dalle3": ""
        }
        return negatives.get(model, negatives["stable-diffusion"])

def create_prompt_optimizer(config: dict = None) -> PromptOptimizer:
    return PromptOptimizer(config)