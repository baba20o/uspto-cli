"""CLI entry point for USPTO patent search."""

import json
import logging

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from uspto.api import USPTOClient

console = Console()


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--no-cache", is_flag=True, help="Disable response caching")
@click.option("--api-key", envvar="USPTO_KEY", default=None, help="USPTO API key (or set USPTO_KEY env)")
@click.pass_context
def main(ctx, debug, no_cache, api_key):
    """USPTO CLI — Patent search and intelligence tool.

    Uses the USPTO Open Data Portal (ODP) API.
    Requires an API key: set USPTO_KEY env var or pass --api-key.
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)
    ctx.ensure_object(dict)
    ctx.obj["client"] = USPTOClient(api_key=api_key, use_cache=not no_cache)


# ── Patent Search ────────────────────────────────────────


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--offset", "-o", default=0, help="Start offset")
@click.option("--sort", "-s", default=None, help="Sort field + order, e.g. 'applicationMetaData.filingDate desc'")
@click.option("--fields", "-f", default=None, help="Comma-separated fields to include")
@click.option("--filters", default=None, help="Filter expression, e.g. 'applicationMetaData.applicationTypeCode UTL'")
@click.option("--range-filters", default=None, help="Range filter, e.g. 'applicationMetaData.filingDate 2023-01-01:2024-01-01'")
@click.option("--facets", default=None, help="Comma-separated facet fields")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def search(ctx, query, limit, offset, sort, fields, filters, range_filters, facets, json_output):
    """Search patent applications by keyword.

    Supports boolean operators (AND, OR, NOT), wildcards (*),
    exact phrases (""), field:value syntax, and range queries.

    Examples:

        uspto search "machine learning"

        uspto search "applicationMetaData.firstApplicantName:Google"

        uspto search "artificial intelligence" --sort "applicationMetaData.filingDate desc"
    """
    client = ctx.obj["client"]
    result = client.search_patents(
        query, sort=sort, offset=offset, limit=limit,
        fields=fields, filters=filters, range_filters=range_filters, facets=facets,
    )

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    _render_patent_results(result, query)


@main.command()
@click.argument("application_number")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--section", type=click.Choice([
    "full", "meta-data", "assignment", "attorney", "continuity",
    "transactions", "documents", "adjustment", "foreign-priority",
    "associated-documents",
]), default="full", help="Which section of the application to retrieve")
@click.pass_context
def lookup(ctx, application_number, json_output, section):
    """Look up a patent application by number.

    Examples:

        uspto lookup 14412875

        uspto lookup 14412875 --section assignment

        uspto lookup 16330077 --section documents
    """
    client = ctx.obj["client"]

    section_map = {
        "full": client.get_application,
        "meta-data": client.get_application_metadata,
        "assignment": client.get_application_assignment,
        "attorney": client.get_application_attorney,
        "continuity": client.get_application_continuity,
        "transactions": client.get_application_transactions,
        "documents": client.get_application_documents,
        "adjustment": client.get_application_adjustment,
        "foreign-priority": client.get_application_foreign_priority,
        "associated-documents": client.get_associated_documents,
    }

    result = section_map[section](application_number)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    _render_application(result, application_number, section)


# ── Petition Decisions ───────────────────────────────────


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--offset", "-o", default=0, help="Start offset")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def petitions(ctx, query, limit, offset, json_output):
    """Search petition decisions.

    Example:

        uspto petitions "Denied AND Design"
    """
    client = ctx.obj["client"]
    result = client.search_petition_decisions(query, offset=offset, limit=limit)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    console.print(Panel(json.dumps(result, indent=2)[:3000], title=f"Petition Decisions: '{query}'"))


# ── PTAB Trials ──────────────────────────────────────────


@main.command()
@click.argument("query")
@click.option("--type", "search_type", type=click.Choice(["proceedings", "decisions", "documents"]),
              default="proceedings", help="PTAB search type")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--offset", "-o", default=0, help="Start offset")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def ptab(ctx, query, search_type, limit, offset, json_output):
    """Search PTAB trials (proceedings, decisions, or documents).

    Example:

        uspto ptab "IPR2023" --type proceedings
    """
    client = ctx.obj["client"]
    search_map = {
        "proceedings": client.search_ptab_proceedings,
        "decisions": client.search_ptab_decisions,
        "documents": client.search_ptab_documents,
    }
    result = search_map[search_type](query, offset=offset, limit=limit)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    console.print(Panel(json.dumps(result, indent=2)[:3000], title=f"PTAB {search_type}: '{query}'"))


# ── Appeals & Interferences ──────────────────────────────


@main.command()
@click.argument("query")
@click.option("--type", "search_type", type=click.Choice(["appeals", "interferences"]),
              default="appeals", help="Search type")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def appeals(ctx, query, search_type, limit, json_output):
    """Search PTAB appeal or interference decisions.

    Example:

        uspto appeals "pharmaceutical" --type appeals
    """
    client = ctx.obj["client"]
    if search_type == "appeals":
        result = client.search_appeal_decisions(query, limit=limit)
    else:
        result = client.search_interference_decisions(query, limit=limit)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    console.print(Panel(json.dumps(result, indent=2)[:3000], title=f"PTAB {search_type}: '{query}'"))


# ── Bulk Datasets ────────────────────────────────────────


@main.command()
@click.argument("query", default="")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def datasets(ctx, query, limit, json_output):
    """Search bulk dataset products.

    Example:

        uspto datasets "patent grant"
    """
    client = ctx.obj["client"]
    result = client.search_bulk_datasets(query, limit=limit)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    console.print(Panel(json.dumps(result, indent=2)[:3000], title=f"Bulk Datasets: '{query}'"))


# ── Status Codes ─────────────────────────────────────────


@main.command("status-codes")
@click.argument("query", default="")
@click.option("--limit", "-n", default=25, help="Number of results")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.pass_context
def status_codes(ctx, query, limit, json_output):
    """Search patent application status codes.

    Example:

        uspto status-codes "Preexam"
    """
    client = ctx.obj["client"]
    result = client.search_status_codes(query, limit=limit)

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    console.print(Panel(json.dumps(result, indent=2)[:3000], title=f"Status Codes: '{query}'"))


# ── Cache Management ─────────────────────────────────────


@main.command("clear-cache")
@click.pass_context
def clear_cache(ctx):
    """Clear the local response cache."""
    from uspto.cache import PatentCache
    cache = PatentCache()
    count = cache.clear()
    console.print(f"[green]Cleared {count} cached responses.[/green]")


# ── Renderers ────────────────────────────────────────────


def _render_patent_results(result: dict, query: str):
    """Render patent search results as a rich table."""
    count = result.get("count", result.get("recordTotalQuantity", 0))
    records = result.get("patentFileWrapperDataBag", result.get("results", []))

    if not records:
        console.print(f"[yellow]No results for '{query}'[/yellow]")
        return

    table = Table(title=f"Patent Search: '{query}' ({count} total)", show_lines=True)
    table.add_column("App #", style="cyan", no_wrap=True)
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Filing Date", style="green", no_wrap=True)
    table.add_column("Status", style="yellow", no_wrap=True)
    table.add_column("Applicant", style="magenta")

    for doc in records:
        app_num = doc.get("applicationNumberText", "—")
        meta = doc.get("applicationMetaData", {})
        title = meta.get("inventionTitle", "—")
        filing = meta.get("filingDate", "—")
        status = meta.get("applicationStatusDescriptionText", "—")
        applicant = meta.get("firstApplicantName", "—")

        table.add_row(app_num, title, filing, status, applicant)

    console.print(table)
    console.print(f"\n[dim]Showing {len(records)} of {count} results[/dim]")


def _render_application(result: dict, app_number: str, section: str):
    """Render a single application lookup."""
    records = result.get("patentFileWrapperDataBag", [])
    if not records:
        console.print(f"[yellow]No data found for application {app_number}[/yellow]")
        return

    doc = records[0]
    meta = doc.get("applicationMetaData", {})

    if section == "full" or section == "meta-data":
        console.print(Panel.fit(
            f"[cyan]Application:[/cyan] {doc.get('applicationNumberText', app_number)}\n"
            f"[cyan]Title:[/cyan] {meta.get('inventionTitle', '—')}\n"
            f"[cyan]Type:[/cyan] {meta.get('applicationTypeLabelName', '—')}\n"
            f"[cyan]Filing Date:[/cyan] {meta.get('filingDate', '—')}\n"
            f"[cyan]Grant Date:[/cyan] {meta.get('grantDate', '—')}\n"
            f"[cyan]Patent #:[/cyan] {meta.get('patentNumber', '—')}\n"
            f"[cyan]Status:[/cyan] {meta.get('applicationStatusDescriptionText', '—')}\n"
            f"[cyan]Applicant:[/cyan] {meta.get('firstApplicantName', '—')}\n"
            f"[cyan]Group Art Unit:[/cyan] {meta.get('groupArtUnitNumber', '—')}",
            title=f"Patent Application {app_number}",
        ))
    else:
        # For other sections, pretty-print the JSON
        console.print(Panel(
            json.dumps(doc, indent=2)[:5000],
            title=f"{section} — Application {app_number}",
        ))


if __name__ == "__main__":
    main()
