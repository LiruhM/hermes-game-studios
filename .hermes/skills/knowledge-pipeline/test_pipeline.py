"""
Knowledge Compounding Pipeline v1.0 — Test Suite
Integration tests for the Knowledge Pipeline components.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from knowledge_pipeline.capture import (
    CaptureEngine, CaptureConfig, CapturedItem, CaptureSource, CaptureType,
    create_capture_engine
)
from knowledge_pipeline.organize import (
    OrganizeEngine, OrganizeConfig, OrganizeResult, PARADestination,
    create_organize_engine
)
from knowledge_pipeline.distill import (
    DistillEngine, DistillConfig, DistillResult, DistillLayer, LayerConfig,
    create_distill_engine
)
from knowledge_pipeline.express import (
    ExpressEngine, ExpressConfig, ExpressResult, OutputType, OutputConfig,
    create_express_engine
)
from knowledge_pipeline.orchestrator import (
    PipelineOrchestrator, PipelineConfig, PipelineRunResult,
    create_pipeline_orchestrator
)
from knowledge_pipeline.cron import (
    CronScheduler, CronJob,
    create_cron_scheduler
)


# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture
def temp_vault():
    """Create temporary vault structure for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        
        # Create PARA structure
        (vault_path / "00-Inbox").mkdir(parents=True)
        (vault_path / "50-Meta/00-Inbox").mkdir(parents=True)
        (vault_path / "10-Projetos").mkdir(parents=True)
        (vault_path / "20-Areas").mkdir(parents=True)
        (vault_path / "30-Recursos").mkdir(parents=True)
        (vault_path / "40-Arquivo").mkdir(parents=True)
        (vault_path / "90-Sistema").mkdir(parents=True)
        
        # Create templates dir
        (vault_path / "30-Recursos/_taxonomy").mkdir(parents=True)
        (vault_path / "30-Recursos/_taxonomy/tags.md").write_text("# Tag Taxonomy\n\n#ideia\n#tarefa\n#token-opt")
        
        # Create atomic notes folders
        (vault_path / "30-Recursos/Atomic-Notes").mkdir(parents=True)
        (vault_path / "30-Recursos/Literature-Notes").mkdir(parents=True)
        (vault_path / "30-Recursos/Resource-Notes").mkdir(parents=True)
        (vault_path / "30-Recursos/Highlights").mkdir(parents=True)
        
        yield str(vault_path)


@pytest.fixture
def capture_config(temp_vault):
    """Create capture config for tests."""
    return CaptureConfig(
        vault_path=temp_vault,
        inbox_paths=["00-Inbox", "50-Meta/00-Inbox"],
        external_scan_paths=[],
        template="[[{{date}}]] | #{{type}} #{{context}}\n{{content}}\n#revisar"
    )


@pytest.fixture
def organize_config(temp_vault):
    """Create organize config for tests."""
    return OrganizeConfig(
        vault_path=temp_vault,
        para_mapping={
            "projeto": "10-Projetos",
            "area": "20-Areas",
            "recurso": "30-Recursos",
            "arquivo": "40-Arquivo",
            "meta": "50-Meta",
            "sistema": "90-Sistema"
        },
        routing_rules={
            "ideia": "projects",
            "tarefa": "projects",
            "insight": "resources",
            "referencia": "resources"
        }
    )


# ============================================================
# CAPTURE TESTS
# ============================================================

class TestCaptureEngine:
    """Tests for CaptureEngine."""
    
    def test_capture_user_input(self, capture_config):
        """Test capturing user input."""
        engine = CaptureEngine(capture_config)
        
        item = engine.capture(
            content="Teste de captura",
            type_=CaptureType.IDEA,
            context="teste",
            source=CaptureSource.USER_INPUT
        )
        
        assert item.content == "Teste de captura"
        assert item.type == CaptureType.IDEA
        assert item.context == "teste"
        assert item.source == CaptureSource.USER_INPUT
        assert item.id.startswith("cap-")
        assert item.vault_path is not None
        
        # Check file was created
        vault_file = Path(capture_config.vault_path) / item.vault_path
        assert vault_file.exists()
    
    def test_capture_deduplication(self, capture_config):
        """Test content deduplication."""
        engine = CaptureEngine(capture_config)
        
        # Capture same content twice
        item1 = engine.capture("Conteúdo duplicado", CaptureType.IDEA, "teste")
        item2 = engine.capture("Conteúdo duplicado", CaptureType.IDEA, "teste")
        
        assert item1.id != "duplicate"
        assert item2.id == "duplicate"
        assert item2.metadata.get("duplicate") == True
    
    def test_capture_from_external(self, capture_config):
        """Test capturing from external file."""
        # Create a test file
        external_dir = Path(capture_config.vault_path) / "external_test"
        external_dir.mkdir()
        test_file = external_dir / "test.md"
        test_file.write_text("# External Note\n\nConteúdo do arquivo externo.")
        
        config = CaptureConfig(
            vault_path=capture_config.vault_path,
            external_scan_paths=[str(external_dir)]
        )
        engine = CaptureEngine(config)
        
        captured = engine.scan_external_sources(dry_run=False)
        
        assert len(captured) >= 1
        assert any("External Note" in item.content for item in captured)


