"""
Monitoring Manager - Prometheus, Grafana, alerting
"""

import subprocess
import json
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class AlertRule:
    name: str
    expr: str
    severity: str
    annotations: Dict[str, str]

class MonitoringManager:
    """Manage monitoring stack: Prometheus, Grafana, alerting."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.prometheus_url = self.config.get("prometheus_url", "http://localhost:9090")
        self.grafana_url = self.config.get("grafana_url", "http://localhost:3000")
        self.grafana_token = self.config.get("grafana_token")
    
    def prometheus_query(self, query: str, time: str = None) -> Dict:
        """Execute PromQL query."""
        params = {"query": query}
        if time:
            params["time"] = time
        
        url = f"{self.prometheus_url}/api/v1/query"
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "data": response.text}
    
    def prometheus_query_range(self, query: str, start: str, end: str, step: str) -> Dict:
        """Execute PromQL range query."""
        params = {"query": query, "start": start, "end": end, "step": step}
        url = f"{self.prometheus_url}/api/v1/query_range"
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "data": response.text}
    
    def get_targets(self) -> Dict:
        """Get Prometheus scrape targets."""
        url = f"{self.prometheus_url}/api/v1/targets"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"status": "error"}
    
    def get_rules(self) -> Dict:
        """Get Prometheus alerting/recording rules."""
        url = f"{self.prometheus_url}/api/v1/rules"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"status": "error"}
    
    def grafana_get_dashboards(self) -> List[Dict]:
        """List Grafana dashboards."""
        headers = {"Authorization": f"Bearer {self.grafana_token}"} if self.grafana_token else {}
        url = f"{self.grafana_url}/api/search"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    
    def grafana_get_dashboard(self, uid: str) -> Dict:
        """Get Grafana dashboard by UID."""
        headers = {"Authorization": f"Bearer {self.grafana_token}"} if self.grafana_token else {}
        url = f"{self.grafana_url}/api/dashboards/uid/{uid}"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {}
    
    def grafana_create_dashboard(self, dashboard: Dict, folder_id: int = 0) -> Dict:
        """Create Grafana dashboard."""
        headers = {
            "Authorization": f"Bearer {self.grafana_token}",
            "Content-Type": "application/json"
        } if self.grafana_token else {"Content-Type": "application/json"}
        url = f"{self.grafana_url}/api/dashboards/db"
        payload = {"dashboard": dashboard, "folderId": folder_id, "overwrite": False}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json()
    
    def alertmanager_get_alerts(self) -> List[Dict]:
        """Get active alerts from Alertmanager."""
        # Alertmanager typically runs on port 9093
        url = f"{self.prometheus_url.replace('9090', '9093')}/api/v2/alerts"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []

def create_monitoring_manager(config: dict = None) -> MonitoringManager:
    return MonitoringManager(config)