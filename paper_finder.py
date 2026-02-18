#!/usr/bin/env python3
"""
Paper Finder - AI-Powered Academic Paper Search Tool

An intelligent tool for finding academic papers with:
- Multi-source search (Semantic Scholar, arXiv)
- AI-powered semantic ranking using OpenAI embeddings
- Multi-dimensional filtering (year, citations, fields, etc.)
- Direct Zotero integration
"""
import sys
import json
import logging
from typing import Optional, List

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

from config import config
from paper_sources import PaperAggregator, Paper
from ai_search import AISearchEngine, MultiDimensionalFilter
from zotero_client import ZoteroClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

console = Console()


def display_papers(papers: List[Paper], show_abstract: bool = False):
    """Display papers in a rich table"""
    table = Table(title="Found Papers", show_lines=True)
    
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="bold cyan", max_width=50)
    table.add_column("Authors", max_width=30)
    table.add_column("Year", justify="center", width=6)
    table.add_column("Citations", justify="right", width=8)
    table.add_column("Source", width=10)
    table.add_column("Score", justify="right", width=6)
    
    for i, paper in enumerate(papers, 1):
        authors = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors += f" +{len(paper.authors) - 3}"
        
        score = f"{paper.relevance_score:.2f}" if paper.relevance_score else "-"
        citations = str(paper.citations) if paper.citations else "-"
        
        table.add_row(
            str(i),
            paper.title[:50] + ("..." if len(paper.title) > 50 else ""),
            authors,
            str(paper.year) if paper.year else "-",
            citations,
            paper.source,
            score,
        )
    
    console.print(table)
    
    if show_abstract:
        for i, paper in enumerate(papers, 1):
            console.print(f"\n[bold cyan]{i}. {paper.title}[/bold cyan]")
            console.print(f"[dim]{paper.abstract[:500]}...[/dim]" if paper.abstract else "[dim]No abstract[/dim]")


