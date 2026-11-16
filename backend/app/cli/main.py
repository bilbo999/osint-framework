"""`osint` CLI entrypoint. Commands are added in Phase 10 (docs/phases/phase-10.md)."""

import typer

from app import __version__

app = typer.Typer(
    name="osint", help="OSINT Framework CLI (public sources only).", no_args_is_help=True
)


@app.command()
def version() -> None:
    """Print the framework version."""
    typer.echo(__version__)


@app.callback()
def main() -> None:
    """OSINT Framework command-line interface."""
