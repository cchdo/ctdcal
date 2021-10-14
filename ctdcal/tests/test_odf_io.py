import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ctdcal import odf_io


def make_salt_file(comment=None, flag=None, to_file=None):
    #  seed RNG for Reading3, comments, and flags
    rng = np.random.default_rng(seed=100)

    # build dummy DataFrame
    constants = {"STNNBR": "0001", "CASTNO": "01", "BathTemp": 21, "unk": 5907}
    salts = pd.DataFrame(data=constants, index=np.arange(12))
    salts.insert(2, "SAMPNO", [f"{x:02.0f}" for x in salts.index])
    salts.insert(4, "CRavg", np.linspace(1.95, 1.98, 12)[::-1])
    salts.insert(5, "autosalSAMPNO", salts["SAMPNO"].astype(int))
    salts.loc[[0, 11], "autosalSAMPNO"] = "worm"
    times = pd.date_range(start="18:32:04", end="19:36:03", periods=24)
    salts["StartTime"] = times[::2].strftime("%H:%M:%S")
    salts["EndTime"] = times[1::2].strftime("%H:%M:%S")

    # assign CR values around mean (give only some samples 3 readings)
    salts["Reading1"] = salts["CRavg"] + 1e-4
    salts["Reading2"] = salts["CRavg"] - 1e-4
    salts["Reading3"] = salts["CRavg"] * rng.choice([1, np.nan], 12)
    attempts = salts[["Reading1", "Reading2", "Reading3"]].count(axis=1)
    salts.insert(9, "Attempts", attempts.map("{:02.0f}".format))

    # add comment marker (#, x)
    if comment is not None:
        salts["STNNBR"] = rng.choice(["", comment], 12, p=[0.8, 0.2]) + salts["STNNBR"]

    # final formatting, remove blank Reading3 cells to match Autosal
    header = "12-345 operator: ABC box: S batch: P678 k15: 0.91011 std dial 408"
    string_df = salts.to_string(
        header=False, index=False, float_format="{:.5f}".format, na_rep=""
    )
    text_out = "\n".join([header, string_df.replace("        ", "")])

    if to_file is not None:
        with open(to_file, "w+") as f:
            f.write(text_out)
    else:
        return text_out


def test_salt_loader(caplog):
    # check salt file loads in correctly
    salt_file = make_salt_file()
    saltDF, refDF = odf_io._salt_loader(io.StringIO(salt_file))

    assert saltDF.shape == (10, 14)
    assert all(saltDF[["StartTime", "EndTime"]].dtypes == object)
    assert all(saltDF[["CRavg", "Reading1", "Reading2", "Reading3"]].dtypes == float)
    assert all(saltDF[["STNNBR", "CASTNO", "SAMPNO", "autosalSAMPNO"]].dtypes == int)
    assert all(saltDF[["BathTEMP", "Unknown", "Attempts", "IndexTime"]].dtypes == int)
    assert all(saltDF.index == np.arange(1, 11))
    assert saltDF["Reading3"].isna().sum() == 5

    assert refDF.shape == (2, 2)
    assert all(refDF.dtypes == float)
    assert all(refDF.index == [0, 11])

    # check commented lines are ignored (1, 4, 10)
    salt_file = make_salt_file(comment="#")
    with caplog.at_level(logging.DEBUG):
        saltDF, refDF = odf_io._salt_loader(io.StringIO(salt_file))
        assert "(#, x)" in caplog.messages[0]
        assert "test_odf_io" in caplog.messages[0]
    assert saltDF.shape == (7, 14)
    assert all(saltDF[["StartTime", "EndTime"]].dtypes == object)
    assert all(saltDF[["CRavg", "Reading1", "Reading2", "Reading3"]].dtypes == float)
    assert all(saltDF[["STNNBR", "CASTNO", "SAMPNO", "autosalSAMPNO"]].dtypes == int)
    assert all(saltDF[["BathTEMP", "Unknown", "Attempts", "IndexTime"]].dtypes == int)
    assert all(saltDF.index == [2, 3, 5, 6, 7, 8, 9])
    assert saltDF["Reading3"].isna().sum() == 3

    assert refDF.shape == (2, 2)
    assert all(refDF.dtypes == float)
    assert all(refDF.index == [0, 11])


def test_remove_autosal_drift(caplog):
    index_time = np.linspace(0, 300, 7)
    CRavg = np.array([2.0] * 6 + [1.4])
    saltDF = pd.DataFrame(data={"STNNBR": 1, "CASTNO": 1}, index=np.arange(1, 6))
    saltDF["IndexTime"], saltDF["CRavg"] = (index_time[1:-1], CRavg[1:-1])
    refDF = pd.DataFrame(data={"IndexTime": index_time[::6], "CRavg": CRavg[::6]})

    # check that drift is removed correctly
    removed = odf_io.remove_autosal_drift(saltDF, refDF)
    np.testing.assert_allclose(removed["CRavg"], np.arange(1.5, 2, 0.1)[::-1])
    assert "IndexTime" not in removed.columns

    # check input DataFrames have not been modified
    assert all(saltDF["CRavg"] == CRavg[1:-1])
    assert all(refDF["CRavg"] == CRavg[::6])

    # return unmodified saltDF if refDF is wrong size
    original = odf_io.remove_autosal_drift(saltDF, refDF.iloc[0])
    assert all(original["CRavg"] == saltDF["CRavg"])
    assert "IndexTime" not in original.columns
    assert "start/end reference" in caplog.messages[0]
    assert "00101" in caplog.messages[0]


def test_salt_exporter(tmp_path, caplog):
    saltDF = pd.DataFrame(data={"STNNBR": 1, "CASTNO": 1}, index=np.arange(5))
    saltDF["CRavg"] = np.ones(5)

    # check test data completes round trip
    assert not Path(tmp_path / "00101_salts.csv").exists()
    odf_io._salt_exporter(saltDF, outdir=str(tmp_path))
    assert Path(tmp_path / "00101_salts.csv").exists()
    with open(Path(tmp_path / "00101_salts.csv")) as f:
        assert saltDF.equals(pd.read_csv(f))

    # check "file already exists" message
    with caplog.at_level(logging.INFO):
        odf_io._salt_exporter(saltDF, outdir=str(tmp_path))
        assert "00101_salts.csv already exists" in caplog.messages[0]

    # check file write with multiple stations
    saltDF["STNNBR"] = [1, 1, 2, 2, 2]
    odf_io._salt_exporter(saltDF, outdir=str(tmp_path))
    assert Path(tmp_path / "00201_salts.csv").exists()

    # check file write with multiple casts
    saltDF["CASTNO"] = [1, 2, 1, 2, 3]
    odf_io._salt_exporter(saltDF, outdir=str(tmp_path))
    assert Path(tmp_path / "00102_salts.csv").exists()
    assert Path(tmp_path / "00202_salts.csv").exists()
    assert Path(tmp_path / "00203_salts.csv").exists()

    # check empty (all NaN) Reading# columns are dropped
    saltDF["STNNBR"], saltDF["CASTNO"] = 3, 1
    saltDF["Reading1"] = 1
    saltDF["Reading2"] = np.nan
    assert not Path(tmp_path / "00301_salts.csv").exists()
    odf_io._salt_exporter(saltDF, outdir=str(tmp_path))
    with open(Path(tmp_path / "00301_salts.csv")) as f:
        empty = pd.read_csv(f)
        assert "Reading1" in empty.columns
        assert "Reading2" not in empty.columns
