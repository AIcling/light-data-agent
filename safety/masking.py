from __future__ import annotations

import pandas as pd


def mask_sensitive_dataframe(df: pd.DataFrame, sensitive_columns: list[str]) -> pd.DataFrame:
    if not sensitive_columns:
        return df
    masked = df.copy()
    for column in sensitive_columns:
        if column in masked.columns:
            masked[column] = masked[column].astype(str).str.replace(r"(.{2}).*(.{2})", r"\1***\2", regex=True)
    return masked
