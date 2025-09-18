"""
Invoice to SAP Data Extraction Package
This package provides utilities to extract data from telecom invoice PDFs and
convert them into a structured format suitable for import into SAP.

Modules
=======

``pdf_utils``
    Low‑level helpers to extract text from PDF documents.

``mobifone_parser``
    Parser for invoices issued by the Mobifone service provider.

``viettel_parser``
    Parser for invoices issued by the Viettel service provider (placeholder).

``vnpt_parser``
    Parser for invoices issued by the VNPT service provider (placeholder).

``transform``
    Functions to map extracted invoice data into SAP journal entries.

``excel_export``
    Helpers to persist the structured data into Excel files.

``app``
    Example Streamlit application demonstrating how to combine the
    parsers, transformation logic and Excel export in an interactive UI.

This package is designed to be modular: each provider’s invoice format is
encapsulated in its own parser so that adding support for additional
providers simply requires implementing a new parser module that outputs
data in the same intermediate schema.
"""

from importlib import import_module

__all__ = [
    "pdf_utils",
    "mobifone_parser",
    "viettel_parser",
    "vnpt_parser",
    "transform",
    "excel_export",
    "app",
]

def get_parser(provider: str):
    """Dynamically load a parser module for the given provider.

    Parameters
    ----------
    provider: str
        Name of the telecom service provider (case insensitive).

    Returns
    -------
    module
        A module implementing a ``parse_pdf`` function for the provider.

    Raises
    ------
    ImportError
        If no parser exists for the specified provider.
    """
    provider = provider.lower().strip()
    if provider not in ("mobifone", "viettel", "vnpt"):
        raise ImportError(f"No parser implemented for provider: {provider}")
    return import_module(f"invoice2SAPdata.{provider}_parser")