"""CLI entry point for USPTO patent search."""

import json
import logging

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from uspto.api import USPTOClient

console = Console()

# Fields to request when --full is used on search (ensures metadata is populated)
FULL_SEARCH_FIELDS = ",".join([
    "applicationNumberText",
    "applicationMetaData.inventionTitle",
    "applicationMetaData.filingDate",
    "applicationMetaData.grantDate",
    "applicationMetaData.patentNumber",
    "applicationMetaData.applicationStatusDescriptionText",
    "applicationMetaData.applicationStatusCode",
    "applicationMetaData.firstApplicantName",
    "applicationMetaData.applicationTypeLabelName",
    "applicationMetaData.groupArtUnitNumber",
])


def _output(data, markdown=False):
    """Output helper: JSON to stdout (markdown) or rich panel (default)."""
    if markdown:
        click.echo(data)
    else:
        console.print(data)


def _error_exit(result):
    """Check for API error and exit if found. Returns True if error."""
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)
    return False


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
@click.option("--full", is_flag=True, help="Request full metadata fields (title, applicant, status, dates)")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown table (for agents)")
@click.pass_context
def search(ctx, query, limit, offset, sort, fields, filters, range_filters, facets, full, json_output, markdown):
    """Search patent applications by keyword.

    Supports boolean operators (AND, OR, NOT), wildcards (*),
    exact phrases (""), field:value syntax, and range queries.

    Use --full to always include title, applicant, status in results.

    Examples:

        uspto search "machine learning"

        uspto search "machine learning" --full

        uspto search "applicationMetaData.firstApplicantName:Google" --full

        uspto search "artificial intelligence" --sort "applicationMetaData.filingDate desc"
    """
    client = ctx.obj["client"]

    # If --full and no explicit fields, use our rich field set
    if full and not fields:
        fields = FULL_SEARCH_FIELDS

    result = client.search_patents(
        query, sort=sort, offset=offset, limit=limit,
        fields=fields, filters=filters, range_filters=range_filters, facets=facets,
    )

    if _error_exit(result):
        return

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    if markdown:
        _render_patent_results_markdown(result, query)
        return

    _render_patent_results(result, query)


