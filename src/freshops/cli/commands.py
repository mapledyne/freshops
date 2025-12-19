"""
CLI commands for FreshOps.

Defines the Click command structure for interacting with
FreshService via the command line.
"""

from __future__ import annotations

from typing import Any

import click
from rich.console import Console

from freshops import FreshServiceClient, __version__, configure_logging, load_config
from freshops.models import Agent, Agents, Departments, Locations

# Shared Rich console instance
console = Console()


def print_output(content: Any, *, plain: bool = False) -> None:
    """
    Print output using Rich or plain text based on mode.

    :param content: Content to print (Rich renderable or string)
    :param plain: If True, use plain text output; if False, use Rich
    """
    if plain:
        # Plain text mode: convert Rich objects to strings
        if hasattr(content, "__str__"):
            click.echo(str(content))
        else:
            click.echo(content)
    else:
        # Rich mode: use Rich console
        console.print(content)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="freshops")
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug mode (sets log level to DEBUG and enables debug features).",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default=None,
    help="Set the logging level (DEBUG, INFO, WARNING, ERROR). Default: ERROR.",
)
@click.option(
    "--plain",
    is_flag=True,
    default=False,
    help="Use plain text output (no Rich formatting). Useful for scripting.",
)
@click.pass_context
def main(
    ctx: click.Context, debug: bool, log_level: str | None, plain: bool
) -> None:
    """
    FreshOps - FreshService API lookup and reporting tool.

    Use the subcommands below to interact with FreshService data.
    """
    # Ensure context object exists for passing data to subcommands
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["plain"] = plain

    # Configure logging
    # --debug flag overrides --log-level and sets to DEBUG
    if debug:
        actual_log_level = "DEBUG"
    elif log_level:
        actual_log_level = log_level.upper()
    else:
        # Default to ERROR for quiet operation
        actual_log_level = "ERROR"

    configure_logging(actual_log_level)

    # Load configuration (from env vars / .env file)
    config = load_config()
    ctx.obj["config"] = config

    # Initialize registries with client (for caching and lazy loading)
    # This is done here so all commands have access to caching
    if config:
        from freshops.models.base import CachedCollection

        client = FreshServiceClient(config)
        CachedCollection.initialize_all_registries(client)

    # If no subcommand, just show help (no config needed)
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# -----------------------------------------------------------------------------
# Tickets Command Group
# -----------------------------------------------------------------------------


@main.group()
@click.pass_context
def tickets(ctx: click.Context) -> None:
    """
    Ticket operations.

    List, search, and retrieve ticket information.
    """
    pass


@tickets.command("list")
@click.option(
    "--status",
    type=click.Choice(["open", "pending", "resolved", "closed"]),
    help="Filter by ticket status",
)
@click.option(
    "--priority",
    type=click.Choice(["low", "medium", "high", "urgent"]),
    help="Filter by priority",
)
@click.option(
    "--limit",
    default=50,
    help="Maximum number of tickets to return",
)
@click.pass_context
def tickets_list(
    ctx: click.Context,
    status: str | None,
    priority: str | None,
    limit: int,
) -> None:
    """
    List tickets with optional filters.

    Examples::

        freshops tickets list
        freshops tickets list --status open
        freshops tickets list --status open --priority high --limit 10
    """
    raise NotImplementedError("tickets_list not yet implemented")


@tickets.command("get")
@click.argument("ticket_id", type=int)
@click.pass_context
def tickets_get(ctx: click.Context, ticket_id: int) -> None:
    """
    Get details for a specific ticket.

    Example::

        freshops tickets get 12345
    """
    raise NotImplementedError("tickets_get not yet implemented")


# -----------------------------------------------------------------------------
# Agents Command Group
# -----------------------------------------------------------------------------


@main.group()
@click.pass_context
def agents(ctx: click.Context) -> None:
    """
    Agent operations.

    List and retrieve agent information.
    """
    pass


@agents.command("list")
@click.option(
    "--limit",
    default=100,
    help="Maximum number of agents to return",
)
@click.pass_context
def agents_list(ctx: click.Context, limit: int) -> None:
    """
    List active agents.

    By default, only active agents are shown. Use filtering methods
    in the library to access inactive agents if needed.

    Example::

        freshops agents list
    """
    config = ctx.obj["config"]
    client = FreshServiceClient(config)

    agents = Agents.from_api_response(client.list_agents(limit=limit)).active()

    if not agents:
        plain = ctx.obj.get("plain", False)
        if plain:
            click.echo("No active agents found.")
        else:
            console.print("[yellow]No active agents found.[/yellow]")
        return

    plain = ctx.obj.get("plain", False)
    print_output(agents, plain=plain)


@agents.command("count")
@click.option(
    "--limit",
    default=100,
    help="Maximum number of agents to query",
)
@click.pass_context
def agents_count(ctx: click.Context, limit: int) -> None:
    """
    Count active agents.

    By default, only active agents are counted. Use filtering methods
    in the library to access inactive agents if needed.

    Example::

        freshops agents count
    """
    config = ctx.obj["config"]
    client = FreshServiceClient(config)

    agents = Agents.from_api_response(client.list_agents(limit=limit)).active()

    count = len(agents)
    plain = ctx.obj.get("plain", False)
    if plain:
        click.echo(str(count))
    else:
        console.print(f"[bold cyan]{count}[/bold cyan] [dim]agent{'s' if count != 1 else ''}[/dim]")


