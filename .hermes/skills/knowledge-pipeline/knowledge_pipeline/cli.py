"""
Knowledge Compounding Pipeline v1.0 — CLI Commands
Command-line interface for the pipeline.
"""

import sys
import click
from pathlib import Path
from typing import Optional, List

from knowledge_pipeline import (
    PipelineOrchestrator, PipelineConfig,
    CaptureEngine, CaptureConfig, CaptureType, CaptureSource,
    OrganizeEngine, OrganizeConfig,
    DistillEngine, DistillConfig,
    ExpressEngine, ExpressConfig,
    CronScheduler,
    create_pipeline_orchestrator, create_capture_engine,
    create_organize_engine, create_distill_engine,
    create_express_engine, create_cron_scheduler
)


def load_config(config_path: Optional[str] = None) -> PipelineConfig:
    """Load pipeline configuration."""
    if config_path:
        import yaml
        from knowledge_pipeline.capture import CaptureConfig
        from knowledge_pipeline.organize import OrganizeConfig
        from knowledge_pipeline.distill import DistillConfig
        from knowledge_pipeline.express import ExpressConfig
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if 'knowledge_pipeline' in data:
                data = data['knowledge_pipeline']
            # Convert nested dicts to proper config objects
            if 'capture' in data and isinstance(data['capture'], dict):
                data['capture'] = CaptureConfig(**data['capture'])
            if 'organize' in data and isinstance(data['organize'], dict):
                data['organize'] = OrganizeConfig(**data['organize'])
            if 'distill' in data and isinstance(data['distill'], dict):
                data['distill'] = DistillConfig(**data['distill'])
            if 'express' in data and isinstance(data['express'], dict):
                data['express'] = ExpressConfig(**data['express'])
            return PipelineConfig(**data)
    return PipelineConfig()


@click.group()
@click.option('--config', '-c', help='Path to config.yaml')
@click.option('--vault', '-v', help='Vault path (overrides config)')
@click.pass_context
def cli(ctx, config, vault):
    """Knowledge Compounding Pipeline — Capture → Organize → Distill → Express → Review"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = load_config(config)
    if vault:
        ctx.obj['config'].vault_path = vault


@cli.command()
@click.argument('content')
@click.option('--type', '-t', 'type_', type=click.Choice([t.value for t in CaptureType]), default='fleeting')
@click.option('--context', '-x', default='geral')
@click.option('--tags', help='Comma-separated tags')
@click.pass_context
def capture(ctx, content, type_, context, tags):
    """Capture a new knowledge item."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    tag_list = [t.strip() for t in tags.split(',')] if tags else None
    
    item = pipeline.capture_user_input(
        content=content,
        type_=CaptureType(type_),
        context=context,
        tags=tag_list
    )
    
    click.echo(f"✅ Captured: {item.id}")
    click.echo(f"   Type: {item.type.value}")
    click.echo(f"   Context: {item.context}")
    click.echo(f"   Vault: {item.vault_path}")


@cli.command()
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--auto/--manual', default=True, help='Auto-determine destination')
@click.pass_context
def organize(ctx, dry_run, auto):
    """Process inbox and route to PARA."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    result = pipeline.organize_now(dry_run=dry_run)
    
    if dry_run:
        click.echo("🔍 DRY RUN - No changes made")
    
    click.echo(f"📁 Moved: {len(result.moved)} items")
    for move in result.moved:
        click.echo(f"   {move['source']} → {move['destination']} ({move['para_destination']})")
    
    if result.tagged:
        click.echo(f"🏷️  Tagged: {len(result.tagged)} items")
    
    if result.errors:
        click.echo(f"❌ Errors: {len(result.errors)}")
        for err in result.errors:
            click.echo(f"   {err}")


@cli.command()
@click.option('--dry-run', is_flag=True)
@click.pass_context
def drift(ctx, dry_run):
    """Detect files outside PARA structure."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    result = pipeline.organize_engine.detect_drift(dry_run=dry_run)
    
    if dry_run:
        click.echo("🔍 DRY RUN - No changes made")
    
    click.echo(f"📄 Drifted files: {len(result.drifted)}")
    for drift in result.drifted[:10]:
        click.echo(f"   {drift['file']} ({drift['size']} bytes)")
    
    if len(result.drifted) > 10:
        click.echo(f"   ... and {len(result.drifted) - 10} more")


