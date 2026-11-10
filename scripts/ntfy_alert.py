#!/usr/bin/env python3
"""
NTFy Alert Script
Sends alerts to ntfy.sh topics with proper sanitization.
"""

import json
import os
import sys
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


# NTFy topics
NTFY_COMMANDS = "hermes-mathe-comandos"
NTFY_PRODUCTION = "hermes-mathe-r8gemiyxxm"


def sanitize(text: str) -> str:
    """Remove non-latin1 characters for HTTP header safety."""
    return re.sub(r'[^\x00-\xFF]', '', text)


def send_alert(
    title: str,
    message: str,
    topic: str = NTFY_PRODUCTION,
    priority: str = "default",
    tags: str = "",
    click_url: str = ""
) -> bool:
    """Send an alert to ntfy.sh."""
    clean_title = sanitize(title)
    clean_message = sanitize(message)
    clean_tags = sanitize(tags) if tags else ""
    
    if not clean_title.strip():
        clean_title = "Hermes Alert"
    
    headers = {
        "Title": clean_title,
        "Priority": priority,
    }
    if clean_tags:
        headers["Tags"] = clean_tags
    if click_url:
        headers["Click"] = click_url
    
    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=clean_message.encode('utf-8'),
            headers=headers,
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"Failed to send alert: {e}", file=sys.stderr)
        return False


# Pre-defined alert types
def alert_service_down(service: str, details: str = ""):
    send_alert(
        f"ALERT: {service} DOWN",
        f"{service} esta DOWN\n{details}\nWatchdog tentando reiniciar...",
        priority="high",
        tags="warning,hermes,watchdog"
    )

def alert_service_up(service: str, details: str = ""):
    send_alert(
        f"OK: {service} RESTAURADO",
        f"{service} voltou a funcionar\n{details}",
        priority="default",
        tags="white_check_mark,hermes,watchdog"
    )

def alert_service_restarting(service: str, attempt: int):
    send_alert(
        f"RESTART: {service} REINICIANDO",
        f"Tentativa {attempt} de reinicio do {service}...",
        priority="default",
        tags="arrows_counterclockwise,hermes,watchdog"
    )

def alert_max_restarts(service: str):
    send_alert(
        f"CRITICAL: {service} FALHA CRITICA",
        f"{service} excedeu maximo de reinicios (5 em 5 min).\nIntervencao manual necessaria.",
        priority="urgent",
        tags="rotating_light,hermes,watchdog,critical"
    )

def alert_circuit_open(service: str, details: str = ""):
    send_alert(
        f"CIRCUIT OPEN: {service}",
        f"Circuit breaker aberto para {service}\n{details}",
        priority="high",
        tags="warning,hermes,circuit"
    )

def alert_degradation(service: str, level: str):
    send_alert(
        f"DEGRADATION: {service}",
        f"{service} escalado para nivel {level}",
        priority="high",
        tags="warning,hermes,degradation"
    )

def alert_fallback_activated(from_provider: str, to_provider: str):
    send_alert(
        f"FALLBACK: {from_provider} -> {to_provider}",
        f"Fallback ativado de {from_provider} para {to_provider}",
        priority="default",
        tags="arrows_counterclockwise,hermes,fallback"
    )

def alert_provider_down(provider: str):
    send_alert(
        f"PROVIDER DOWN: {provider}",
        f"Provider {provider} nao responde",
        priority="urgent",
        tags="warning,hermes,provider"
    )

def alert_provider_restored(provider: str):
    send_alert(
        f"PROVIDER RESTORED: {provider}",
        f"Provider {provider} voltou a funcionar",
        priority="default",
        tags="white_check_mark,hermes,provider"
    )

def alert_dispatch_completed(task: str):
    send_alert(
        f"DISPATCH: {task} CONCLUIDO",
        f"Tarefa {task} finalizada com sucesso",
        priority="default",
        tags="white_check_mark,hermes,dispatch"
    )

def alert_dispatch_failed(task: str, error: str):
    send_alert(
        f"DISPATCH FALHOU: {task}",
        f"Tarefa {task} falhou: {error}",
        priority="high",
        tags="warning,hermes,dispatch"
    )

def alert_milestone_risk(milestone: str, risk: str):
    send_alert(
        f"MILESTONE EM RISCO: {milestone}",
        f"Risco: {risk}",
        priority="high",
        tags="warning,hermes,milestone"
    )

