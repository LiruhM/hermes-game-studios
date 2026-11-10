"""
Knowledge Compounding Pipeline v1.0 — Orchestrator
Main pipeline orchestration: Capture → Organize → Distill → Express → Review
"""

import schedule
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from knowledge_pipeline.capture import CaptureEngine, CaptureConfig, CapturedItem, CaptureSource, CaptureType
from knowledge_pipeline.organize import OrganizeEngine, OrganizeConfig, OrganizeResult
from knowledge_pipeline.distill import DistillEngine, DistillConfig, DistillResult
from knowledge_pipeline.express import ExpressEngine, ExpressConfig, ExpressResult


@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""
    vault_path: str = "C:/Users/mathe/Hermes_Brain"
    
    # Stage configs
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    organize: OrganizeConfig = field(default_factory=OrganizeConfig)
    distill: DistillConfig = field(default_factory=DistillConfig)
    express: ExpressConfig = field(default_factory=ExpressConfig)
    
    # Scheduling
    schedule: Dict[str, Any] = field(default_factory=lambda: {
        "capture_external": "*/30 * * * *",      # Every 30 min
        "organize_inbox": "0 * * * *",           # Hourly
        "detect_drift": "0 9 * * *",             # Daily 9am
        "distill_pending": "0 2 * * *",          # Daily 2am
        "express_scheduled": "0 6 * * 1",        # Weekly Monday 6am
        "review_weekly": "0 8 * * 1",            # Weekly Monday 8am
        "review_monthly": "0 9 1 * *",           # Monthly 1st 9am
    })
    
    # Token optimization
    token_optimization: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "inherit_by_default": True,
        "budget_profile": "analysis"
    })


