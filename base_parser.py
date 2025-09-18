"""
Abstract base class for invoice parsers.

Invoice parsers transform raw PDF documents into a structured
representation. Each parser handles the idiosyncratic layout and
terminology of a single service provider's invoices. They should
inherit from ``BaseInvoiceParser`` and implement the :meth:`parse_pdf`
method. Parsers should not perform any business logic beyond
extracting factual data from the document. Transformation into
accounting journal entries belongs in the ``transform`` module.

The structured representation returned by :meth:`parse_pdf` is a
dictionary with at least the following keys:

``invoice_no`` : str
    The unique sequential number of the invoice.

``serial_no`` : str
    The series or serial code printed on the invoice (e.g. "1K25DAA").

``invoice_date`` : str
    The billing date of the invoice, in ISO format (YYYY‑MM‑DD).

``lines`` : list[dict]
    A list of line items. Each dict must contain:

    ``base_amount`` : float
        The service charge before VAT.

    ``vat_rate`` : int
        The VAT percentage (e.g. 10 for 10% VAT).

    ``vat_amount`` : float
        The VAT amount (not including the base).

    ``total_amount`` : float
        The gross amount (base + VAT).

Additional keys may be present depending on the provider, but the
above keys are required for the transformation layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class BaseInvoiceParser(ABC):
    """Base class for all invoice parsers.

    Subclasses must implement :meth:`parse_pdf` to return structured
    invoice data. Parsers should be stateless; all required
    configuration should be passed explicitly via method arguments or
    class initialisers.
    """

    @abstractmethod
    def parse_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        """Parse a single PDF invoice into a structured dict.

        Parameters
        ----------
        pdf_path : str or Path
            Path to the PDF file to parse.

        Returns
        -------
        dict
            The structured representation of the invoice. See class
            documentation for the required keys.
        """
        raise NotImplementedError