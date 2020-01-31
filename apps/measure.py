import logging
import urllib
from itertools import cycle

import pandas as pd
import plotly.graph_objs as go
from dash.dependencies import Input, Output, State
import dash_core_components as dcc

import numpy as np
from app import app
from apps.base import get_sorted_group_keys
from apps.base import (
    get_title_fragment,
    humanise_list,
    humanise_result_filter,
    humanise_column_name,
    initial_capital,
)
from data import humanise_entity_name
from data import get_count_data
from stateful_routing import get_state
import settings


logger = logging.getLogger(__name__)


DISPLAY_NONE = {"display": "none"}
DISPLAY_SHOW = {"display": ""}

EMPTY_RESPONSE = (settings.EMPTY_CHART_LAYOUT, DISPLAY_NONE, "")


def get_deciles(df):
    """Compute deciles across `calc_value` for each month.

    Returns a list of (decile, value) tuples (e.g. (10, 4.223))
    """
    deciles = np.array(range(10, 100, 10))
    vals_by_month = df.pivot(columns="month", values="calc_value")
    deciles_data = np.nanpercentile(vals_by_month, axis=0, q=deciles)
    return zip(deciles, deciles_data)


def get_decile_traces(df, col_name):
    """Return a set of `Scatter` traces  suitable for adding to a Dash figure
    """
    deciles_traces = []
    months = pd.to_datetime(df["month"].unique())
    legend_text = (
        f"Deciles over all<br>available {humanise_column_name(col_name)}<br>nationally"
    )
    showlegend = True
    for n, decile in get_deciles(df):
        style = "dash" if n == 50 else "dot"
        deciles_traces.append(
            go.Scatter(
                x=months,
                y=decile,
                legendgroup="deciles",
                name=legend_text,
                line=dict(color=settings.DECILE_COLOUR, width=1, dash=style),
                hoverinfo="skip",
                showlegend=showlegend,
            )
        )
        # Only show legend for first decile trace
        showlegend = False
    return deciles_traces


