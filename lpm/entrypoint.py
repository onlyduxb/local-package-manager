# ruff: noqa

import click
from . import commands, crud

# crud.lpm_pth()
# crud.pyright_config()
# crud.vendors()


@click.group()
def main():
    pass


main.add_command(commands.setup)
main.add_command(commands.check)
main.add_command(commands.install)
main.add_command(commands.uninstall)
main.add_command(commands.update)
main.add_command(commands.publish)