def display_paper_detail(paper: Paper):
    """Display detailed information about a paper"""
    content = f"""**{paper.title}**

**Authors:** {', '.join(paper.authors[:10])}{"..." if len(paper.authors) > 10 else ""}

**Year:** {paper.year or "N/A"}

**Citations:** {paper.citations or "N/A"}

**Venue:** {paper.venue or "N/A"}

**Fields:** {', '.join(paper.fields) if paper.fields else "N/A"}

**DOI:** {paper.doi or "N/A"}

**arXiv ID:** {paper.arxiv_id or "N/A"}

**URL:** {paper.url or "N/A"}

**PDF:** {paper.pdf_url or "N/A"}

---

**Abstract:**

{paper.abstract or "No abstract available"}
"""
    console.print(Panel(Markdown(content), title="Paper Details"))


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    Paper Finder - AI-Powered Academic Paper Search
    
    Find papers that match your research interests with precision.
    Uses semantic search and pushes directly to Zotero.
    """
    pass


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=20, help="Maximum number of results")
@click.option("--year-start", "-ys", type=int, help="Filter papers from this year")
@click.option("--year-end", "-ye", type=int, help="Filter papers up to this year")
@click.option("--min-citations", "-c", default=0, help="Minimum citation count")
@click.option("--fields", "-f", multiple=True, help="Fields of study filter")
@click.option("--sources", "-s", multiple=True, default=["semantic_scholar", "arxiv"],
              help="Sources to search: semantic_scholar, arxiv")
@click.option("--ai-rank/--no-ai-rank", default=True, help="Use AI to rank results")
@click.option("--ai-refine/--no-ai-refine", default=False, help="Use AI to refine query")
@click.option("--pdf-only", is_flag=True, help="Only papers with available PDF")
@click.option("--output", "-o", type=click.Path(), help="Save results to JSON file")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def search(
    query: str,
    limit: int,
    year_start: Optional[int],
    year_end: Optional[int],
    min_citations: int,
    fields: tuple,
    sources: tuple,
    ai_rank: bool,
    ai_refine: bool,
    pdf_only: bool,
    output: Optional[str],
    verbose: bool,
):
    """
    Search for academic papers
    
    Example:
        paper-finder search "transformer attention mechanisms in NLP"
        paper-finder search "COVID-19 vaccine efficacy" --year-start 2022 --min-citations 50
    """
    console.print(Panel(f"[bold]Searching for:[/bold] {query}", title="Paper Finder"))
    
    # Initialize components
    aggregator = PaperAggregator()
    ai_engine = AISearchEngine()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Optionally refine query with AI
        search_query = query
        if ai_refine and config.has_openai():
            task = progress.add_task("Refining query with AI...", total=None)
            search_query = ai_engine.refine_search_query(query)
            progress.remove_task(task)
            console.print(f"[dim]Refined query: {search_query}[/dim]")
        
        # Search across sources
        task = progress.add_task("Searching papers...", total=None)
        papers = aggregator.search_all(
            search_query,
            limit=limit * 2,  # Get more for filtering
            sources=list(sources),
            year_start=year_start,
            year_end=year_end,
            min_citations=min_citations,
            fields_of_study=list(fields) if fields else None,
        )
        progress.remove_task(task)
        
        if not papers:
            console.print("[yellow]No papers found. Try different search terms.[/yellow]")
            return
        
        console.print(f"[green]Found {len(papers)} papers[/green]")
        
        # Apply multi-dimensional filtering
        mdf = MultiDimensionalFilter(ai_engine)
        papers = mdf.filter(
            papers,
            year_range=(year_start, year_end) if year_start or year_end else None,
            min_citations=min_citations,
            fields=list(fields) if fields else None,
            has_pdf=pdf_only,
        )
        
        # AI-powered ranking
        if ai_rank:
            task = progress.add_task("AI ranking papers...", total=None)
            papers = ai_engine.rank_papers_by_query(papers, query, top_k=limit)
            progress.remove_task(task)
        else:
            papers = papers[:limit]
    
    # Display results
    display_papers(papers, show_abstract=verbose)
    
    # Save to file if requested
    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in papers], f, indent=2, ensure_ascii=False)
        console.print(f"[green]Results saved to {output}[/green]")
    
    # Store in session for push command
    _store_session_papers(papers)
    
    console.print("\n[dim]Use 'paper-finder push' to add papers to Zotero[/dim]")


@cli.command()
@click.option("--indices", "-i", help="Paper indices to push (e.g., '1,2,3' or '1-5' or 'all')")
@click.option("--collection", "-c", help="Zotero collection name (creates if doesn't exist)")
@click.option("--no-duplicates", is_flag=True, help="Skip papers already in library")
@click.option("--attach-pdf/--no-pdf", default=True, help="Attach PDFs when available")
def push(
    indices: Optional[str],
    collection: Optional[str],
    no_duplicates: bool,
    attach_pdf: bool,
):
    """
    Push found papers to Zotero library
    
    Example:
        paper-finder push --indices 1,2,3 --collection "ML Papers"
        paper-finder push --indices all --no-duplicates
    """
    # Load papers from session
    papers = _load_session_papers()
    
    if not papers:
        console.print("[yellow]No papers in session. Run 'search' first.[/yellow]")
        return
    
    # Parse indices
    if not indices:
        display_papers(papers)
        indices = Prompt.ask(
            "Enter paper numbers to push",
            default="all"
        )
    
    selected_papers = _parse_indices(papers, indices)
    
    if not selected_papers:
        console.print("[yellow]No valid papers selected.[/yellow]")
        return
    
    console.print(f"[bold]Selected {len(selected_papers)} papers to push[/bold]")
    
    # Initialize Zotero client
    zotero = ZoteroClient()
    
    if not zotero.is_available():
        console.print("[red]Zotero not configured. Please set up .env file.[/red]")
        console.print("[dim]Required: ZOTERO_API_KEY and ZOTERO_USER_ID[/dim]")
        return
    
    # Check for duplicates if requested
    if no_duplicates:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Checking for duplicates...", total=None)
            selected_papers = zotero.check_duplicates(selected_papers)
            progress.remove_task(task)
        console.print(f"[dim]{len(selected_papers)} new papers to add[/dim]")
    
    if not selected_papers:
        console.print("[yellow]All papers already in library.[/yellow]")
        return
    
    # Confirm before pushing
    if not Confirm.ask(f"Push {len(selected_papers)} papers to Zotero?"):
        return
    
    # Push to Zotero
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Pushing to Zotero...", total=None)
        result = zotero.add_papers(
            selected_papers,
            attach_pdfs=attach_pdf,
            create_collection_name=collection,
        )
        progress.remove_task(task)
    
    # Display results
    console.print(f"[green]Successfully added {result['added']} papers[/green]")
    if result["failed"]:
        console.print(f"[yellow]Failed to add {result['failed']} papers[/yellow]")


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=30, help="Number of papers to analyze")
def analyze(query: str, limit: int):
    """
    Analyze research landscape and identify gaps
    
    Example:
        paper-finder analyze "quantum machine learning applications"
    """
    console.print(Panel(f"[bold]Analyzing:[/bold] {query}", title="Research Analysis"))
    
    if not config.has_openai():
        console.print("[yellow]OpenAI not configured. Analysis requires AI.[/yellow]")
        return
    
    aggregator = PaperAggregator()
    ai_engine = AISearchEngine()
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Gathering papers...", total=None)
        papers = aggregator.search_all(query, limit=limit)
        progress.remove_task(task)
        
        if not papers:
            console.print("[yellow]No papers found for analysis.[/yellow]")
            return
        
        task = progress.add_task("Analyzing research landscape...", total=None)
        analysis = ai_engine.analyze_research_gap(papers, query)
        progress.remove_task(task)
    
    console.print(Panel(Markdown(analysis), title="Research Analysis"))


@cli.command()
def collections():
    """List Zotero collections"""
    zotero = ZoteroClient()
    
    if not zotero.is_available():
        console.print("[red]Zotero not configured.[/red]")
        return
    
    colls = zotero.get_collections()
    
    if not colls:
        console.print("[yellow]No collections found.[/yellow]")
        return
    
    table = Table(title="Zotero Collections")
    table.add_column("Key", style="dim")
    table.add_column("Name", style="bold")
    
    for c in colls:
        table.add_row(c["key"], c["name"])
    
    console.print(table)


@cli.command()
def status():
    """Check configuration status"""
    table = Table(title="Configuration Status")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details", style="dim")
    
    # OpenAI
    if config.has_openai():
        table.add_row("OpenAI", "[green]Configured[/green]", "AI-powered search enabled")
    else:
        table.add_row("OpenAI", "[yellow]Not configured[/yellow]", "Set OPENAI_API_KEY")
    
    # Zotero
    if config.has_zotero():
        table.add_row("Zotero", "[green]Configured[/green]", f"User ID: {config.zotero_user_id}")
    else:
        table.add_row("Zotero", "[yellow]Not configured[/yellow]", "Set ZOTERO_API_KEY and ZOTERO_USER_ID")
    
    # Semantic Scholar
    if config.semantic_scholar_api_key:
        table.add_row("Semantic Scholar", "[green]API Key Set[/green]", "Higher rate limits")
    else:
        table.add_row("Semantic Scholar", "[blue]Public API[/blue]", "Rate limited")
    
    console.print(table)


# Session management for storing papers between commands
SESSION_FILE = ".paper_finder_session.json"


def _store_session_papers(papers: List[Paper]):
    """Store papers in session file"""
    import os
    with open(os.path.join(os.path.dirname(__file__), SESSION_FILE), "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in papers], f, ensure_ascii=False)


def _load_session_papers() -> List[Paper]:
    """Load papers from session file"""
    import os
    session_path = os.path.join(os.path.dirname(__file__), SESSION_FILE)
    
    if not os.path.exists(session_path):
        return []
    
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return [
            Paper(
                title=p["title"],
                authors=p["authors"],
                abstract=p["abstract"],
                year=p.get("year"),
                doi=p.get("doi"),
                url=p.get("url"),
                pdf_url=p.get("pdf_url"),
                source=p.get("source", ""),
                citations=p.get("citations", 0),
                venue=p.get("venue"),
                arxiv_id=p.get("arxiv_id"),
                fields=p.get("fields", []),
                keywords=p.get("keywords", []),
                relevance_score=p.get("relevance_score", 0),
            )
            for p in data
        ]
    except Exception:
        return []


def _parse_indices(papers: List[Paper], indices_str: str) -> List[Paper]:
    """Parse index string like '1,2,3' or '1-5' or 'all'"""
    if indices_str.lower() == "all":
        return papers
    
    selected = set()
    
    for part in indices_str.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                selected.update(range(start, end + 1))
            except ValueError:
                continue
        else:
            try:
                selected.add(int(part))
            except ValueError:
                continue
    
    return [papers[i - 1] for i in sorted(selected) if 1 <= i <= len(papers)]


if __name__ == "__main__":
    cli()
