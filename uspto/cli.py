"""CLI entry point for USPTO patent search."""

import json
import logging

import click
from rich.console import Console
from rich.table import Table

from uspto.api import USPTOClient

console = Console()


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--no-cache", is_flag=True, help="Disable response caching")
@click.pass_context
def main(ctx, debug, no_cache):
    """USPTO CLI — Patent search and intelligence tool."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)
    ctx.ensure_object(dict)
    ctx.obj["client"] = USPTOClient(use_cache=not no_cache)


@main.command()
@click.argument("query")
@click.option("--rows", "-n", default=10, help="Number of results")
@click.option("--start", "-s", default=0, help="Start offset")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def search(ctx, query, rows, start, json_output):
    """Search patents by keyword."""
    client = ctx.obj["client"]
    result = client.search_patents(query, start=start, rows=rows)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    _render_results(result)


@main.command()
@click.argument("patent_number")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def lookup(ctx, patent_number, json_output):
    """Look up a specific patent by number."""
    client = ctx.obj["client"]
    result = client.get_patent(patent_number)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    _render_results(result)


@main.command()
@click.argument("query")
@click.option("--rows", "-n", default=10, help="Number of results")
@click.option("--page", "-p", default=1, help="Page number")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def fulltext(ctx, query, rows, page, json_output):
    """Full-text patent search via PatentsView API."""
    client = ctx.obj["client"]
    result = client.search_patentsview(query, per_page=rows, page=page)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    patents = result.get("patents", [])
    if not patents:
        console.print("[yellow]No patents found.[/yellow]")
        return

    table = Table(title=f"PatentsView: '{query}'", show_lines=True)
    table.add_column("Number", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Date", style="green", no_wrap=True)
    table.add_column("Assignee", style="yellow")

    for p in patents:
        table.add_row(
            p.get("patent_number", "—"),
            p.get("patent_title", "—"),
            p.get("patent_date", "—"),
            p.get("assignee_organization", "—") if isinstance(p.get("assignee_organization"), str)
            else (p["assignee_organization"][0] if isinstance(p.get("assignee_organization"), list) and p["assignee_organization"] else "—"),
        )

    console.print(table)
    total = result.get("total_patent_count", "?")
    console.print(f"\n[dim]Total: {total} patents[/dim]")


@main.command()
@click.pass_context
def clear_cache(ctx):
    """Clear the local response cache."""
    from uspto.cache import PatentCache
    cache = PatentCache()
    count = cache.clear()
    console.print(f"[green]Cleared {count} cached responses.[/green]")


def _render_results(result):
    """Render USPTO API search results as a rich table."""
    results = result.get("response", {}).get("docs", [])
    if not results:
        # Try alternate response structures
        if isinstance(result, list):
            results = result
        else:
            console.print("[yellow]No results found.[/yellow]")
            return

    table = Table(title="USPTO Patent Search Results", show_lines=True)
    table.add_column("App #", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Date", style="green", no_wrap=True)
    table.add_column("Assignee", style="yellow")

    for doc in results:
        table.add_row(
            doc.get("applId", doc.get("patentNumber", "—")),
            doc.get("inventionTitle", doc.get("title", "—")),
            doc.get("filingDate", doc.get("grantDate", "—")),
            doc.get("applicantName", doc.get("assignee", "—")),
        )

    console.print(table)
    total = result.get("response", {}).get("numFound", len(results))
    console.print(f"\n[dim]Total: {total} results[/dim]")


if __name__ == "__main__":
    main()
