import click
from . import crud

# @click.group()
# def main():
#     pass

# @main.command()
# def init():
#     click.echo("Welcome to lpm install wizard.")

@click.group()
def main():
    pass

main.add_command(crud.setup)
main.add_command(crud.check)