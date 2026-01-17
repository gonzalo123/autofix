from commands import setup_commands
from lib.cli import cli

import logging

logging.basicConfig(
            format='%(asctime)s [%(levelname)s] %(message)s',
            level=logging.INFO,
            datefmt='%d/%m/%Y %X'
        )

setup_commands(cli)

if __name__ == "__main__":
    cli()
