from .log import run as log


def setup_commands(cli):
    cli.add_command(cmd=log, name="log")
