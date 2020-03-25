import pandas as pd
import numpy as np

from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.plotting import figure
from bokeh.models import (
    Button,
    ColumnDataSource,
    # CustomJS,
    DataTable,
    TableColumn,
    Select,
    MultiSelect,
    StringFormatter,  # https://docs.bokeh.org/en/latest/_modules/bokeh/models/widgets/tables.html#DataTable
)


### intialize data
df = pd.read_csv("../all_rinko_merged.csv")
df["Residual"] = df["REFOXY_rinko"] - df["CTDRINKO"]
df["Flag"] = 1
df_edited = df.copy()
ssscc_list = df["SSSCC_rinko"].unique()

### intialize widgets
button = Button(label="Save flagged data", button_type="success")
# button.js_on_click(CustomJS(args=dict(source=source),
#                             code=open(join(dirname(__file__), "download.js")).read()))
parameter = Select(
    title="Parameter", options=["CTDTMP", "CTDCOND", "SBE43", "RINKO"], value="RINKO"
)
station = Select(title="Station", options=[str(x) for x in ssscc_list], value="00101")
# explanation of flags:
# https://cchdo.github.io/hdo-assets/documentation/manuals/pdf/90_1/chap4.pdf
flag_list = MultiSelect(
    title="Plot data flagged as:",
    value=["1", "2", "3"],
    options=[
        ("1", "1 [Uncalibrated]"),
        ("2", "2 [Acceptable]"),
        ("3", "3 [Questionable]"),
        ("4", "4 [Bad]"),
    ],
)
# returns list of select options, e.g., ['2'] or ['1','2']

source_table = ColumnDataSource(data=dict())
source_plot_ssscc = ColumnDataSource(data=dict(x=[], y=[]))
source_plot_all = ColumnDataSource(data=dict(x=[], y=[]))

### set up plots
plot_ssscc = figure(
    plot_height=800,
    plot_width=400,
    title="{} vs CTDPRS [Station {}]".format(parameter.value, station.value),
    tools="crosshair,pan,reset,wheel_zoom",
    y_axis_label="Pressure (dbar)",
)
plot_all = figure(
    plot_height=800,
    plot_width=400,
    title="{} vs CTDPRS [Station {}]".format(parameter.value, station.value),
    tools="crosshair,reset,wheel_zoom",
)
plot_ssscc.y_range.flipped = True  # invert y-axis
plot_all.y_range.flipped = True  # invert y-axis
plot_all.scatter(df["REFOXY_rinko"], df["CTDPRS_rinko_ctd"])
plot_ssscc.scatter(
    "x",
    "y",
    fill_color="#999999",
    line_color="#000000",
    size=10,
    line_width=2,
    source=source_plot_ssscc,
)
plot_all.scatter(
    "x",
    "y",
    fill_color="#999999",
    line_color="#000000",
    size=10,
    line_width=2,
    source=source_plot_all,
)

parameter.on_change("value", lambda attr, old, new: update())
station.on_change("value", lambda attr, old, new: update())
flag_list.on_change("value", lambda attr, old, new: update())


def update():

    print("exec update()")

    table_rows = df_edited["SSSCC_rinko"] == int(station.value)
    plot_rows = (df_edited["SSSCC_rinko"] == int(station.value)) & (
        df_edited["Flag"].isin(flag_list.value)
    )

    current_table = df_edited[table_rows]
    current_plot = df_edited[plot_rows]

    # can this be split off into separate updates? might improve speed
    # update_param()
    # update_station()
    # update_plot_flag()
    # update flag()

    source_table.data = {  # this causes update_flag() to execute
        "SSSCC": current_table["SSSCC_rinko"],
        "CTDPRS": current_table["CTDPRS_rinko_ctd"],
        "REFOXY": current_table["REFOXY_rinko"],
        "CTDRINKO": current_table["CTDRINKO"],
        "diff": current_table["Residual"],
        "flag": current_table["Flag"],
    }
    source_plot_ssscc.data = {
        "x": current_plot["REFOXY_rinko"],
        "y": current_plot["CTDPRS_rinko_ctd"],
    }
    source_plot_all.data = {
        "x": current_plot["REFOXY_rinko"],
        "y": current_plot["CTDPRS_rinko_ctd"],
    }
    plot_ssscc.title.text = "{} vs CTDPRS [Station {}]".format(
        parameter.value, station.value
    )
    plot_all.title.text = "{} vs CTDPRS [Station {}]".format(
        parameter.value, station.value
    )
    plot_ssscc.x_range = plot_all.x_range
    plot_ssscc.y_range = plot_all.y_range


def update_flag():

    print("exec update_flag()")

    df_edited.loc[
        df_edited["SSSCC_rinko"] == source_table.data["SSSCC"][0], "Flag",
    ] = source_table.data["flag"]


columns = [
    TableColumn(
        field="SSSCC",
        title="SSSCC",
        width=40,
        formatter=StringFormatter(text_align="right"),
    ),
    TableColumn(
        field="CTDPRS",
        title="CTDPRS",
        width=80,
        formatter=StringFormatter(text_align="right"),
    ),
    TableColumn(
        field="REFOXY",
        title="REFOXY",
        width=80,
        formatter=StringFormatter(text_align="right"),
    ),
    TableColumn(
        field="CTDRINKO",
        title="CTDRINKO",
        width=80,
        formatter=StringFormatter(text_align="right"),
    ),
    TableColumn(
        field="diff",
        title="Residual",
        width=80,
        formatter=StringFormatter(text_align="right"),
    ),
    TableColumn(
        field="flag",
        title="Flag",
        width=20,
        formatter=StringFormatter(text_align="center", font_style="bold"),
    ),
]

data_table = DataTable(
    source=source_table,
    columns=columns,
    index_width=20,
    width=380 + 20,  # sum of col widths + idx width
    height=800,
    editable=True,
    fit_columns=True,
    sortable=False,
)

# TODO: build a second DataTable for points that have changed flag value

# run update() when user selects new column (may indicate new flag value)
# source_table.selected.on_change("indices", lambda attr, old, new: update_flag())
source_table.on_change("data", lambda attr, old, new: update_flag())

# TODO: highlight scatterpoint based on selected row
# source_table.selected.on_change("indices", lambda attr, old, new: update_highlight())
# source_table.selected.indices -> could likely be used to highlight point

controls = column(parameter, station, flag_list, button, width=170)

curdoc().add_root(row(controls, data_table, plot_ssscc, plot_all))
curdoc().title = "CTDO Data Flagging Tool"

update()
