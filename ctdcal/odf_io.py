import csv
import datetime as dt
import sys
from collections import OrderedDict
from pathlib import Path

import gsw
import numpy as np
import pandas as pd

import config as cfg


def _salt_loader(ssscc, salt_dir):
    """
    Load raw file into salt and reference DataFrames.
    """
    saltpath = salt_dir + ssscc  # salt files have no extension
    with open(saltpath, newline="") as f:
        saltF = csv.reader(
            f, delimiter=" ", quoting=csv.QUOTE_NONE, skipinitialspace="True"
        )
        saltArray = []
        for row in saltF:
            saltArray.append(row)
        del saltArray[0]  # remove header

    header = OrderedDict(  # having this as a dict streamlines next steps
        [
            ("STNNBR", int),
            ("CASTNO", int),
            ("SAMPNO", int),
            ("BathTEMP", int),
            ("CRavg", float),
            ("autosalSAMPNO", int),
            ("Unknown", int),
            ("StartTime", object),
            ("EndTime", object),
            ("Attempts", int),
        ]
    )
    saltDF = pd.DataFrame.from_records(saltArray)

    # add as many "Reading#"s as needed
    for ii in range(0, len(saltDF.columns) - len(header)):
        header["Reading{}".format(ii + 1)] = float
    saltDF.columns = list(header.keys())  # name columns

    # TODO: check autosalSAMPNO against SAMPNO for mismatches?
    # TODO: handling for re-samples?

    # add time (in seconds) needed for autosal drift removal step
    saltDF["IndexTime"] = pd.to_datetime(saltDF["EndTime"])
    saltDF["IndexTime"] = (saltDF["IndexTime"] - saltDF["IndexTime"].iloc[0]).dt.seconds
    saltDF["IndexTime"] += (saltDF["IndexTime"] < 0) * (3600 * 24)  # fix overnight runs

    refDF = saltDF.loc[
        saltDF["autosalSAMPNO"] == "worm", ["IndexTime", "CRavg"]
    ].astype(float)
    saltDF = saltDF[saltDF["autosalSAMPNO"] != "worm"].astype(header)  # force dtypes

    return saltDF, refDF


def remove_autosal_drift(saltDF, refDF):
    """Calculate linear CR drift between reference values"""
    diff = refDF.diff(axis="index").dropna()
    time_coef = (diff["CRavg"] / diff["IndexTime"]).iloc[0]

    saltDF["CRavg"] += saltDF["IndexTime"] * time_coef
    saltDF["CRavg"] = saltDF["CRavg"].round(5)  # match initial precision
    saltDF = saltDF.drop(labels="IndexTime", axis="columns")

    return saltDF


def _salt_exporter(
    saltDF, outdir=cfg.directory["salt"], stn_col="STNNBR", cast_col="CASTNO"
):
    """
    Export salt DataFrame to .csv file. Extra logic is included in the event that
    multiple stations and/or casts are included in a single raw salt file.
    """
    stations = saltDF[stn_col].unique()
    for station in stations:
        stn_salts = saltDF[saltDF[stn_col] == station]
        casts = stn_salts[cast_col].unique()
        for cast in casts:
            stn_cast_salts = stn_salts[stn_salts[cast_col] == cast]
            outfile = (  # format to SSSCC_salts.csv
                outdir + "{0:03}".format(station) + "{0:02}".format(cast) + "_salts.csv"
            )
            if Path(outfile).exists():
                print(outfile + " already exists...skipping")
                continue
            stn_cast_salts.to_csv(outfile, index=False)


def process_salts(ssscc_list, salt_dir=cfg.directory["salt"]):
    # TODO: import salt_dir from a config file
    # TODO: update and include linear drift correction from above
    """
    Master salt processing function. Load in salt files for given station/cast list,
    calculate salinity, and export to .csv files.

    Parameters
    ----------
    ssscc_list : list of str
        List of stations to process
    salt_dir : str, optional
        Path to folder containing raw salt files (defaults to data/salt/)

    """
    for ssscc in ssscc_list:
        if not Path(salt_dir + ssscc + "_salts.csv").exists():
            try:
                saltDF, refDF = _salt_loader(ssscc, salt_dir)
            except FileNotFoundError:
                print("Salt file for cast " + ssscc + " does not exist... skipping")
                continue
            saltDF = remove_autosal_drift(saltDF, refDF)
            saltDF["SALNTY"] = gsw.SP_salinometer(
                (saltDF["CRavg"] / 2.0), saltDF["BathTEMP"]
            ).round(4)
            _salt_exporter(saltDF, salt_dir)

    return True
