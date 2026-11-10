#!/usr/bin/env python3
"""
Token Audit Script
Tracks token usage across providers and models.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List


def get_token_log_dir() -> Path:
    """Get the token audit log directory."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA not set")
    log_dir = Path(localappdata) / "hermes" / "logs" / "token-audit"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def load_token_logs(days: int = 7) -> List[Dict[str, Any]]:
    """Load token usage logs from the last N days."""
    log_dir = get_token_log_dir()
    logs = []
    cutoff = datetime.now() - timedelta(days=days)
    
    for log_file in log_dir.glob("tokens-*.jsonl"):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        # Check date
                        entry_time = datetime.fromisoformat(entry.get("timestamp", "").replace("Z", "+00:00"))
                        if entry_time >= cutoff:
                            logs.append(entry)
                    except Exception:
                        continue
        except Exception:
            continue
    
    return logs


def analyze_token_usage(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze token usage patterns."""
    if not logs:
        return {"period_days": 7, "total_requests": 0, "total_tokens": 0, "total_prompt_tokens": 0, "total_completion_tokens": 0, "avg_tokens_per_request": 0, "by_provider": {}, "by_model": {}, "daily": {}}
    
    total_requests = len(logs)
    total_tokens = sum(log.get("total_tokens", 0) for log in logs)
    total_prompt = sum(log.get("prompt_tokens", 0) for log in logs)
    total_completion = sum(log.get("completion_tokens", 0) for log in logs)
    
    by_provider = {}
    by_model = {}
    daily = {}
    
    for log in logs:
        provider = log.get("provider", "unknown")
        model = log.get("model", "unknown")
        date = log.get("timestamp", "")[:10]  # YYYY-MM-DD
        
        tokens = log.get("total_tokens", 0)
        
        if provider not in by_provider:
            by_provider[provider] = {"requests": 0, "tokens": 0, "prompt": 0, "completion": 0}
        by_provider[provider]["requests"] += 1
        by_provider[provider]["tokens"] += tokens
        by_provider[provider]["prompt"] += log.get("prompt_tokens", 0)
        by_provider[provider]["completion"] += log.get("completion_tokens", 0)
        
        if model not in by_model:
            by_model[model] = {"requests": 0, "tokens": 0}
        by_model[model]["requests"] += 1
        by_model[model]["tokens"] += tokens
        
        if date not in daily:
            daily[date] = {"requests": 0, "tokens": 0}
        daily[date]["requests"] += 1
        daily[date]["tokens"] += tokens
    
    # Sort by tokens descending
    by_provider = dict(sorted(by_provider.items(), key=lambda x: x[1]["tokens"], reverse=True))
    by_model = dict(sorted(by_model.items(), key=lambda x: x[1]["tokens"], reverse=True))
    daily = dict(sorted(daily.items()))
    
    return {
        "period_days": 7,
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "avg_tokens_per_request": round(total_tokens / total_requests, 1) if total_requests > 0 else 0,
        "by_provider": by_provider,
        "by_model": by_model,
        "daily": daily,
    }


def estimate_costs(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate costs based on provider pricing (free tiers = $0)."""
    # Free tier providers
    free_providers = {"pollinations", "opencode", "felo", "kiro", "huggingface", "groq"}
    # Low cost providers
    cheap_providers = {"deepseek", "glm", "minimax", "siliconflow"}
    
    costs = {"estimated_usd": 0.0, "by_provider": {}}
    
    for provider, data in analysis.get("by_provider", {}).items():
        provider_lower = provider.lower()
        if any(free in provider_lower for free in free_providers):
            cost = 0.0
        elif any(cheap in provider_lower for cheap in cheap_providers):
            # Rough estimate: $0.10-0.50 per 1M tokens
            cost = (data["tokens"] / 1_000_000) * 0.30
        else:
            # Default estimate for paid providers
            cost = (data["tokens"] / 1_000_000) * 2.00
        
        costs["by_provider"][provider] = {"tokens": data["tokens"], "estimated_usd": round(cost, 4)}
        costs["estimated_usd"] += cost
    
    costs["estimated_usd"] = round(costs["estimated_usd"], 4)
    return costs


def save_audit_report(analysis: Dict[str, Any], costs: Dict[str, Any]) -> Path:
    """Save the audit report."""
    log_dir = get_token_log_dir()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_file = log_dir / f"audit-report-{timestamp}.json"
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "analysis": analysis,
        "costs": costs,
    }
    
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Latest symlink (copy for Windows compatibility)
    latest = log_dir / "latest-audit.json"
    try:
        latest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    
    return report_file


def log_token_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, metadata: Dict = None):
    """Log a token usage entry (called by other scripts)."""
    log_dir = get_token_log_dir()
    log_file = log_dir / f"tokens-{datetime.now().strftime('%Y%m')}.jsonl"
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "metadata": metadata or {},
    }
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Token Audit")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    parser.add_argument("--save", action="store_true", help="Save audit report")
    parser.add_argument("--log", action="store_true", help="Log a test entry")
    args = parser.parse_args()
    
    # Default action: save audit report (for cron compatibility)
    if not any([args.save, args.log]):
        args.save = True
    
    if args.log:
        log_token_usage("test", "test-model", 100, 50, 150, {"test": True})
        print("Logged test entry")
        return 0
    
    print(f"Loading token logs for last {args.days} days...")
    logs = load_token_logs(args.days)
    print(f"Found {len(logs)} log entries")
    
    analysis = analyze_token_usage(logs)
    costs = estimate_costs(analysis)
    
    print("\n=== TOKEN USAGE ANALYSIS ===")
    print(f"Period: {analysis['period_days']} days")
    print(f"Total Requests: {analysis['total_requests']}")
    print(f"Total Tokens: {analysis['total_tokens']:,}")
    print(f"  Prompt: {analysis['total_prompt_tokens']:,}")
    print(f"  Completion: {analysis['total_completion_tokens']:,}")
    print(f"Avg Tokens/Request: {analysis['avg_tokens_per_request']:.1f}")
    
    print("\n--- By Provider ---")
    for provider, data in analysis["by_provider"].items():
        cost = costs["by_provider"].get(provider, {}).get("estimated_usd", 0)
        print(f"  {provider}: {data['requests']} reqs, {data['tokens']:,} tokens, ~${cost:.4f}")
    
    print("\n--- By Model ---")
    for model, data in list(analysis["by_model"].items())[:10]:
        print(f"  {model}: {data['requests']} reqs, {data['tokens']:,} tokens")
    
    print("\n--- Daily ---")
    for date, data in analysis["daily"].items():
        print(f"  {date}: {data['requests']} reqs, {data['tokens']:,} tokens")
    
    print(f"\n=== ESTIMATED COST: ${costs['estimated_usd']:.4f} ===")
    
    if args.save:
        report_file = save_audit_report(analysis, costs)
        print(f"\nReport saved: {report_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())