@agents.command("get")
@click.argument("agent_id", type=int)
@click.pass_context
def agents_get(ctx: click.Context, agent_id: int) -> None:
    """
    Get details for a specific agent.

    Example::

        freshops agents get 23004708456
    """
    config = ctx.obj["config"]
    client = FreshServiceClient(config)

    agent_data = client.get_agent(agent_id)
    agent = Agent.from_api_response(agent_data)

    plain = ctx.obj.get("plain", False)
    print_output(agent, plain=plain)


# -----------------------------------------------------------------------------
# Requesters Command Group
# -----------------------------------------------------------------------------


@main.group()
@click.pass_context
def requesters(ctx: click.Context) -> None:
    """
    Requester operations.

    List and search requester information.
    """
    pass


@requesters.command("list")
@click.option(
    "--limit",
    default=100,
    help="Maximum number of requesters to return",
)
@click.pass_context
def requesters_list(ctx: click.Context, limit: int) -> None:
    """
    List requesters.

    Example::

        freshops requesters list
    """
    raise NotImplementedError("requesters_list not yet implemented")


@requesters.command("search")
@click.option(
    "--email",
    help="Search by email address",
)
@click.option(
    "--name",
    help="Search by name",
)
@click.pass_context
def requesters_search(
    ctx: click.Context,
    email: str | None,
    name: str | None,
) -> None:
    """
    Search for requesters.

    Examples::

        freshops requesters search --email "user@example.com"
        freshops requesters search --name "John"
    """
    raise NotImplementedError("requesters_search not yet implemented")


# -----------------------------------------------------------------------------
# Locations Command Group
# -----------------------------------------------------------------------------


@main.group()
@click.pass_context
def locations(ctx: click.Context) -> None:
    """
    Location operations.

    List and retrieve location information.
    """
    pass


@locations.command("list")
@click.option(
    "--limit",
    default=100,
    help="Maximum number of locations to return",
)
@click.pass_context
def locations_list(ctx: click.Context, limit: int) -> None:
    """
    List all locations.

    Example::

        freshops locations list
    """
    config = ctx.obj["config"]
    client = FreshServiceClient(config)

    locations = Locations.from_api_response(client.list_locations(limit=limit))

    if not locations:
        plain = ctx.obj.get("plain", False)
        if plain:
            click.echo("No locations found.")
        else:
            console.print("[yellow]No locations found.[/yellow]")
        return

    plain = ctx.obj.get("plain", False)
    print_output(locations, plain=plain)


@locations.command("count")
@click.option(
    "--limit",
    default=100,
    help="Maximum number of locations to query",
)
@click.pass_context
def locations_count(ctx: click.Context, limit: int) -> None:
    """
    Count locations.

    Example::

        freshops locations count
    """
    config = ctx.obj["config"]
    client = FreshServiceClient(config)

    locations = Locations.from_api_response(client.list_locations(limit=limit))

    count = len(locations)
    plain = ctx.obj.get("plain", False)
    if plain:
        click.echo(str(count))
    else:
        console.print(f"[bold cyan]{count}[/bold cyan] [dim]location{'s' if count != 1 else ''}[/dim]")


# -----------------------------------------------------------------------------
# Departments Command Group
# -----------------------------------------------------------------------------


@main.group()
@click.pass_context
def departments(ctx: click.Context) -> None:
    """
    Department operations.

    List and retrieve department information.
    """
    pass


@departments.command("list")
@click.option(
    "--limit",
    default=100,
    help="Maximum number of departments to return",
)
@click.pass_context
def departments_list(ctx: click.Context, limit: int) -> None:
    """
    List all departments.

    Example::

        freshops departments list
    """
    config = ctx.obj["config"]
    client = FreshServiceClient(config)

    departments = Departments.from_api_response(client.list_departments(limit=limit))

    if not departments:
        plain = ctx.obj.get("plain", False)
        if plain:
            click.echo("No departments found.")
        else:
            console.print("[yellow]No departments found.[/yellow]")
        return

    plain = ctx.obj.get("plain", False)
    print_output(departments, plain=plain)


@departments.command("count")
@click.option(
    "--limit",
    default=100,
    help="Maximum number of departments to query",
)
@click.pass_context
def departments_count(ctx: click.Context, limit: int) -> None:
    """
    Count departments.

    Example::

        freshops departments count
    """
    config = ctx.obj["config"]
    client = FreshServiceClient(config)

    departments = Departments.from_api_response(client.list_departments(limit=limit))

    count = len(departments)
    plain = ctx.obj.get("plain", False)
    if plain:
        click.echo(str(count))
    else:
        console.print(f"[bold cyan]{count}[/bold cyan] [dim]department{'s' if count != 1 else ''}[/dim]")


# -----------------------------------------------------------------------------
# Assets Command Group
# -----------------------------------------------------------------------------


@main.group()
@click.pass_context
def assets(ctx: click.Context) -> None:
    """
    Asset operations.

    List and search asset information.
    """
    pass


@assets.command("list")
@click.option(
    "--limit",
    default=100,
    help="Maximum number of assets to return",
)
@click.pass_context
def assets_list(ctx: click.Context, limit: int) -> None:
    """
    List assets.

    Example::

        freshops assets list
    """
    raise NotImplementedError("assets_list not yet implemented")


@assets.command("search")
@click.option(
    "--name",
    help="Search by asset name",
)
@click.pass_context
def assets_search(ctx: click.Context, name: str | None) -> None:
    """
    Search for assets.

    Example::

        freshops assets search --name "laptop"
    """
    raise NotImplementedError("assets_search not yet implemented")