# ============================================================
# ORGANIZE TESTS
# ============================================================

class TestOrganizeEngine:
    """Tests for OrganizeEngine."""
    
    def test_determine_destination(self, organize_config):
        """Test PARA destination determination."""
        engine = OrganizeEngine(organize_config)
        
        # Test various types
        assert engine._get_destination("ideia", "projeto", "") == "projects"
        assert engine._get_destination("tarefa", "sprint", "") == "projects"
        assert engine._get_destination("insight", "aprendizado", "") == "resources"
        assert engine._get_destination("referencia", "docs", "") == "resources"
        assert engine._get_destination("fleeting", "random", "") == "inbox"
    
    def test_parse_frontmatter(self, organize_config, temp_vault):
        """Test frontmatter parsing."""
        engine = OrganizeEngine(organize_config)
        
        # Create test file with frontmatter
        test_file = Path(temp_vault) / "00-Inbox" / "test.md"
        test_file.write_text("""---
id: test-123
type: ideia
context: teste
tags: ["#teste"]
---
# Test Note

Content here.""")
        
        frontmatter, body = engine._parse_frontmatter(test_file)
        
        assert frontmatter["id"] == "test-123"
        assert frontmatter["type"] == "ideia"
        assert frontmatter["context"] == "teste"
        assert "#teste" in frontmatter["tags"]
        assert "Content here" in body
    
    def test_auto_tag(self, organize_config, temp_vault):
        """Test auto-tagging."""
        engine = OrganizeEngine(organize_config)
        
        # Create test file with Python content
        test_file = Path(temp_vault) / "00-Inbox" / "python-note.md"
        test_file.write_text("""---
id: test-456
type: referencia
context: python
---
# Python Note

def hello():
    print("Hello World")

import json
response = requests.get("https://api.example.com")""")
        
        tags = engine.auto_tag(test_file)
        
        assert "#python" in tags
        assert "#api" in tags or "#database" in tags


# ============================================================
# DISTILL TESTS
# ============================================================

class TestDistillEngine:
    """Tests for DistillEngine."""
    
    def test_load_template(self, temp_vault):
        """Test template loading."""
        config = DistillConfig(vault_path=temp_vault)
        engine = DistillEngine(config)
        
        template = engine._load_template(1)
        assert "Highlights" in template
        assert "{{content}}" in template
        
        template = engine._load_template(4)
        assert "Atomic Note" in template
        assert "{{links_formatted}}" in template
    
    def test_suggest_tags(self, temp_vault):
        """Test tag suggestion."""
        config = DistillConfig(vault_path=temp_vault)
        engine = DistillEngine(config)
        
        content = "This is about python and llm token optimization with rag"
        tags = engine._suggest_tags(content, 4)
        
        assert "#atomic" in tags
        assert "#python" in tags
        assert "#llm" in tags
        assert "#rag" in tags or "#token-opt" in tags


# ============================================================
# EXPRESS TESTS
# ============================================================