@main.command()
@click.argument("application_number")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown (for agents)")
@click.option("--section", type=click.Choice([
    "full", "meta-data", "assignment", "attorney", "continuity",
    "transactions", "documents", "adjustment", "foreign-priority",
    "associated-documents",
]), default="full", help="Which section of the application to retrieve")
@click.pass_context
def lookup(ctx, application_number, json_output, markdown, section):
    """Look up a patent application by number.

    Examples:

        uspto lookup 14412875

        uspto lookup 14412875 --section assignment

        uspto lookup 16330077 --section documents --markdown
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

    if _error_exit(result):
        return

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    if markdown:
        _render_application_markdown(result, application_number, section)
        return

    _render_application(result, application_number, section)


# ── Landscape (Faceted Analysis) ────────────────────────


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=5, help="Number of sample results to show")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown (for agents)")
@click.pass_context
def landscape(ctx, query, limit, json_output, markdown):
    """Technology landscape analysis — top assignees and filing patterns.

    Runs a faceted search to show WHO is filing patents and application
    type distribution for a given technology area.

    Examples:

        uspto landscape "machine learning"

        uspto landscape "CRISPR gene editing" --markdown

        uspto landscape "applicationMetaData.firstApplicantName:Google"
    """
    client = ctx.obj["client"]

    # Faceted search: top assignees + application types + status
    facet_fields = ",".join([
        "applicationMetaData.firstApplicantName",
        "applicationMetaData.applicationTypeCode",
        "applicationMetaData.applicationStatusCode",
    ])

    result = client.search_patents(
        query,
        limit=limit,
        fields=FULL_SEARCH_FIELDS,
        facets=facet_fields,
        sort="applicationMetaData.filingDate desc",
    )

    if _error_exit(result):
        return

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    if markdown:
        _render_landscape_markdown(result, query)
        return

    _render_landscape(result, query)


# ── Patent Family (Continuity Chain) ────────────────────


@main.command()
@click.argument("application_number")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown (for agents)")
@click.pass_context
def family(ctx, application_number, json_output, markdown):
    """Show patent family — parent and child continuity chain.

    Retrieves continuity data for a patent application showing
    parent applications (prior art lineage) and child applications
    (derivatives, continuations, divisions).

    Examples:

        uspto family 14412875

        uspto family 16330077 --markdown
    """
    client = ctx.obj["client"]
    result = client.get_application_continuity(application_number)

    if _error_exit(result):
        return

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    if markdown:
        _render_family_markdown(result, application_number)
        return

    _render_family(result, application_number)


# ── Assignee Search ─────────────────────────────────────


@main.command()
@click.argument("assignee_name")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--offset", "-o", default=0, help="Start offset")
@click.option("--sort", "-s", default="applicationMetaData.filingDate desc", help="Sort order")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown (for agents)")
@click.pass_context
def assignee(ctx, assignee_name, limit, offset, sort, json_output, markdown):
    """Search patents by assignee/applicant name.

    Shortcut for field-targeted search on firstApplicantName.

    Examples:

        uspto assignee "Google"

        uspto assignee "OpenAI" --limit 20

        uspto assignee "Microsoft" --sort "applicationMetaData.filingDate asc"
    """
    client = ctx.obj["client"]
    query = f"applicationMetaData.firstApplicantName:{assignee_name}"
    result = client.search_patents(
        query, sort=sort, offset=offset, limit=limit,
        fields=FULL_SEARCH_FIELDS,
    )

    if _error_exit(result):
        return

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    if markdown:
        _render_patent_results_markdown(result, f"Assignee: {assignee_name}")
        return

    _render_patent_results(result, f"Assignee: {assignee_name}")


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

    if _error_exit(result):
        return

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

    if _error_exit(result):
        return

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

    if _error_exit(result):
        return

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

    if _error_exit(result):
        return

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

    if _error_exit(result):
        return

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


# ── Rich Renderers ──────────────────────────────────────


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
        console.print(Panel(
            json.dumps(doc, indent=2)[:5000],
            title=f"{section} — Application {app_number}",
        ))


def _render_landscape(result: dict, query: str):
    """Render landscape analysis with rich formatting."""
    count = result.get("count", 0)
    console.print(Panel.fit(
        f"[bold]Technology Landscape: '{query}'[/bold]\n"
        f"[cyan]Total Patents:[/cyan] {count:,}",
        title="Landscape Analysis",
    ))

    # Render facets if present
    facets = result.get("facets", {})
    if facets:
        for facet_name, facet_data in facets.items():
            short_name = facet_name.split(".")[-1]
            table = Table(title=f"Facet: {short_name}", show_lines=False)
            table.add_column("Value", style="cyan")
            table.add_column("Count", style="green", justify="right")

            buckets = facet_data if isinstance(facet_data, list) else facet_data.get("buckets", [])
            for bucket in buckets[:15]:
                if isinstance(bucket, dict):
                    val = bucket.get("value", bucket.get("key", "—"))
                    cnt = bucket.get("count", bucket.get("doc_count", "—"))
                    table.add_row(str(val), str(cnt))
                else:
                    table.add_row(str(bucket), "—")

            console.print(table)
    else:
        console.print("[yellow]No facet data returned — API may not support facets for this query[/yellow]")

    # Also show sample results
    records = result.get("patentFileWrapperDataBag", [])
    if records:
        console.print(f"\n[dim]Most recent {len(records)} filings:[/dim]")
        _render_patent_results(result, query)


def _render_family(result: dict, app_number: str):
    """Render patent family continuity data."""
    records = result.get("patentFileWrapperDataBag", [])
    if not records:
        console.print(f"[yellow]No continuity data for {app_number}[/yellow]")
        return

    doc = records[0]
    parents = doc.get("parentContinuityBag", [])
    children = doc.get("childContinuityBag", [])

    console.print(Panel.fit(
        f"[bold]Patent Family for {app_number}[/bold]\n"
        f"[cyan]Parents:[/cyan] {len(parents)}  |  [cyan]Children:[/cyan] {len(children)}",
        title="Continuity Chain",
    ))

    if parents:
        table = Table(title="Parent Applications", show_lines=True)
        table.add_column("App #", style="cyan")
        table.add_column("Filing Date", style="green")
        table.add_column("Relationship", style="yellow")
        table.add_column("Status", style="white")
        for p in parents:
            table.add_row(
                p.get("parentApplicationNumberText", p.get("applicationNumberText", "—")),
                p.get("filingDate", "—"),
                p.get("continuityTypeDescriptionText", p.get("claimTypeCode", "—")),
                p.get("applicationStatusDescriptionText", "—"),
            )
        console.print(table)

    if children:
        table = Table(title="Child Applications", show_lines=True)
        table.add_column("App #", style="cyan")
        table.add_column("Filing Date", style="green")
        table.add_column("Relationship", style="yellow")
        table.add_column("Status", style="white")
        for c in children:
            table.add_row(
                c.get("childApplicationNumberText", c.get("applicationNumberText", "—")),
                c.get("filingDate", "—"),
                c.get("continuityTypeDescriptionText", c.get("claimTypeCode", "—")),
                c.get("applicationStatusDescriptionText", "—"),
            )
        console.print(table)


# ── Markdown Renderers (for agent consumption) ──────────


def _render_patent_results_markdown(result: dict, query: str):
    """Render patent search results as markdown table."""
    count = result.get("count", result.get("recordTotalQuantity", 0))
    records = result.get("patentFileWrapperDataBag", result.get("results", []))

    lines = [f"## Patent Search: '{query}' ({count:,} total)", ""]

    if not records:
        lines.append("No results found.")
        click.echo("\n".join(lines))
        return

    lines.append("| App # | Title | Filing Date | Status | Applicant |")
    lines.append("|-------|-------|-------------|--------|-----------|")

    for doc in records:
        app_num = doc.get("applicationNumberText", "—")
        meta = doc.get("applicationMetaData", {})
        title = meta.get("inventionTitle", "—")
        filing = meta.get("filingDate", "—")
        status = meta.get("applicationStatusDescriptionText", "—")
        applicant = meta.get("firstApplicantName", "—")
        # Escape pipes in values
        title = str(title).replace("|", "\\|")[:60]
        applicant = str(applicant).replace("|", "\\|")
        lines.append(f"| {app_num} | {title} | {filing} | {status} | {applicant} |")

    lines.append(f"\n*Showing {len(records)} of {count:,} results*")
    click.echo("\n".join(lines))


def _render_application_markdown(result: dict, app_number: str, section: str):
    """Render application data as markdown."""
    records = result.get("patentFileWrapperDataBag", [])
    if not records:
        click.echo(f"No data found for application {app_number}")
        return

    doc = records[0]
    meta = doc.get("applicationMetaData", {})

    if section in ("full", "meta-data"):
        lines = [
            f"## Patent Application {app_number}",
            "",
            f"- **Title:** {meta.get('inventionTitle', '—')}",
            f"- **Type:** {meta.get('applicationTypeLabelName', '—')}",
            f"- **Filing Date:** {meta.get('filingDate', '—')}",
            f"- **Grant Date:** {meta.get('grantDate', '—')}",
            f"- **Patent #:** {meta.get('patentNumber', '—')}",
            f"- **Status:** {meta.get('applicationStatusDescriptionText', '—')}",
            f"- **Applicant:** {meta.get('firstApplicantName', '—')}",
            f"- **Group Art Unit:** {meta.get('groupArtUnitNumber', '—')}",
        ]
        click.echo("\n".join(lines))
    else:
        click.echo(f"## {section} — Application {app_number}\n")
        click.echo(f"```json\n{json.dumps(doc, indent=2)[:5000]}\n```")


def _render_landscape_markdown(result: dict, query: str):
    """Render landscape analysis as markdown."""
    count = result.get("count", 0)
    lines = [
        f"## Technology Landscape: '{query}'",
        "",
        f"**Total Patents:** {count:,}",
        "",
    ]

    facets = result.get("facets", {})
    if facets:
        for facet_name, facet_data in facets.items():
            short_name = facet_name.split(".")[-1]
            lines.append(f"### {short_name}")
            lines.append("")
            lines.append("| Value | Count |")
            lines.append("|-------|-------|")

            buckets = facet_data if isinstance(facet_data, list) else facet_data.get("buckets", [])
            for bucket in buckets[:15]:
                if isinstance(bucket, dict):
                    val = bucket.get("value", bucket.get("key", "—"))
                    cnt = bucket.get("count", bucket.get("doc_count", "—"))
                    lines.append(f"| {val} | {cnt} |")

            lines.append("")

    records = result.get("patentFileWrapperDataBag", [])
    if records:
        lines.append(f"### Most Recent {len(records)} Filings")
        lines.append("")
        lines.append("| App # | Title | Filing Date | Applicant |")
        lines.append("|-------|-------|-------------|-----------|")
        for doc in records:
            app_num = doc.get("applicationNumberText", "—")
            meta = doc.get("applicationMetaData", {})
            title = str(meta.get("inventionTitle", "—")).replace("|", "\\|")[:60]
            filing = meta.get("filingDate", "—")
            applicant = str(meta.get("firstApplicantName", "—")).replace("|", "\\|")
            lines.append(f"| {app_num} | {title} | {filing} | {applicant} |")

    click.echo("\n".join(lines))


def _render_family_markdown(result: dict, app_number: str):
    """Render patent family as markdown."""
    records = result.get("patentFileWrapperDataBag", [])
    if not records:
        click.echo(f"No continuity data for {app_number}")
        return

    doc = records[0]
    parents = doc.get("parentContinuityBag", [])
    children = doc.get("childContinuityBag", [])

    lines = [
        f"## Patent Family: {app_number}",
        "",
        f"**Parents:** {len(parents)} | **Children:** {len(children)}",
        "",
    ]

    if parents:
        lines.append("### Parent Applications")
        lines.append("")
        lines.append("| App # | Filing Date | Relationship | Status |")
        lines.append("|-------|-------------|--------------|--------|")
        for p in parents:
            lines.append("| {} | {} | {} | {} |".format(
                p.get("parentApplicationNumberText", p.get("applicationNumberText", "—")),
                p.get("filingDate", "—"),
                p.get("continuityTypeDescriptionText", p.get("claimTypeCode", "—")),
                p.get("applicationStatusDescriptionText", "—"),
            ))
        lines.append("")

    if children:
        lines.append("### Child Applications")
        lines.append("")
        lines.append("| App # | Filing Date | Relationship | Status |")
        lines.append("|-------|-------------|--------------|--------|")
        for c in children:
            lines.append("| {} | {} | {} | {} |".format(
                c.get("childApplicationNumberText", c.get("applicationNumberText", "—")),
                c.get("filingDate", "—"),
                c.get("continuityTypeDescriptionText", c.get("claimTypeCode", "—")),
                c.get("applicationStatusDescriptionText", "—"),
            ))

    click.echo("\n".join(lines))


if __name__ == "__main__":
    main()