@cli.command()
@click.argument('source_path')
@click.option('--layer', '-l', type=click.IntRange(1, 4), default=4)
@click.option('--auto-link/--no-auto-link', default=True)
@click.option('--auto-tag/--no-auto-tag', default=True)
@click.pass_context
def distill(ctx, source_path, layer, auto_link, auto_tag):
    """Distill a note to target layer (1-4)."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    result = pipeline.distill_now(source_path, target_layer=layer)
    
    if result.success:
        click.echo(f"✅ Distilled to Layer {result.layer}: {result.output_path}")
        if result.links_created:
            click.echo(f"   🔗 Links: {len(result.links_created)}")
        if result.tags_suggested:
            click.echo(f"   🏷️  Tags: {', '.join(result.tags_suggested)}")
    else:
        click.echo(f"❌ Failed: {result.error}")
        sys.exit(1)


@cli.command()
@click.argument('topic')
@click.option('--type', '-t', 'output_type', type=click.Choice(['article', 'report', 'doc', 'newsletter']), default='article')
@click.option('--sources', '-s', help='Comma-separated source note paths')
@click.option('--max-sources', '-m', default=10)
@click.pass_context
def express(ctx, topic, output_type, sources, max_sources):
    """Generate output from atomic notes."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    source_list = [s.strip() for s in sources.split(',')] if sources else None
    
    result = pipeline.express_now(topic, output_type, source_list)
    
    if result.success:
        click.echo(f"✅ Generated {output_type}: {result.output_path}")
        click.echo(f"   Sources: {len(result.sources)}")
        click.echo(f"   Citations: {len(result.citations)}")
    else:
        click.echo(f"❌ Failed: {result.error}")
        sys.exit(1)


@cli.command()
@click.option('--capture/--no-capture', default=True)
@click.option('--organize/--no-organize', default=True)
@click.option('--distill/--no-distill', default=True)
@click.option('--express-topics', '-e', multiple=True, help='Topics to generate outputs for')
@click.option('--dry-run', is_flag=True)
@click.pass_context
def run(ctx, capture, organize, distill, express_topics, dry_run):
    """Run full pipeline."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    click.echo("🚀 Running full pipeline...")
    
    result = pipeline.run_full_pipeline(
        capture_external=capture,
        organize=organize,
        distill=distill,
        express_topics=list(express_topics) if express_topics else None,
        dry_run=dry_run
    )
    
    click.echo(f"⏱️  Duration: {result.duration_seconds:.1f}s")
    click.echo(f"📥 Captured: {len(result.capture_results)}")
    if result.organize_results:
        click.echo(f"📁 Organized: {len(result.organize_results.moved)} moved")
    click.echo(f"🔬 Distilled: {len(result.distill_results)}")
    click.echo(f"📝 Expressed: {len(result.express_results)}")
    
    if result.errors:
        click.echo(f"❌ Errors: {len(result.errors)}")
        for err in result.errors:
            click.echo(f"   {err}")


@cli.command()
@click.pass_context
def status(ctx):
    """Show pipeline status."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    status = pipeline.get_status()
    pending = pipeline.get_pending_work()
    
    click.echo("📊 Pipeline Status")
    click.echo(f"   Running: {'Yes' if status['running'] else 'No'}")
    click.echo(f"   Vault: {status['vault_path']}")
    click.echo(f"   Last run: {status['last_run'] or 'Never'}")
    if status['last_run_duration']:
        click.echo(f"   Last duration: {status['last_run_duration']:.1f}s")
    
    click.echo("\n📋 Pending Work")
    click.echo(f"   Inbox items: {pending['inbox_items']}")
    click.echo(f"   Pending distill: {pending['pending_distill']}")
    click.echo(f"   Drift files: {pending['drift_files']}")


@cli.command()
@click.pass_context
def cron_start(ctx):
    """Start cron scheduler."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    click.echo("⏰ Starting cron scheduler...")
    pipeline.start_scheduler()
    click.echo("✅ Scheduler started (background)")
    click.echo("   Jobs: capture_external (30min), organize_inbox (hourly), detect_drift (daily 9am)")
    click.echo("   distill_pending (daily 2am), express_scheduled (Mon 6am), review_weekly (Mon 8am)")


@cli.command()
@click.pass_context
def cron_stop(ctx):
    """Stop cron scheduler."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    
    pipeline.stop_scheduler()
    click.echo("🛑 Scheduler stopped")


@cli.command()
@click.pass_context
def cron_status(ctx):
    """Show cron job status."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    scheduler = CronScheduler(pipeline)
    
    status = scheduler.get_all_status()
    
    click.echo("⏰ Cron Jobs")
    for name, info in status.items():
        enabled = "✅" if info['enabled'] else "❌"
        click.echo(f"   {enabled} {name}: {info['schedule']} (runs: {info['run_count']})")


@cli.command()
@click.argument('job_name')
@click.pass_context
def cron_run(ctx, job_name):
    """Run a cron job immediately."""
    pipeline = PipelineOrchestrator(ctx.obj['config'])
    scheduler = CronScheduler(pipeline)
    
    click.echo(f"▶️  Running {job_name}...")
    success = scheduler.run_job_now(job_name)
    
    if success:
        click.echo("✅ Completed")
    else:
        click.echo("❌ Failed")
        sys.exit(1)


if __name__ == '__main__':
    cli()