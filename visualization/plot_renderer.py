from __future__ import annotations

from typing import Any

import plotly.express as px


CHART_RENDER_MAP = {
    "line": "line_chart",
    "line_chart": "line_chart",
    "bar": "bar_chart",
    "bar_chart": "bar_chart",
    "histogram": "histogram",
    "scatter": "scatter_plot",
    "scatter_plot": "scatter_plot",
}


class PlotRenderer:
    def render(self, df, spec: dict[str, Any] | None):
        if spec is None or df.empty:
            return None
        chart_type = spec.get("chart_type", "table")
        render_type = CHART_RENDER_MAP.get(chart_type, chart_type)
        x = spec.get("x")
        y = spec.get("y")
        color = spec.get("color")
        title = spec.get("title", "Chart")
        if x and x not in df.columns:
            return None
        if y and y not in df.columns:
            return None
        try:
            if render_type == "line_chart" and x in df.columns and y in df.columns:
                return px.line(df, x=x, y=y, color=color if color in df.columns else None, title=title)
            if render_type == "bar_chart" and x in df.columns and y in df.columns:
                return px.bar(df, x=x, y=y, color=color if color in df.columns else None, title=title)
            if render_type == "histogram" and x in df.columns:
                return px.histogram(df, x=x, title=title)
            if render_type == "scatter_plot" and x in df.columns and y in df.columns:
                return px.scatter(df, x=x, y=y, color=color if color in df.columns else None, title=title)
        except Exception:
            return None
        return None
