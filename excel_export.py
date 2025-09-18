"""
Excel export utilities.

After transforming invoice data into a list of ledger rows using the
functions in :mod:`transform`, the rows can be persisted into an
Excel file using :func:`export_rows_to_excel`. The export will
preserve column ordering and optionally write to an existing template
workbook if needed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence, Mapping

import pandas as pd


def export_rows_to_excel(
    rows: Iterable[Mapping[str, object]],
    output_path: str | Path,
    sheet_name: str = "Sheet1",
    index: bool = False,
) -> None:
    """Write ledger rows into an Excel workbook.

    Parameters
    ----------
    rows : iterable of mappings
        Each element should be a mapping (e.g. dict) keyed by column
        names. All rows should contain the same set of keys.

    output_path : str or Path
        Location to write the Excel file. Parent directories will be
        created if necessary.

    sheet_name : str, optional
        Name of the worksheet. Defaults to "Sheet1".

    index : bool, optional
        Whether to include the DataFrame index in the output file.

    Returns
    -------
    None
        The file is written to disk as a side effect.
    """
    output_path = Path(output_path)
    if not rows:
        # Nothing to write
        return
    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Convert to DataFrame, preserving column order from the first row
    first_row = next(iter(rows))
    columns: Sequence[str] = list(first_row.keys())
    df = pd.DataFrame(rows, columns=columns)
    df.to_excel(output_path, sheet_name=sheet_name, index=index, engine="openpyxl")