from __future__ import annotations

import io
import re
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from core.types import LoadedDataset


def normalize_identifier(value: str, fallback: str = "table") -> str:
    normalized = re.sub(r"\W+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        normalized = fallback
    if normalized[0].isdigit():
        normalized = f"{fallback}_{normalized}"
    return normalized


def _dedupe_columns(columns: list[str]) -> tuple[list[str], dict[str, str]]:
    seen: dict[str, int] = {}
    normalized_columns: list[str] = []
    mapping: dict[str, str] = {}
    for original in columns:
        base = normalize_identifier(str(original), "column")
        count = seen.get(base, 0)
        seen[base] = count + 1
        normalized = base if count == 0 else f"{base}_{count + 1}"
        normalized_columns.append(normalized)
        mapping[str(original)] = normalized
    return normalized_columns, mapping


class CSVLoader:
    def load(
        self,
        source: str | Path | bytes | BinaryIO,
        table_name: str | None = None,
        filename: str | None = None,
    ) -> LoadedDataset:
        original_filename = filename or self._filename_from_source(source)
        inferred_table = normalize_identifier(Path(original_filename).stem, "data")
        final_table_name = normalize_identifier(table_name or inferred_table, "data")
        df = self._read_csv(source)
        df = self._normalize_dataframe(df)
        column_mapping = getattr(df, "_column_mapping", {})
        return LoadedDataset(
            table_name=final_table_name,
            dataframe=df,
            original_filename=original_filename,
            column_mapping=column_mapping,
        )

    def _filename_from_source(self, source: str | Path | bytes | BinaryIO) -> str:
        if isinstance(source, (str, Path)):
            return Path(source).name
        if hasattr(source, "name"):
            return str(getattr(source, "name"))
        return "uploaded.csv"

    def _read_csv(self, source: str | Path | bytes | BinaryIO) -> pd.DataFrame:
        if isinstance(source, (str, Path)):
            last_error: Exception | None = None
            for encoding in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    return pd.read_csv(source, sep=None, engine="python", encoding=encoding)
                except UnicodeDecodeError as exc:
                    last_error = exc
            raise ValueError(f"Could not decode CSV file: {last_error}") from last_error

        raw = source if isinstance(source, bytes) else source.read()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return pd.read_csv(
                    io.BytesIO(raw),
                    sep=None,
                    engine="python",
                    encoding=encoding,
                )
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f"Could not decode CSV upload: {last_error}") from last_error

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty and len(df.columns) == 0:
            raise ValueError("CSV file has no columns.")
        normalized_columns, mapping = _dedupe_columns([str(c) for c in df.columns])
        df = df.copy()
        df.columns = normalized_columns
        for column in df.columns:
            if self._looks_like_date_column(column):
                parsed = pd.to_datetime(df[column], errors="coerce")
                parse_rate = parsed.notna().mean() if len(parsed) else 0
                if parse_rate >= 0.75:
                    df[column] = parsed
        df._column_mapping = mapping  # type: ignore[attr-defined]
        return df

    def _looks_like_date_column(self, column: str) -> bool:
        lowered = column.lower()
        return any(token in lowered for token in ("date", "time", "day", "month", "year"))