@dataclass
class PipelineRunResult:
    """Result of a full pipeline run."""
    timestamp: datetime
    capture_results: List[CapturedItem] = field(default_factory=list)
    organize_results: Optional[OrganizeResult] = None
    distill_results: List[DistillResult] = field(default_factory=list)
    express_results: List[ExpressResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class PipelineOrchestrator:
    """
    Main orchestrator for the Knowledge Compounding Pipeline.
    
    Runs stages in sequence:
    1. Capture - External sources, user input, hooks
    2. Organize - PARA routing, drift detection, auto-tagging
    3. Distill - Progressive summarization L1→L4
    4. Express - Generate outputs from atomic notes
    5. Review - Dashboard generation (via second-brain-pipeline)
    
    Supports scheduled runs and manual triggers.
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self._vault_path = Path(self.config.vault_path)
        
        # Initialize stage engines
        self.capture_engine = CaptureEngine(self.config.capture)
        self.organize_engine = OrganizeEngine(self.config.organize)
        self.distill_engine = DistillEngine(self.config.distill)
        self.express_engine = ExpressEngine(self.config.express)
        
        # Scheduler
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._last_run: Optional[PipelineRunResult] = None
        
        # Setup schedules
        self._setup_schedules()
    
    def _setup_schedules(self):
        """Setup cron-like schedules using schedule library."""
        sched = self.config.schedule
        
        # Capture external sources every 30 min
        schedule.every(30).minutes.do(self._run_capture_external)
        
        # Organize inbox hourly
        schedule.every().hour.do(self._run_organize_inbox)
        
        # Detect drift daily at 9am
        schedule.every().day.at("09:00").do(self._run_detect_drift)
        
        # Distill pending daily at 2am
        schedule.every().day.at("02:00").do(self._run_distill_pending)
        
        # Express scheduled weekly Monday 6am
        schedule.every().monday.at("06:00").do(self._run_express_scheduled)
        
        # Review weekly Monday 8am
        schedule.every().monday.at("08:00").do(self._run_review_weekly)
        
        # Review monthly 1st at 9am - use day 1 approach
        schedule.every().day.at("09:00").do(self._run_review_monthly_check)
    
    def _run_capture_external(self):
        """Scheduled capture from external sources."""
        try:
            self.capture_engine.scan_external_sources(dry_run=False)
        except Exception as e:
            print(f"[Pipeline] Capture external error: {e}")
    
    def _run_organize_inbox(self):
        """Scheduled inbox organization."""
        try:
            self.organize_engine.process_inbox(auto=True, dry_run=False)
        except Exception as e:
            print(f"[Pipeline] Organize inbox error: {e}")
    
    def _run_detect_drift(self):
        """Scheduled drift detection."""
        try:
            self.organize_engine.detect_drift(dry_run=False)
        except Exception as e:
            print(f"[Pipeline] Drift detection error: {e}")
    
    def _run_distill_pending(self):
        """Scheduled distillation of pending notes."""
        try:
            pending = self.distill_engine.get_pending_distill(max_layer=3)
            if pending:
                self.distill_engine.batch_distill(pending, target_layer=4)
        except Exception as e:
            print(f"[Pipeline] Distill pending error: {e}")
    
    def _run_express_scheduled(self):
        """Scheduled express generation for active topics."""
        # This would generate outputs for active projects/topics
        # For now, placeholder
        pass
    
    def _run_review_weekly(self):
        """Scheduled weekly review."""
        # Would integrate with second-brain-pipeline review
        pass
    
    def _run_review_monthly(self):
        """Scheduled monthly review."""
        # Would integrate with second-brain-pipeline review
        pass
    
    def _run_review_monthly_check(self):
        """Check if it's the 1st of the month and run monthly review."""
        from datetime import datetime
        if datetime.now().day == 1:
            self._run_review_monthly()
    
    def start_scheduler(self):
        """Start the background scheduler thread."""
        if self._running:
            return
        
        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
    
    def stop_scheduler(self):
        """Stop the background scheduler."""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    # ============================================================
    # MANUAL TRIGGERS
    # ============================================================
    
    def run_full_pipeline(
        self,
        capture_external: bool = True,
        organize: bool = True,
        distill: bool = True,
        express_topics: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> PipelineRunResult:
        """
        Run complete pipeline manually.
        
        Args:
            capture_external: Scan external sources
            organize: Process inbox
            distill: Distill pending notes
            express_topics: Topics to generate outputs for
            dry_run: Don't write changes
            
        Returns:
            PipelineRunResult with all stage results
        """
        start_time = time.time()
        result = PipelineRunResult(timestamp=datetime.now())
        
        try:
            # Stage 1: Capture
            if capture_external:
                captured = self.capture_engine.scan_external_sources(dry_run=dry_run)
                result.capture_results = captured
            
            # Stage 2: Organize
            if organize:
                org_result = self.organize_engine.process_inbox(auto=True, dry_run=dry_run)
                result.organize_results = org_result
                
                # Also detect drift
                drift_result = self.organize_engine.detect_drift(dry_run=dry_run)
                if drift_result.drifted:
                    result.errors.append(f"Drift detected: {len(drift_result.drifted)} files")
            
            # Stage 3: Distill
            if distill:
                pending = self.distill_engine.get_pending_distill(max_layer=3)
                if pending:
                    distill_results = self.distill_engine.batch_distill(
                        pending, target_layer=4, 
                        auto_link=True, auto_tag=True
                    )
                    result.distill_results = distill_results
            
            # Stage 4: Express
            if express_topics:
                for topic in express_topics:
                    # Generate article for each topic
                    expr_result = self.express_engine.generate(
                        topic, "article", max_sources=10
                    )
                    result.express_results.append(expr_result)
        
        except Exception as e:
            result.errors.append(f"Pipeline error: {str(e)}")
        
        result.duration_seconds = time.time() - start_time
        self._last_run = result
        
        return result
    
    def capture_user_input(
        self,
        content: str,
        type_: CaptureType = CaptureType.FLEETING,
        context: str = "geral",
        tags: Optional[List[str]] = None
    ) -> CapturedItem:
        """Capture direct user input."""
        return self.capture_engine.capture(
            content=content,
            type_=type_,
            context=context,
            source=CaptureSource.USER_INPUT,
            tags=tags
        )
    
    def organize_now(self, dry_run: bool = False) -> OrganizeResult:
        """Manually trigger inbox organization."""
        return self.organize_engine.process_inbox(auto=True, dry_run=dry_run)
    
    def distill_now(self, source_path: str, target_layer: int = 4) -> DistillResult:
        """Manually trigger distillation of a specific note."""
        return self.distill_engine.distill_note(source_path, target_layer)
    
    def express_now(
        self,
        topic: str,
        output_type: str = "article",
        sources: Optional[List[str]] = None
    ) -> ExpressResult:
        """Manually trigger output generation."""
        return self.express_engine.generate(topic, output_type, sources)
    
    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status."""
        return {
            "running": self._running,
            "last_run": self._last_run.timestamp.isoformat() if self._last_run else None,
            "last_run_duration": self._last_run.duration_seconds if self._last_run else None,
            "last_run_errors": len(self._last_run.errors) if self._last_run else 0,
            "vault_path": self.config.vault_path,
            "schedules": len(schedule.jobs)
        }
    
    def get_pending_work(self) -> Dict[str, Any]:
        """Get count of pending work at each stage."""
        # Count inbox files
        inbox_count = 0
        for inbox_rel in self.config.organize.inbox_paths:
            inbox_path = self._vault_path / inbox_rel
            if inbox_path.exists():
                inbox_count += len(list(inbox_path.rglob("*.md")))
        
        # Count pending distill
        pending_distill = len(self.distill_engine.get_pending_distill(max_layer=3))
        
        # Count drift
        drift_result = self.organize_engine.detect_drift(dry_run=True)
        drift_count = len(drift_result.drifted)
        
        return {
            "inbox_items": inbox_count,
            "pending_distill": pending_distill,
            "drift_files": drift_count
        }


def create_pipeline_orchestrator(config: Optional[PipelineConfig] = None) -> PipelineOrchestrator:
    """Factory function to create pipeline orchestrator."""
    return PipelineOrchestrator(config)


__all__ = [
    "PipelineOrchestrator",
    "PipelineConfig",
    "PipelineRunResult",
    "create_pipeline_orchestrator"
]