@app.callback(
    Output("measure-container", "children"),
    [Input("page-state", "children")],
    [State("url-for-update", "search")],
)
def update_measures(page_state, current_qs):
    query_string = urllib.parse.parse_qs(current_qs[1:])
    page_state = get_state(page_state)
    if page_state.get("page_id") != settings.MEASURE_ID:
        return []
    measures = [
        {
            "id": 1,
            "numerators": ["CREA"],
            "denominators": ["CREA", "ESR", "PV"],
            "result_filter": "all",
            "groupby": "practice_id",
            "ccg_ids_for_practice_filter": ["all"],
            "lab_ids_for_practice_filter": ["all"],
            "sparse_data_toggle": True,
        },
        {
            "id": 2,
            "numerators": ["K"],
            "denominators": ["per1000"],
            "result_filter": "all",
            "groupby": "practice_id",
            "ccg_ids_for_practice_filter": ["all"],
            "lab_ids_for_practice_filter": ["all"],
            "sparse_data_toggle": True,
        },
        {
            "id": 3,
            "numerators": ["TSH"],
            "denominators": ["per1000"],
            "result_filter": "all",
            "groupby": "practice_id",
            "ccg_ids_for_practice_filter": ["all"],
            "lab_ids_for_practice_filter": ["all"],
            "sparse_data_toggle": True,
        },
        {
            "id": 4,
            "numerators": ["TSH"],
            "denominators": ["TSH"],
            "result_filter": "under_range",
            "groupby": "practice_id",
            "ccg_ids_for_practice_filter": ["all"],
            "lab_ids_for_practice_filter": ["all"],
            "sparse_data_toggle": True,
        },
    ]
    charts = []
    for measure in measures:
        numerators = measure["numerators"]
        denominators = measure["denominators"]
        result_filter = measure["result_filter"]
        groupby = measure["groupby"]
        col_name = measure["groupby"]

        trace_df = get_count_data(
            numerators=measure["numerators"],
            denominators=measure["denominators"],
            result_filter=measure["result_filter"],
            lab_ids_for_practice_filter=measure["lab_ids_for_practice_filter"],
            ccg_ids_for_practice_filter=measure["ccg_ids_for_practice_filter"],
            by=col_name,
            hide_entities_with_sparse_data=measure["sparse_data_toggle"],
        )
        if trace_df.empty:
            return EMPTY_RESPONSE

        # Don't show deciles in cases where they don't make sense
        if len(trace_df[col_name].unique()) < 10 or groupby == "result_category":
            show_deciles = False
        else:
            show_deciles = True

        traces = get_decile_traces(trace_df, col_name) if show_deciles else []

        # If we're showing deciles then get the IDs of the highlighted entities so
        # we can display them
        if show_deciles:
            highlight_entities = query_string.get("highlight_entities", [])
            entity_ids = get_sorted_group_keys(
                trace_df[trace_df[col_name].isin(highlight_entities)], col_name
            )
        # If we're not showing deciles then we want to display all entities
        # automatically
        else:
            entity_ids = get_sorted_group_keys(trace_df, col_name)

        has_error_bars = False
        for colour, entity_id in zip(cycle(settings.LINE_COLOUR_CYCLE), entity_ids):
            entity_df = trace_df[trace_df[col_name] == entity_id]
            # First, plot the practice line
            traces.append(
                go.Scatter(
                    legendgroup=entity_id,
                    x=entity_df["month"],
                    y=entity_df["calc_value"],
                    text=entity_df["label"],
                    hoverinfo="text",
                    name=humanise_entity_name(col_name, entity_id),
                    line_width=2,
                    line=dict(color=colour, width=1, dash="solid"),
                )
            )
            if entity_df["calc_value_error"].sum() > 0:
                has_error_bars = True
                # If there's any error, bounds and fill
                traces.append(
                    go.Scatter(
                        legendgroup=entity_id,
                        x=entity_df["month"],
                        y=entity_df["calc_value"] + entity_df["calc_value_error"],
                        name=str(entity_id),
                        line=dict(color=colour, width=1, dash="dot"),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
                traces.append(
                    go.Scatter(
                        legendgroup=entity_id,
                        x=entity_df["month"],
                        y=entity_df["calc_value"] - entity_df["calc_value_error"],
                        name=str(entity_id),
                        fill="tonexty",
                        line=dict(color=colour, width=1, dash="dot"),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

        fragment = get_title_fragment(numerators, denominators, result_filter)

        if show_deciles and entity_ids:
            fragment = initial_capital(fragment)
            if col_name == "test_code":
                title = get_title_fragment(entity_ids, denominators, result_filter)
            elif col_name == "result_category":
                category_list = humanise_list(
                    [humanise_result_filter(x) for x in entity_ids]
                )
                title = f"{fragment} {category_list}"
            else:
                entity_desc = humanise_column_name(
                    col_name, plural=len(entity_ids) != 1
                )
                title = f"{fragment} at {entity_desc} {humanise_list(entity_ids)}"
            title += f"<br>(with deciles over all {humanise_column_name(col_name)})"
        elif show_deciles and not entity_ids:
            title = f"Deciles for {fragment} over all {humanise_column_name(col_name)}"
        else:
            fragment = initial_capital(fragment)
            title = (
                f"{fragment} grouped by {humanise_column_name(col_name, plural=False)}"
            )

        annotations = []
        if has_error_bars:
            annotations.append(
                go.layout.Annotation(
                    text=(
                        "* coloured bands indicate uncertainty due to suppression of "
                        'low numbers (<a href="/faq#low-numbers">see FAQ</a>)'
                    ),
                    font={"color": "#6c757d"},
                    xref="paper",
                    xanchor="right",
                    x=1,
                    xshift=120,
                    yref="paper",
                    yanchor="top",
                    y=0,
                    yshift=-26,
                    showarrow=False,
                )
            )

        all_x_vals = set().union(*[trace.x for trace in traces])

        figure = {
            "data": traces,
            "layout": go.Layout(
                title=title,
                height=350,
                xaxis={"range": [min(all_x_vals), max(all_x_vals)]},
                showlegend=True,
                legend={"orientation": "v"},
                annotations=annotations,
            ),
        }
        charts.append(dcc.Graph(id=str(measure["id"]), figure=figure))
    print("XXXXXXXXXXXXXXXXXXXXXXXX {}".format(len(charts)))
    return charts