"""
Invoice parser package.

This package bundles parser implementations for various telecom
providers and exposes a convenience :func:`get_parser` function to
dynamically load the appropriate parser based on the provider name.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "base_parser",
    "pdf_utils",
    "mobifone_parser",
    "viettel_parser",
    "vnpt_parser",
    "get_parser",
]


def get_parser(provider: str) -> Any:
    """Return the parser module for the specified provider.

    Parameters
    ----------
    provider : str
        Name of the telecom provider (case insensitive). Valid values
        include ``"mobifone"``, ``"viettel"`` and ``"vnpt"``.

    Returns
    -------
    module
        The parser module implementing a ``parse_pdf`` function.

    Raises
    ------
    ImportError
        If an unsupported provider name is supplied.
    """
    provider = provider.lower().strip()
    # Delegate to the parsers packaged under invoice2SAPdata.  By referencing
    # the fully qualified module names here we avoid accidentally loading
    # the placeholder parsers in this top-level package, which do not
    # support multi-invoice PDFs.  All supported providers live inside
    # the ``invoice2SAPdata`` package.
    module_map = {
        "mobifone": "invoice2SAPdata.mobifone_parser",
        "viettel": "invoice2SAPdata.viettel_parser",
        "vnpt": "invoice2SAPdata.vnpt_parser",
    }
    if provider not in module_map:
        raise ImportError(f"No parser available for provider: {provider}")
    module_name = module_map[provider]
    return import_module(module_name)