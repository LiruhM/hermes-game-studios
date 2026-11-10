#!/usr/bin/env python3
"""
Hermes Ecosystem Watchdog
Monitors all services and auto-restarts on failure.
Runs as persistent daemon with configurable intervals.
"""

import subprocess
import requests
import time
import json
import logging
import sys
import os
import threading
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum

# Setup logging
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "watchdog.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("watchdog")

# NTFy topics
NTFY_COMMANDS = "hermes-mathe-comandos"
NTFY_PRODUCTION = "hermes-mathe-r8gemiyxxm"


class ServiceState(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    RESTARTING = "restarting"
    UNKNOWN = "unknown"


@dataclass
class Service:
    name: str
    health_check: Callable[[], tuple[ServiceState, str]]
    restart_cmd: list[str] | str
    cwd: str = None
    env: dict = None
    shell: bool = False
    critical: bool = True
    check_interval: int = 30
    max_restarts: int = 5
    restart_window: int = 300

    state: ServiceState = ServiceState.UNKNOWN
    last_check: float = 0
    last_restart: float = 0
    restart_count: int = 0
    consecutive_failures: int = 0
    process: subprocess.Popen = None


class NTFyNotifier:
    @staticmethod
    def send(title: str, message: str, topic: str = NTFY_COMMANDS, priority: str = "default", tags: str = ""):
        try:
            import re
            clean_title = re.sub(r'[^\x00-\xFF]', '', title)
            clean_message = re.sub(r'[^\x00-\xFF]', '', message)
            if not clean_title.strip():
                clean_title = "Hermes Watchdog"

            headers = {"Title": clean_title, "Priority": priority}
            if tags:
                headers["Tags"] = tags

            requests.post(
                f"https://ntfy.sh/{topic}",
                data=clean_message.encode('utf-8'),
                headers=headers,
                timeout=5
            )
            logger.debug(f"Notification sent: {clean_title}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    @staticmethod
    def service_down(service: str, details: str):
        NTFyNotifier.send(f"ALERT: {service} DOWN", f"{service} esta DOWN\n{details}\nWatchdog tentando reiniciar...", priority="high", tags="warning,hermes,watchdog")

    @staticmethod
    def service_up(service: str, details: str = ""):
        NTFyNotifier.send(f"OK: {service} RESTAURADO", f"{service} voltou a funcionar\n{details}", priority="default", tags="white_check_mark,hermes,watchdog")

    @staticmethod
    def service_restarting(service: str, attempt: int):
        NTFyNotifier.send(f"RESTART: {service} REINICIANDO", f"Tentativa {attempt} de reinicio do {service}...", priority="default", tags="arrows_counterclockwise,hermes,watchdog")

    @staticmethod
    def max_restarts_exceeded(service: str):
        NTFyNotifier.send(f"CRITICAL: {service} FALHA CRITICA", f"{service} excedeu maximo de reinicios (5 em 5 min).\nIntervencao manual necessaria.", priority="urgent", tags="rotating_light,hermes,watchdog,critical")

    @staticmethod
    def circuit_opened(service: str, details: str):
        NTFyNotifier.send(f"CIRCUIT OPEN: {service}", f"Circuit breaker aberto para {service}\n{details}", priority="high", tags="warning,hermes,circuit")

    @staticmethod
    def degradation_escalated(service: str, level: str):
        NTFyNotifier.send(f"DEGRADATION: {service}", f"{service} escalado para nivel {level}", priority="high", tags="warning,hermes,degradation")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: float = 30.0
    half_open_max_calls: int = 3
    excluded_exceptions: tuple = (TimeoutError,)


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        self._lock = threading.Lock()

    def _transition_to_open(self):
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        logger.warning(f"Circuit breaker {self.name} OPENED")

    def _transition_to_half_open(self):
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        logger.info(f"Circuit breaker {self.name} HALF_OPEN")

    def _transition_to_closed(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"Circuit breaker {self.name} CLOSED")

    def _on_success(self):
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def _on_failure(self):
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to_open()
            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.config.failure_threshold:
                    self._transition_to_open()

    def call(self, func: Callable, *args, **kwargs):
        with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.config.timeout_seconds:
                    self._transition_to_half_open()
                else:
                    raise CircuitOpenError(f"Circuit {self.name} OPEN")
            elif self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitOpenError(f"Circuit {self.name} HALF_OPEN limit")
                self.half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.excluded_exceptions:
            raise
        except Exception as e:
            self._on_failure()
            raise


class DegradationLevel:
    NORMAL = 0
    KOMPRESS_DISABLED = 1
    QUEUE_REQUESTS = 2
    SHED_NON_CRITICAL = 3
    FAIL_FAST = 4


class DegradationManager:
    def __init__(self):
        self.feature_flags = {
            "compression_enabled": True,
            "queue_requests": False,
            "shed_non_critical": False,
            "fail_fast": False,
        }

    def evaluate(self, health_data: dict) -> int:
        checks = health_data.get("checks", {})
        metrics = health_data.get("metrics", {})
        level = DegradationLevel.NORMAL

        if not checks.get("kompress", {}).get("ready", True):
            level = max(level, DegradationLevel.KOMPRESS_DISABLED)

        p99 = metrics.get("latency_p99_ms", 0)
        if p99 > 5000:
            level = max(level, DegradationLevel.FAIL_FAST)
        elif p99 > 2000:
            level = max(level, DegradationLevel.QUEUE_REQUESTS)

        error_rate = metrics.get("error_rate_5m", 0)
        if error_rate > 0.10:
            level = max(level, DegradationLevel.FAIL_FAST)
        elif error_rate > 0.05:
            level = max(level, DegradationLevel.SHED_NON_CRITICAL)

        return level

    def apply(self, level: int):
        self.feature_flags = {
            "compression_enabled": level < DegradationLevel.KOMPRESS_DISABLED,
            "queue_requests": level >= DegradationLevel.QUEUE_REQUESTS,
            "shed_non_critical": level >= DegradationLevel.SHED_NON_CRITICAL,
            "fail_fast": level >= DegradationLevel.FAIL_FAST,
        }


class AdaptiveSchedule:
    def __init__(self):
        self.intervals = {
            "healthy": 30,
            "degraded": 10,
            "down": 5,
            "restarting": 2,
            "unknown": 60,
        }
        self.jitter_pct = 0.2

    def get_interval(self, state: str) -> float:
        import random
        base = self.intervals.get(state, 30)
        jitter = base * self.jitter_pct * (random.random() * 2 - 1)
        return max(1, base + jitter)


class Watchdog:
    def __init__(self):
        self.services: Dict[str, Service] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.degradation_manager = DegradationManager()
        self.adaptive_schedule = AdaptiveSchedule()
        self.running = False
        self.check_thread: Optional[threading.Thread] = None
        self.health_server_thread: Optional[threading.Thread] = None
        self._setup_services()
        self._setup_circuit_breakers()
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_services(self):
        # Headroom Proxy (8787) - CRITICAL
        self.services["headroom-proxy"] = Service(
            name="Headroom Proxy",
            health_check=self._check_headroom_proxy,
            restart_cmd=["headroom", "proxy", "--port", "8787", "--host", "127.0.0.1"],
            critical=True, check_interval=30,
        )
        # MemPalace MCP (8765) - CRITICAL
        self.services["mempalace-mcp"] = Service(
            name="MemPalace MCP",
            health_check=self._check_mempalace_mcp,
            restart_cmd=["mempalace-mcp", "--transport", "http", "--host", "127.0.0.1", "--port", "8765"],
            critical=True, check_interval=30,
        )
        # System Tray (36787)
        self.services["system-tray"] = Service(
            name="System Tray",
            health_check=self._check_system_tray,
            restart_cmd=["python", "-m", "windows_system_tray", "--daemon"],
            cwd=str(Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "skills" / "development" / "windows-system-tray"),
            env=self._get_tray_env(), critical=False, check_interval=60,
        )
        # Cron Jobs Health
        self.services["cron-jobs"] = Service(
            name="Cron Jobs",
            health_check=self._check_cron_jobs,
            restart_cmd=None, critical=True, check_interval=300,
        )
        # Hermes AI Gateway (20128) - CRITICAL
        self.services["ai-gateway"] = Service(
            name="Hermes AI Gateway",
            health_check=self._check_ai_gateway,
            restart_cmd=["docker", "restart", "hermes-ai-gateway"],
            critical=True, check_interval=30,
        )
        # Session Persistence
        self.services["session-persistence"] = Service(
            name="Session Persistence",
            health_check=self._check_session_persistence,
            restart_cmd=None, critical=True, check_interval=60,
        )

    def _get_tray_env(self) -> dict:
        env = os.environ.copy()
        skill_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "skills" / "development" / "windows-system-tray"
        env["PYTHONPATH"] = str(skill_dir) + os.pathsep + env.get("PYTHONPATH", "")
        return env

    def _setup_circuit_breakers(self):
        self.circuit_breakers = {
            "headroom-proxy": CircuitBreaker("headroom-proxy", CircuitBreakerConfig(
                failure_threshold=3, timeout_seconds=60, success_threshold=2
            )),
            "mempalace-mcp": CircuitBreaker("mempalace-mcp", CircuitBreakerConfig(
                failure_threshold=3, timeout_seconds=60
            )),
            "ai-gateway": CircuitBreaker("ai-gateway", CircuitBreakerConfig(
                failure_threshold=5, timeout_seconds=60, success_threshold=2
            )),
        }

    # ===== HEALTH CHECKS =====

    def _quick_check(self, url: str, method: str = "GET", json_data: dict = None, timeout: int = 3, retries: int = 2) -> tuple[bool, str]:
        for attempt in range(retries + 1):
            try:
                if method == "GET":
                    resp = requests.get(url, timeout=timeout)
                else:
                    resp = requests.post(url, json=json_data, timeout=timeout)
                if resp.status_code == 200:
                    return True, ""
                return False, f"HTTP {resp.status_code}"
            except requests.ConnectionError:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return False, "Connection refused"
            except requests.Timeout:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return False, "Timeout"
            except Exception as e:
                return False, str(e)
        return False, "Max retries"

    def _check_headroom_proxy(self) -> tuple[ServiceState, str]:
        start = time.time()
        ok, err = self._quick_check("http://127.0.0.1:8787/health", timeout=3, retries=2)
        latency_ms = (time.time() - start) * 1000
        if ok:
            try:
                resp = requests.get("http://127.0.0.1:8787/health", timeout=2)
                data = resp.json()
                status = data.get("status", "unknown")
                ready = data.get("ready", True)
                checks = data.get("checks", {})
                kompress_ready = checks.get("kompress", {}).get("ready", True)
                
                if not ready or status == "unhealthy":
                    return ServiceState.DOWN, f"status: {status}, ready: {ready}"
                if not kompress_ready:
                    return ServiceState.DEGRADED, "kompress not ready"
                if latency_ms > 500:
                    return ServiceState.DEGRADED, f"latency {latency_ms:.0f}ms"
                return ServiceState.HEALTHY, f"v{data.get('version', '?')}, uptime {data.get('uptime_seconds', 0):.0f}s"
            except:
                return ServiceState.HEALTHY, "responding"
        return ServiceState.DOWN, err

    def _check_mempalace_mcp(self) -> tuple[ServiceState, str]:
        ok, err = self._quick_check("http://127.0.0.1:8765/mcp", method="POST", json_data={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=3, retries=2)
        if ok:
            try:
                resp = requests.post("http://127.0.0.1:8765/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=2)
                data = resp.json()
                tools = data.get("result", {}).get("tools", [])
                return ServiceState.HEALTHY, f"{len(tools)} tools"
            except:
                return ServiceState.HEALTHY, "responding"
        return ServiceState.DOWN, err

    def _check_system_tray(self) -> tuple[ServiceState, str]:
        ok, err = self._quick_check("http://127.0.0.1:36787/status", timeout=3, retries=2)
        if ok:
            try:
                resp = requests.get("http://127.0.0.1:36787/status", timeout=2)
                data = resp.json()
                state = data.get("state", "unknown")
                return ServiceState.HEALTHY, f"state={state}"
            except:
                return ServiceState.HEALTHY, "responding"
        return ServiceState.DOWN, err

    def _check_cron_jobs(self) -> tuple[ServiceState, str]:
        try:
            result = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10, cwd=Path(os.environ.get("LOCALAPPDATA", "")) / "hermes")
            if result.returncode == 0:
                output = result.stdout
                if "error" in output.lower() or "failed" in output.lower():
                    return ServiceState.DEGRADED, "Alguns jobs com erro"
                return ServiceState.HEALTHY, "Todos OK"
            return ServiceState.DOWN, "hermes cron list falhou"
        except Exception as e:
            return ServiceState.DOWN, str(e)

    def _check_ai_gateway(self) -> tuple[ServiceState, str]:
        start = time.time()
        ok, err = self._quick_check("http://127.0.0.1:20128/health", timeout=3, retries=2)
        latency_ms = (time.time() - start) * 1000
        if ok:
            try:
                resp = requests.get("http://127.0.0.1:20128/health", timeout=2)
                data = resp.json()
                status = data.get("status", "unknown")
                if status == "healthy":
                    return ServiceState.HEALTHY, f"latency {latency_ms:.0f}ms"
                elif status == "degraded":
                    return ServiceState.DEGRADED, f"status: {status}, latency {latency_ms:.0f}ms"
                return ServiceState.DOWN, f"status: {status}"
            except:
                return ServiceState.HEALTHY, "responding"
        return ServiceState.DOWN, err

    def _check_session_persistence(self) -> tuple[ServiceState, str]:
        try:
            active_md = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "memory" / "active.md"
            if active_md.exists():
                mtime = active_md.stat().st_mtime
                age = time.time() - mtime
                if age < 300:  # Updated within 5 min
                    return ServiceState.HEALTHY, f"active.md atualizado ha {age:.0f}s"
                return ServiceState.DEGRADED, f"active.md antigo ({age:.0f}s)"
            return ServiceState.DOWN, "active.md nao existe"
        except Exception as e:
            return ServiceState.DOWN, str(e)

    # ===== SERVICE MANAGEMENT =====

    def _start_service(self, service: Service) -> bool:
        try:
            cmd = service.restart_cmd
            if isinstance(cmd, str):
                cmd = cmd.split()
            service.process = subprocess.Popen(cmd, cwd=service.cwd, env=service.env, shell=service.shell, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            logger.info(f"Started {service.name} (PID: {service.process.pid})")
            return True
        except Exception as e:
            logger.error(f"Failed to start {service.name}: {e}")
            return False

    def _stop_service(self, service: Service):
        if service.process:
            try:
                service.process.terminate()
                service.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                service.process.kill()
            except Exception as e:
                logger.error(f"Error stopping {service.name}: {e}")
            finally:
                service.process = None

    def _restart_service(self, service: Service) -> bool:
        now = time.time()
        if now - service.last_restart > service.restart_window:
            service.restart_count = 0
        if service.restart_count >= service.max_restarts:
            logger.critical(f"{service.name} exceeded max restarts ({service.max_restarts} in {service.restart_window}s)")
            NTFyNotifier.max_restarts_exceeded(service.name)
            return False
        service.state = ServiceState.RESTARTING
        service.restart_count += 1
        service.last_restart = now
        logger.warning(f"Restarting {service.name} (attempt {service.restart_count}/{service.max_restarts})")
        NTFyNotifier.service_restarting(service.name, service.restart_count)
        self._stop_service(service)
        time.sleep(2)
        if self._start_service(service):
            service.state = ServiceState.HEALTHY
            service.consecutive_failures = 0
            logger.info(f"{service.name} restarted successfully")
            return True
        else:
            service.state = ServiceState.DOWN
            return False

    # ===== MAIN LOOP =====

    def check_service(self, key: str):
        service = self.services[key]
        now = time.time()
        if now - service.last_check < service.check_interval:
            return
        service.last_check = now
        
        cb = self.circuit_breakers.get(key)
        if cb and cb.state == CircuitState.OPEN:
            service.state = ServiceState.DOWN
            logger.warning(f"Circuit breaker {key} OPEN, skipping check")
            return

        try:
            if cb:
                state, details = cb.call(service.health_check)
            else:
                state, details = service.health_check()
        except CircuitOpenError:
            service.state = ServiceState.DOWN
            NTFyNotifier.circuit_opened(service.name, "Circuit breaker open")
            return
        except Exception as e:
            state, details = ServiceState.DOWN, str(e)

        prev_state = service.state
        service.state = state
        
        if state == ServiceState.HEALTHY:
            service.consecutive_failures = 0
            if prev_state in (ServiceState.DOWN, ServiceState.DEGRADED, ServiceState.RESTARTING):
                logger.info(f"OK {service.name} RECUPERADO: {details}")
                NTFyNotifier.service_up(service.name, details)
        elif state == ServiceState.DEGRADED:
            service.consecutive_failures += 1
            logger.warning(f"WARN {service.name} DEGRADADO: {details}")
            if service.consecutive_failures >= 3 and service.critical:
                NTFyNotifier.send(f"WARN {service.name} DEGRADADO", f"{service.name} degradado ha {service.consecutive_failures} checks\n{details}", priority="high")
        elif state == ServiceState.DOWN:
            service.consecutive_failures += 1
            logger.error(f"DOWN {service.name} CAIU: {details}")
            if service.critical or service.consecutive_failures >= 2:
                NTFyNotifier.service_down(service.name, details)
            if service.restart_cmd and service.restart_count < service.max_restarts:
                self._restart_service(service)
            elif service.restart_count >= service.max_restarts:
                logger.critical(f"{service.name} - max restarts exceeded, not attempting restart")

    def run_checks(self):
        for key in self.services:
            try:
                self.check_service(key)
            except Exception as e:
                logger.error(f"Error checking {key}: {e}")

    def _monitor_loop(self):
        logger.info("Watchdog monitoring started")
        NTFyNotifier.send("Watchdog INICIADO", "Monitoramento ativo para todos os servicos Hermes", tags="dog,hermes,watchdog", topic=NTFY_PRODUCTION)
        while self.running:
            try:
                self.run_checks()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            # Adaptive sleep based on worst service state
            worst_state = "healthy"
            for svc in self.services.values():
                if svc.state == ServiceState.DOWN:
                    worst_state = "down"
                    break
                elif svc.state == ServiceState.DEGRADED and worst_state != "down":
                    worst_state = "degraded"
                elif svc.state == ServiceState.RESTARTING and worst_state == "healthy":
                    worst_state = "restarting"
            
            sleep_time = self.adaptive_schedule.get_interval(worst_state)
            time.sleep(sleep_time)

    def start(self):
        if self.running:
            return
        self.running = True
        self.check_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.check_thread.start()
        self._start_health_server()
        logger.info("Watchdog started")

    def stop(self):
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=10)
        for service in self.services.values():
            self._stop_service(service)
        logger.info("Watchdog stopped")
        NTFyNotifier.send("Watchdog PARADO", "Monitoramento desativado", tags="dog,hermes,watchdog", topic=NTFY_PRODUCTION)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def status(self) -> dict:
        return {key: {"name": svc.name, "state": svc.state.value, "last_check": datetime.fromtimestamp(svc.last_check).isoformat() if svc.last_check else None, "consecutive_failures": svc.consecutive_failures, "restart_count": svc.restart_count, "pid": svc.process.pid if svc.process else None} for key, svc in self.services.items()}

    def _start_health_server(self):
        """Start HTTP health endpoint on port 36788"""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json
        
        watchdog = self
        
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    
                    # Aggregate status
                    services_status = watchdog.status()
                    healthy = sum(1 for s in services_status.values() if s["state"] == "healthy")
                    degraded = sum(1 for s in services_status.values() if s["state"] == "degraded")
                    down = sum(1 for s in services_status.values() if s["state"] == "down")
                    total = len(services_status)
                    
                    overall = "healthy" if down == 0 and degraded == 0 else ("degraded" if down == 0 else "unhealthy")
                    
                    circuit_breakers = {name: {"state": cb.state.value} for name, cb in watchdog.circuit_breakers.items()}
                    
                    health_data = {
                        "service": "hermes-watchdog",
                        "status": overall,
                        "services": {"total": total, "healthy": healthy, "degraded": degraded, "down": down},
                        "circuit_breakers": circuit_breakers,
                        "details": services_status
                    }
                    
                    self.wfile.write(json.dumps(health_data, indent=2).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                pass  # Suppress default logging
        
        self.health_server = HTTPServer(("127.0.0.1", 36788), HealthHandler)
        self.health_server_thread = threading.Thread(target=self.health_server.serve_forever, daemon=True)
        self.health_server_thread.start()
        logger.info("Watchdog health server started on port 36788")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Ecosystem Watchdog")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--once", action="store_true", help="Run checks once and exit")
    args = parser.parse_args()
    watchdog = Watchdog()
    if args.status:
        print(json.dumps(watchdog.status(), indent=2))
        return
    if args.once:
        watchdog.run_checks()
        print(json.dumps(watchdog.status(), indent=2))
        return
    watchdog.start()
    try:
        while watchdog.running:
            time.sleep(1)
    except KeyboardInterrupt:
        watchdog.stop()


if __name__ == "__main__":
    main()