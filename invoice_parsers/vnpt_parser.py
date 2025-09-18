"""
Parser for VNPT value‑added tax invoices (Hóa đơn GTGT).

This module implements a parser for VNPT invoices. VNPT invoices are
structured documents with clearly labelled sections for the invoice
serial number, invoice number and date, as well as a table and
summary lines describing the charges. Unlike some telecom invoices,
VNPT bills do not always list the VAT rate and VAT amount alongside
each service line in the table; instead, a summary near the bottom
provides the VAT rate, VAT amount and the total amount due. The
parser extracts these fields and returns them in a normalised
structure for further processing.

The returned dictionary includes the following mandatory keys:

``invoice_no`` : str
    Sequential number of the invoice (the "Số" field).

``serial_no`` : str
    The invoice serial code (e.g. ``"1K25THA"``) from the "Ký hiệu" field.

``invoice_date`` : str
    The invoice date formatted as ISO 8601 (YYYY‑MM‑DD).

``lines`` : list[dict]
    A list of line items. Each line contains:

    ``base_amount`` : float
        The total charge before VAT (Cộng tiền hàng).

    ``vat_rate`` : int
        The VAT rate percentage (Thuế suất thuế GTGT), typically 0 or 10.

    ``vat_amount`` : float
        The VAT amount (Tiền thuế GTGT).

    ``total_amount`` : float
        The grand total including VAT (Tổng cộng tiền thanh toán).

If the invoice contains multiple charge lines with different VAT rates
or amounts, the parser may need to be extended to capture each one
individually. For single‑line invoices, extracting the summary
values suffices.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from base_parser import BaseInvoiceParser
from pdf_utils import extract_text


class VNPTInvoiceParser(BaseInvoiceParser):
    """Concrete parser implementation for VNPT invoices.

    VNPT invoices have the serial number (Ký hiệu) and invoice number (Số)
    in a box on the top right of the document. The invoice date is given
    in the form "Ngày (Date) DD Tháng (Month) MM Năm (Year) YYYY" at the
    top. Charge details appear in a table and are summarised near the
    bottom with lines such as "Cộng tiền hàng", "Thuế suất thuế GTGT",
    "Tiền thuế GTGT" and "Tổng cộng tiền thanh toán". This parser
    normalises the text and uses regular expressions to extract these
    values.
    """

    # Pattern to capture the invoice serial (Ký hiệu)
    _serial_pattern = re.compile(r"Ký\s*hiệu\s*[:\s]+([A-Z0-9]+)", re.IGNORECASE)
    # Pattern to capture the invoice number (Số)
    _number_pattern = re.compile(r"Số\s*[:\s]+(\d+)", re.IGNORECASE)
    # Pattern to capture date in the header: Ngày (Date) DD Tháng (Month) MM Năm (Year) YYYY
    _date_pattern = re.compile(
        r"Ngày[^0-9]*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{4})",
        re.IGNORECASE,
    )
    # Patterns to capture summary lines at the bottom of the invoice
    _base_amount_pattern = re.compile(
        r"Cộng\s+tiền\s+hàng[^:]*:\s*([0-9][0-9\.,]*)", re.IGNORECASE
    )
    _vat_rate_pattern = re.compile(
        r"Thuế\s+suất\s+thuế\s+GTGT[^:]*:\s*(\d{1,2})%?", re.IGNORECASE
    )
    _vat_amount_pattern = re.compile(
        r"Tiền\s+thuế\s+GTGT[^:]*:\s*([0-9][0-9\.,]*)", re.IGNORECASE
    )
    _total_amount_pattern = re.compile(
        r"Tổng\s+cộng\s+tiền\s+thanh\s+toán[^:]*:\s*([0-9][0-9\.,]*)", re.IGNORECASE
    )

    @staticmethod
    def _parse_number(value: str) -> float:
        """Convert a formatted monetary string into a float.

        VNPT invoices use dots as thousands separators and commas as
        decimal separators (e.g. "47.272" or "4.727"). This helper
        removes dots and converts commas to periods before casting to
        ``float``. If conversion fails, returns ``0.0``.
        """
        cleaned = value.replace("\xa0", "").strip()
        cleaned = cleaned.replace(",", ".")
        cleaned = cleaned.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def parse_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        """Parse a single VNPT invoice PDF into a structured dict.

        Reads the PDF text, normalises whitespace and extracts the
        invoice serial, number, date and monetary values from the
        summary lines. If some fields cannot be found, their values
        remain empty or zero as appropriate.

        Parameters
        ----------
        pdf_path : str or Path
            Path to the PDF file to parse.

        Returns
        -------
        dict
            A dictionary containing the extracted invoice data with keys
            ``invoice_no``, ``serial_no``, ``invoice_date`` and
            ``lines``.
        """
        text = extract_text(pdf_path)
        # Normalise whitespace: collapse multiple whitespace characters into a single space.
        normalised = re.sub(r"\s+", " ", text)
        result: Dict[str, Any] = {
            "invoice_no": "",
            "serial_no": "",
            "invoice_date": "",
            "lines": [],
        }

        # Serial number
        serial_match = self._serial_pattern.search(normalised)
        if serial_match:
            result["serial_no"] = serial_match.group(1).strip()

        # Invoice number
        number_match = self._number_pattern.search(normalised)
        if number_match:
            result["invoice_no"] = number_match.group(1).strip()

        # Invoice date
        date_match = self._date_pattern.search(normalised)
        if date_match:
            day, month, year = date_match.groups()
            try:
                result["invoice_date"] = date(
                    int(year), int(month), int(day)
                ).isoformat()
            except ValueError:
                result["invoice_date"] = ""

        # Extract summary monetary values
        base_match = self._base_amount_pattern.search(normalised)
        vat_rate_match = self._vat_rate_pattern.search(normalised)
        vat_amount_match = self._vat_amount_pattern.search(normalised)
        total_match = self._total_amount_pattern.search(normalised)

        base_amount = self._parse_number(base_match.group(1)) if base_match else 0.0
        vat_rate = int(vat_rate_match.group(1)) if vat_rate_match else 0
        vat_amount = self._parse_number(vat_amount_match.group(1)) if vat_amount_match else 0.0
        total_amount = self._parse_number(total_match.group(1)) if total_match else 0.0

        # If we found at least one monetary value, add a line item
        if base_match or vat_amount_match or total_match:
            result["lines"].append(
                {
                    "base_amount": base_amount,
                    "vat_rate": vat_rate,
                    "vat_amount": vat_amount,
                    "total_amount": total_amount,
                }
            )

        return result


def parse_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    """Parse a VNPT invoice from a PDF file path.

    Instantiates :class:`VNPTInvoiceParser` and delegates the parsing
    work to it. Returns the structured invoice dictionary.

    Parameters
    ----------
    pdf_path : str or Path
        Path to the VNPT invoice PDF.

    Returns
    -------
    dict
        Parsed invoice data.
    """
    parser = VNPTInvoiceParser()
    return parser.parse_pdf(pdf_path)