class TestExpressEngine:
    """Tests for ExpressEngine."""
    
    def test_load_template(self, temp_vault):
        """Test template loading."""
        config = ExpressConfig(vault_path=temp_vault)
        engine = ExpressEngine(config)
        
        template = engine._load_template("article")
        assert "Introduction" in template
        assert "{{intro}}" in template
        
        template = engine._load_template("report")
        assert "Executive Summary" in template
        assert "{{executive_summary}}" in template
    
    def test_format_references_wiki(self, temp_vault):
        """Test wiki citation formatting."""
        config = ExpressConfig(vault_path=temp_vault, citation_style="wiki")
        engine = ExpressEngine(config)
        
        citations = [
            {"path": "30-Recursos/Atomic-Notes/note1.md", "title": "Note 1", "layer": "4"},
            {"path": "30-Recursos/Atomic-Notes/note2.md", "title": "Note 2", "layer": "4"}
        ]
        
        refs = engine._format_references(citations)
        
        assert "[[30-Recursos/Atomic-Notes/note1.md|Note 1]] (Layer 4)" in refs
        assert "[[30-Recursos/Atomic-Notes/note2.md|Note 2]] (Layer 4)" in refs
    
    def test_format_references_markdown(self, temp_vault):
        """Test markdown citation formatting."""
        config = ExpressConfig(vault_path=temp_vault, citation_style="markdown")
        engine = ExpressEngine(config)
        
        citations = [
            {"path": "note1.md", "title": "Note 1", "layer": "4"}
        ]
        
        refs = engine._format_references(citations)
        
        assert "- [Note 1](note1.md)" in refs


# ============================================================
# ORCHESTRATOR TESTS
# ============================================================

class TestPipelineOrchestrator:
    """Tests for PipelineOrchestrator."""
    
    def test_create_pipeline(self, temp_vault):
        """Test pipeline creation."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        assert pipeline.capture_engine is not None
        assert pipeline.organize_engine is not None
        assert pipeline.distill_engine is not None
        assert pipeline.express_engine is not None
    
    def test_capture_user_input(self, temp_vault):
        """Test user input capture."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        item = pipeline.capture_user_input(
            content="Teste pipeline",
            type_=CaptureType.IDEA,
            context="pipeline"
        )
        
        assert item.content == "Teste pipeline"
        assert item.type == CaptureType.IDEA
    
    def test_get_status(self, temp_vault):
        """Test status retrieval."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        status = pipeline.get_status()
        
        assert "running" in status
        assert "vault_path" in status
        assert status["vault_path"] == temp_vault
    
    def test_get_pending_work(self, temp_vault):
        """Test pending work count."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        pending = pipeline.get_pending_work()
        
        assert "inbox_items" in pending
        assert "pending_distill" in pending
        assert "drift_files" in pending


# ============================================================
# CRON TESTS
# ============================================================

class TestCronScheduler:
    """Tests for CronScheduler."""
    
    def test_create_scheduler(self, temp_vault):
        """Test scheduler creation."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        scheduler = CronScheduler(pipeline)
        
        assert "capture_external" in scheduler._jobs
        assert "organize_inbox" in scheduler._jobs
        assert "detect_drift" in scheduler._jobs
        assert "distill_pending" in scheduler._jobs
    
    def test_job_status(self, temp_vault):
        """Test job status retrieval."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        scheduler = CronScheduler(pipeline)
        
        status = scheduler.get_job_status("capture_external")
        
        assert status is not None
        assert status["name"] == "capture_external"
        assert status["enabled"] == True
        assert "schedule" in status
    
    def test_get_all_status(self, temp_vault):
        """Test all jobs status."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        scheduler = CronScheduler(pipeline)
        
        all_status = scheduler.get_all_status()
        
        assert len(all_status) >= 7  # At least 7 default jobs
        assert "capture_external" in all_status
        assert "organize_inbox" in all_status


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestIntegration:
    """Integration tests (marked for manual running)."""
    
    @pytest.mark.integration
    def test_full_pipeline_run(self, temp_vault):
        """Test full pipeline run."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        # Run pipeline
        result = pipeline.run_full_pipeline(
            capture_external=False,
            organize=True,
            distill=False,
            express_topics=None,
            dry_run=True
        )
        
        assert result.timestamp is not None
        assert result.duration_seconds >= 0
        assert isinstance(result.errors, list)
    
    @pytest.mark.integration
    def test_capture_organize_distill_flow(self, temp_vault):
        """Test capture -> organize -> distill flow."""
        config = PipelineConfig(vault_path=temp_vault)
        pipeline = PipelineOrchestrator(config)
        
        # Capture
        item = pipeline.capture_user_input(
            "Ideia para teste de integração",
            CaptureType.IDEA,
            "integracao"
        )
        assert item.success if hasattr(item, 'success') else True
        
        # Organize (dry run)
        org_result = pipeline.organize_now(dry_run=True)
        assert isinstance(org_result, OrganizeResult)
        
        # Check pending distill
        pending = pipeline.distill_engine.get_pending_distill()
        assert isinstance(pending, list)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x", "-m", "not integration"])