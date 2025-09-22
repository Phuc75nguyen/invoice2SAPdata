"""
Excel export utilities.

This module provides a single entry point ``export_rows_to_excel``
that accepts an iterable of dictionaries (ledger rows) and produces
an in-memory Excel workbook containing the data. Returning the
workbook as a ``BytesIO`` object allows callers such as a
Streamlit application to embed the file directly in a download
button without having to manage temporary files on disk. Should a
file path be provided, the function will also write the file to
disk to support batch or command-line usage. The columns of the
Excel file are taken from the keys of the first row in the input
sequence to ensure a consistent ordering.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Union

import pandas as pd


def export_rows_to_excel(
    rows: Iterable[Mapping[str, object]],
    output_path: Union[str, Path, None] = None,
    sheet_name: str = "Sheet1",
    index: bool = False,
) -> io.BytesIO:
    """Create an Excel workbook from an iterable of ledger rows.

    Given a list (or other iterable) of dictionaries representing
    accounting journal entries, this function constructs a pandas
    ``DataFrame`` with a stable column order and writes it into an
    Excel file. By default, the file is written into an in-memory
    ``BytesIO`` object and returned to the caller. If ``output_path``
    is provided, the workbook will also be persisted to that location
    on disk. Callers such as Streamlit can pass the resulting
    ``BytesIO`` directly to a download button.

    Parameters
    ----------
    rows : iterable of mapping
        Each element should be a mapping (e.g. dict) keyed by column
        names. All rows should contain the same set of keys.

    output_path : str or Path or None, optional
        If supplied, the generated workbook will additionally be written
        to this location. Parent directories will be created as
        necessary. If omitted or ``None``, the workbook is only
        returned in-memory.

    sheet_name : str, optional
        Name of the worksheet. Defaults to "Sheet1".

    index : bool, optional
        Whether to include the DataFrame index in the output file.

    Returns
    -------
    io.BytesIO
        A bytes buffer containing the Excel file content.
    """
    # Prepare an output buffer regardless of whether we also write to disk.
    output = io.BytesIO()

    # Try to fetch the first row. If there are no rows, still generate a valid
    # workbook. Without writing at least a blank worksheet, callers like
    # Streamlit will receive a zero‑byte file that Excel cannot open.
    iterator = iter(rows)
    try:
        first_row = next(iterator)
    except StopIteration:
        # Write an empty DataFrame into the workbook to ensure the file
        # structure is valid. Even with no data, this creates a sheet
        # that Excel can open.
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=index)
        # If a disk path is provided, persist the blank workbook there
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                f.write(output.getvalue())
        # Reset buffer before returning
        output.seek(0)
        return output

    # Convert to DataFrame, preserving column order based on first row
    columns: Sequence[str] = list(first_row.keys())
    df = pd.DataFrame([first_row, *iterator], columns=columns)

    # Write to the in-memory buffer using openpyxl engine
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=index)

    # Optionally write to disk
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(output.getvalue())

    # Reset buffer position for reading
    output.seek(0)
    return output