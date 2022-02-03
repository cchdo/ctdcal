import logging
from importlib import resources
from pathlib import Path

import click
from bokeh.application import Application
from bokeh.application.handlers.script import ScriptHandler
from bokeh.server.server import Server
from tornado.ioloop import IOLoop

from . import get_ctdcal_config

# Rich handling
# from rich.logging import RichHandler
# from rich.console import Console
# handler = logging.StreamHandler()
# handler.addFilter(logging.Filter("ctdcal"))  # filter out msgs from other modules
# FORMAT = "%(funcName)s: %(message)s"
# logging.basicConfig(
#     level="INFO",
#     format=FORMAT,
#     datefmt="[%X]",
#     handlers=[handler, RichHandler(console=Console(stderr=True))],
# )

# log = logging.getLogger(__name__)

handler = logging.StreamHandler()
handler.addFilter(logging.Filter("ctdcal"))  # filter out msgs from other modules
FORMAT = "%(funcName)s: %(message)s"
logging.basicConfig(
    level=logging.NOTSET,
    format=FORMAT,
    datefmt="[%X]",
    handlers=[handler],
    # handlers=[RichHandler(console=Console(stderr=True))],
)

log = logging.getLogger(__name__)
cfg = get_ctdcal_config()


@click.group()
@click.option("--debug/--no-debug", default=False)
def cli(debug):
    """The ctdcal command creates and manipulates data directories

    Documentation: tbd
    """
    if debug:
        click.echo("Debug mode on (logging all levels)")
        logging.getLogger("ctdcal").setLevel(logging.NOTSET)
    else:
        click.echo("Debug mode off (logging 'WARNING' and higher levels)")
        logging.getLogger("ctdcal").setLevel(logging.WARNING)


@cli.command()
def init():
    """Setup data folder with appropriate subfolders"""

    log.info(f"Building default /data/ directories: \n {*cfg.dirs.keys(),}")

    for sub_dir in cfg.dirs.values():
        Path(sub_dir).mkdir(parents=True)


@cli.command("import")  # click workaround to get a command named 'import'
def import_data():
    """Import data from given folder into ctdcal for processing"""
    # something like this?
    # ctdcal import _path_

    # TODO: smart imports based on file ext? .hex, .xmlcon, .cap
    # NOTE: ODF file types vs. others (oxygen, salt)

    raise NotImplementedError


@cli.command()
@click.option(
    "-g",
    "--group",
    type=click.Choice(["ODF", "PMEL"], case_sensitive=False),
    default="ODF",
)
# @click.option(
#     "-t",
#     "--type",
#     type=click.Choice(["bottle", "ctd", "all"], case_sensitive=False),
#     default="all",
# )
def process(group):
    """Process data using a particular group's methodology"""

    if group == "ODF":
        from .scripts.odf_process_all import odf_process_all

        odf_process_all()
    elif group == "PMEL":
        # pmel_process()
        raise NotImplementedError


@cli.command()
def cruise_report():
    """Generate bottle residual figures for cruise report"""

    from .scripts.cruise_report import cruise_report_residuals

    cruise_report_residuals()


@cli.command()
def qc():  # pragma: no cover
    """Launch interactive data flagging web app for QA/QC"""
    io_loop = IOLoop.current()
    with resources.path("ctdcal.tools", "data_qc.py") as fname:
        bokeh_app = Application(ScriptHandler(filename=fname))
    server = Server(bokeh_app, io_loop=io_loop)
    server.start()
    server.show("/")
    io_loop.start()


if __name__ == "__main__":
    cli()