def alert_sprint_blocked(sprint: str, blocker: str):
    send_alert(
        f"SPRINT BLOQUEADO: {sprint}",
        f"Bloqueio: {blocker}",
        priority="high",
        tags="warning,hermes,sprint"
    )

def alert_watchdog_started():
    send_alert(
        "Watchdog INICIADO",
        "Monitoramento ativo para todos os servicos Hermes",
        tags="dog,hermes,watchdog"
    )

def alert_watchdog_stopped():
    send_alert(
        "Watchdog PARADO",
        "Monitoramento desativado",
        tags="dog,hermes,watchdog"
    )

def alert_health_check_failed(service: str, error: str):
    send_alert(
        f"HEALTH CHECK FALHOU: {service}",
        f"Servico {service} falhou no health check: {error}",
        priority="high",
        tags="warning,hermes,health"
    )

def alert_session_checkpoint_failed(error: str):
    send_alert(
        "SESSION CHECKPOINT FALHOU",
        f"Falha ao salvar checkpoint da sessao: {error}",
        priority="high",
        tags="warning,hermes,session"
    )

def alert_backup_completed(size_mb: float):
    send_alert(
        "BACKUP CONCLUIDO",
        f"Backup diario completado: {size_mb:.1f} MB",
        priority="default",
        tags="white_check_mark,hermes,backup"
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="NTFy Alert Sender")
    parser.add_argument("--title", required=True, help="Alert title")
    parser.add_argument("--message", required=True, help="Alert message")
    parser.add_argument("--topic", default=NTFY_PRODUCTION, help="NTFy topic")
    parser.add_argument("--priority", default="default", choices=["min", "low", "default", "high", "urgent"], help="Priority")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--click", default="", help="Click URL")
    
    # Pre-defined alerts
    parser.add_argument("--service-down", help="Service down alert")
    parser.add_argument("--service-up", help="Service up alert")
    parser.add_argument("--service-restarting", help="Service restarting alert")
    parser.add_argument("--circuit-open", help="Circuit breaker open alert")
    parser.add_argument("--degradation", help="Degradation alert")
    parser.add_argument("--fallback", nargs=2, metavar=('FROM', 'TO'), help="Fallback alert")
    parser.add_argument("--provider-down", help="Provider down alert")
    parser.add_argument("--provider-restored", help="Provider restored alert")
    parser.add_argument("--dispatch-completed", help="Dispatch completed alert")
    parser.add_argument("--dispatch-failed", nargs=2, metavar=('TASK', 'ERROR'), help="Dispatch failed alert")
    parser.add_argument("--watchdog-started", action="store_true", help="Watchdog started alert")
    parser.add_argument("--watchdog-stopped", action="store_true", help="Watchdog stopped alert")
    
    args = parser.parse_args()
    
    success = False
    
    if args.service_down:
        alert_service_down(args.service_down)
        success = True
    elif args.service_up:
        alert_service_up(args.service_up)
        success = True
    elif args.service_restarting:
        parts = args.service_restarting.split(":")
        service = parts[0]
        attempt = int(parts[1]) if len(parts) > 1 else 1
        alert_service_restarting(service, attempt)
        success = True
    elif args.circuit_open:
        alert_circuit_open(args.circuit_open)
        success = True
    elif args.degradation:
        parts = args.degradation.split(":")
        service = parts[0]
        level = parts[1] if len(parts) > 1 else "unknown"
        alert_degradation(service, level)
        success = True
    elif args.fallback:
        alert_fallback_activated(args.fallback[0], args.fallback[1])
        success = True
    elif args.provider_down:
        alert_provider_down(args.provider_down)
        success = True
    elif args.provider_restored:
        alert_provider_restored(args.provider_restored)
        success = True
    elif args.dispatch_completed:
        alert_dispatch_completed(args.dispatch_completed)
        success = True
    elif args.dispatch_failed:
        alert_dispatch_failed(args.dispatch_failed[0], args.dispatch_failed[1])
        success = True
    elif args.watchdog_started:
        alert_watchdog_started()
        success = True
    elif args.watchdog_stopped:
        alert_watchdog_stopped()
        success = True
    else:
        success = send_alert(args.title, args.message, args.topic, args.priority, args.tags, args.click)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()