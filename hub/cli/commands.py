import click
from hub.cli.auth import login, logout, register
from hub import __version__


@click.group()
@click.version_option(__version__, message="%(prog)s %(version)s")
@click.pass_context
def cli(ctx):
    pass


def add_auth_commands(cli):
    cli.add_command(login)
    cli.add_command(logout)
    cli.add_command(register)


add_auth_commands(cli)