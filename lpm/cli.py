# ruff: noqa

import click
from . import crud

@click.group()
def main():
    pass

main.add_command(crud.setup)
main.add_command(crud.check)