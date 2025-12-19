"""
Entry point for running freshops.cli as a module.

Usage::

    python -m freshops.cli [COMMAND] [OPTIONS]
"""

import sys


def _is_interactive_mode() -> bool:
    """
    Check if running in interactive/debug mode.

    --debug flag indicates interactive use where we don't need
    strict exit codes and want to avoid debugger interruptions.
    """
    return "--debug" in sys.argv or any(
        arg.startswith("--log-level") and "DEBUG" in arg.upper()
        for arg in sys.argv
    )


def _needs_config() -> bool:
    """
    Check if the command being run requires configuration.

    Help and version requests don't need config.
    """
    safe_args = {
        "--help",
        "-h",
        "--version",
        "--debug",
        "--log-level",
        "--plain",
    }
    args = set(sys.argv[1:])

    # No args = show help, no config needed
    if not args:
        return False

    # If only safe args (help, version, debug flags), no config needed
    if args.issubset(safe_args):
        return False

    # Any actual command needs config
    return True


def _check_config_early() -> bool:
    """
    Check config before Click runs.

    :returns: True if config is valid, False if missing
    """
    from freshops import check_config, load_config
    from freshops.config import get_config_help

    config = load_config()
    is_valid, missing = check_config(config)

    if not is_valid:
        import click

        click.secho("Error: Missing required configuration!", fg="red", bold=True)
        click.echo()
        click.echo(f"Missing: {', '.join(missing)}")
        click.echo()
        click.echo(get_config_help())
        return False

    return True


def _exit(code: int) -> None:
    """
    Exit with the given code, respecting interactive mode.

    In interactive mode (--debug), we just return and let the script
    end naturally to avoid triggering debugger breakpoints on SystemExit.
    In automation mode, we use sys.exit() for proper exit codes.
    """
    if _is_interactive_mode():
        # Let script end naturally - debugger won't break
        return
    sys.exit(code)


def run() -> None:
    """Run the CLI with proper exception handling."""
    import click

    from freshops.cli.commands import main

    # Check config BEFORE Click runs to avoid exception handling issues
    if _needs_config() and not _check_config_early():
        _exit(1)
        return  # In interactive mode, _exit() returns so we need this

    # Run Click with standalone_mode=False so we handle exceptions ourselves
    try:
        main(standalone_mode=False)
    except click.ClickException as e:
        e.show()
        _exit(e.exit_code)
    except click.Abort:
        click.echo("Aborted!", err=True)
        _exit(1)


if __name__ == "__main__":
    run()
