import click

from taskweb.server import create_app


@click.group()
def main():
    """TaskWeb - Web interface for Taskwarrior."""
    pass


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=5000, type=int, help="Port to bind to.")
@click.option("--debug", is_flag=True, help="Enable debug mode.")
def serve(host, port, debug):
    """Start the web server."""
    app = create_app()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
