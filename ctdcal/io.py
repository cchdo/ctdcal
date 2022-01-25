import logging
from io import BufferedIOBase, BytesIO, StringIO
from pathlib import Path
from typing import Union
from zipfile import ZipFile, is_zipfile
from zipimport import ZipImportError

import pandas as pd
import requests

log = logging.getLogger(__name__)


def load_exchange_btl(btl_file: Union[str, Path]) -> pd.DataFrame:
    """
    Load WHP-exchange bottle file (_hy1.csv) into DataFrame. File can be on local
    file system or downloaded from an appropriate cchdo.ucsd.edu link
    (e.g., https://cchdo.ucsd.edu/data/19436/325020210316_hy1.csv)

    Adapted from cchdo.hydro package.

    Parameters
    ----------
    btl_file : str or Path
        Name or URL of file to be loaded

    Returns
    -------
    df : DataFrame
        Loaded bottle file
    """
    # read from url
    if isinstance(btl_file, (str, Path)) and str(btl_file).startswith("http"):
        log.info("Loading bottle file from http link")
        file = requests.get(btl_file).text.splitlines(keepends=True)

    # read from file
    elif isinstance(btl_file, (str, Path)):
        log.info("Loading bottle file from local file")
        with open(btl_file) as f:
            file = f.readlines()

    # find index of units row
    for idx, line in enumerate(file):
        if line.startswith("EXPOCODE"):
            units = idx + 1  # units row immediately follows column names
            break

    return pd.read_csv(
        StringIO("".join(file)),
        skiprows=[0, units],
        skipfooter=1,
        engine="python",
        comment="#",
        skipinitialspace=True,
    )


def load_exchange_ctd(
    ctd_file: Union[str, Path, BufferedIOBase], recursed=False
) -> pd.DataFrame:
    """
    Load WHP-exchange CTD file(s) (_ct1.csv) into DataFrame. File(s) can be on local
    file system or downloaded from an appropriate cchdo.ucsd.edu link
    (e.g., https://cchdo.ucsd.edu/data/19434/325020210316_ct1.zip)

    Adapted from cchdo.hydro package.

    Parameters
    ----------
    ctd_file : str or Path
        Name or URL of file to be loaded

    Returns
    -------
    df : DataFrame
        Loaded CTD file
    """
    # read from url (.zip)
    if isinstance(ctd_file, (str, Path)) and str(ctd_file).startswith("http"):
        log.info("Loading CTD file from http link")
        data_raw = BytesIO(requests.get(ctd_file).content)

    # read from file
    elif isinstance(ctd_file, (str, Path)):
        log.info("Loading CTD file from local file")
        with open(ctd_file, "rb") as f:
            data_raw = BytesIO(f.read())

    # read from open file
    elif isinstance(ctd_file, BufferedIOBase):
        log.info("Loading open file object")
        data_raw = BytesIO(ctd_file.read())

    # .zip special behavior
    if is_zipfile(data_raw):
        log.info("Loading CTD files from .zip")

        if recursed is True:
            raise ZipImportError("Recursive .zip files encountered... exiting")

        data_raw.seek(0)  # is_zipfile moves cursor to EOF, reset to start
        zip_contents = []
        with ZipFile(data_raw) as zf:
            for zipinfo in zf.infolist():
                zip_contents.append(BytesIO(zf.read(zipinfo)))

        # same as using functools.partial, slightly different syntax
        return [load_exchange_ctd(zc, recursed=True) for zc in zip_contents]

    else:
        data_raw.seek(0)  # is_zipfile moves cursor to EOF, reset to start
        file = data_raw.read().decode("utf8").splitlines(keepends=True)

    # find index of units row
    for idx, line in enumerate(file):
        if line.startswith("CTDPRS"):
            columns = idx
            units = idx + 1  # units row immediately follows column names
            break

    return pd.read_csv(
        StringIO("".join(file)),
        skiprows=list(range(0, columns)) + [units],  # skip up to column names (+ units)
        skipfooter=1,
        engine="python",
        comment="#",
        skipinitialspace=True,
    )


def write_pressure_details(
    ssscc: str, log_file: Union[str, Path], p_start: float, p_end: float
) -> None:
    """
    Write start/end deck pressure to ondeck_pressure.csv log file.

    Parameters
    ----------
    ssscc : str
        Station/cast in SSSCC format
    log_file : str or Path
        File destination for pressure details
    p_start : float
        Average starting on-deck pressure (pre-deployment)
    p_end : float
        Average ending on-deck pressure (post-deployment)

    Returns
    -------
    None
    """
    df = pd.DataFrame(
        {"SSSCC": ssscc, "ondeck_start_p": p_start, "ondeck_end_p": p_end}, index=[0]
    )
    add_header = not Path(log_file).exists()  # add header iff file doesn't exist
    with open(log_file, "a") as f:
        df.to_csv(f, mode="a", header=add_header, index=False)


def write_cast_details(
    ssscc: str,
    log_file: Union[str, Path],
    time_start: float,
    time_end: float,
    time_bottom: float,
    p_start: float,
    p_max: float,
    b_alt: float,
    b_lat: float,
    b_lon: float,
) -> None:
    """
    Write cast details to cast_details.csv log file.

    Parameters
    ----------
    ssscc : str
        Station/cast in SSSCC format
    log_file : str or Path
        File destination for cast details
    time_start : float
        Time at start of cast (from minimum pressure after 10m soak)
    time_end : float
        Time at end of cast (when instrument leaves water)
    time_bottom : float
        Time at bottom of cast (max depth)
    p_start : float
        Pressure at the time the cast begins
    p_max : float
        Pressure at bottom of cast
    b_alt : float
        Altimeter value at bottom of cast
    b_lat : float
        Latitude at bottom of cast
    b_lon : float
        Longitude at bottom of cast

    Returns
    -------
    None
    """
    df = pd.DataFrame(
        {
            "SSSCC": ssscc,
            "start_time": time_start,
            "bottom_time": time_bottom,
            "end_time": time_end,
            "start_pressure": p_start,
            "max_pressure": p_max,
            "altimeter_bottom": b_alt,
            "latitude": b_lat,
            "longitude": b_lon,
        },
        index=[0],
    )
    add_header = not Path(log_file).exists()  # add header iff file doesn't exist
    with open(log_file, "a") as f:
        df.to_csv(f, mode="a", header=add_header, index=False)