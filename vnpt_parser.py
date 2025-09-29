"""
Parser for VNPT (Tổng công ty Dịch vụ Viễn thông) VAT invoices.

VNPT invoices follow a relatively structured format. Key fields such
as the serial number (``Ký hiệu``), invoice number (``Số``) and
invoice date (``Ngày ... Tháng ... Năm ...``) appear near the top of
the document. Charge details are summarised near the bottom with
labels like ``Cộng tiền hàng`` (total before tax), ``Thuế suất thuế
GTGT`` (VAT rate), ``Tiền thuế GTGT`` (VAT amount) and ``Tổng cộng
tiền thanh toán`` (grand total).

This module implements a parser that extracts these fields and
returns a normalised dictionary. Monetary values printed with dot
thousand separators and comma decimals (e.g. ``47.272`` or
``4.727``) are converted to floats. If any field cannot be found,
the corresponding value is left blank or set to zero. Each invoice
produces a single line item in the returned ``lines`` list because
VNPT bills generally summarise charges in a single row.

The structured representation returned has the following keys:

``invoice_no`` : str
    Sequential number of the invoice (the ``Số`` field).

``serial_no`` : str
    The invoice serial code from the ``Ký hiệu`` field.

``invoice_date`` : str
    The invoice date formatted as ISO 8601 (YYYY‑MM‑DD).

``lines`` : list[dict]
    A list containing one dict with the keys ``base_amount``,
    ``vat_rate``, ``vat_amount`` and ``total_amount``. These map to
    ``Cộng tiền hàng``, ``Thuế suất thuế GTGT``, ``Tiền thuế GTGT``
    and ``Tổng cộng tiền thanh toán`` respectively.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict

from base_parser import BaseInvoiceParser
from pdf_utils import extract_text


class VNPTInvoiceParser(BaseInvoiceParser):
    """Concrete parser implementation for VNPT invoices.

    This parser has been enhanced to cope with VNPT invoices where the
    summary monetary figures (base amount, VAT rate, VAT amount and
    total payment) are not printed on the same lines as their labels.

    Earlier iterations of this parser looked for numbers directly
    following the labels ``Cộng tiền hàng``, ``Thuế suất thuế GTGT``,
    ``Tiền thuế GTGT`` and ``Tổng cộng tiền thanh toán``. However, on
    some invoices these labels appear on separate lines from their
    corresponding numbers, causing the simple patterns to fail and
    returning an empty ``lines`` list. To make the parser more robust,
    we now capture the first instance of the base amount, VAT rate,
    VAT amount and total payment by looking for a block of numbers
    surrounding the ``Thuế suất thuế GTGT`` line. In practice, the
    number immediately preceding the ``VAT rate`` line is the base
    amount, while the next two numbers are the VAT amount and the
    grand total. This pattern reliably matches VNPT invoice
    summaries in the wild.
    """

    # Pattern to capture the invoice serial (Ký hiệu)
    # Pattern to capture the invoice serial (Ký hiệu).
    # VNPT invoices often include an English translation in parentheses,
    # e.g. "Ký hiệu (Serial): 1K25THA". Allow any optional parentheses
    # after the Vietnamese label before the colon or whitespace.
    _serial_pattern = re.compile(
        r"Ký\s*hiệu\s*(?:\([^)]*\))?[^:\n]*[:\s]+([A-Z0-9]+)",
        re.IGNORECASE,
    )
    # Pattern to capture the invoice number (Số). Similar to serial,
    # handle optional parentheses such as "Số (No.): 3802879".
    _number_pattern = re.compile(
        r"Số\s*(?:\([^)]*\))?[^:\n]*[:\s]+(\d+)",
        re.IGNORECASE,
    )
    # Pattern to capture the invoice date in the header: Ngày (Date) DD Tháng (Month) MM Năm (Year) YYYY
    _date_pattern = re.compile(
        r"Ngày[^0-9]*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{4})",
        re.IGNORECASE,
    )
    # Patterns to capture summary lines at the bottom of the invoice
    _base_amount_pattern = re.compile(
        r"Cộng\s+tiền\s+hàng[^:]*[:\s]*([0-9][0-9\.,]*)",
        re.IGNORECASE,
    )
    _vat_rate_pattern = re.compile(
        r"Thuế\s+suất\s+thuế\s+GTGT[^:]*[:\s]*([0-9]{1,2})%?",
        re.IGNORECASE,
    )
    _vat_amount_pattern = re.compile(
        r"Tiền\s+thuế\s+GTGT[^:]*[:\s]*([0-9][0-9\.,]*)",
        re.IGNORECASE,
    )
    _total_amount_pattern = re.compile(
        r"Tổng\s+cộng\s+tiền\s+thanh\s+toán[^:]*[:\s]*([0-9][0-9\.,]*)",
        re.IGNORECASE,
    )

    # Pattern to capture a block of summary numbers. This matches four
    # numbers in order: base amount, VAT rate, VAT amount and total
    # amount. The base amount is immediately followed by a ``Thuế suất
    # thuế GTGT`` line containing the VAT rate, then the next two
    # numeric tokens are the VAT amount and the grand total. This
    # pattern uses a reluctant match for the text between the VAT rate
    # and the following numbers to avoid consuming too much. See
    # ``parse_pdf`` for how this is used.
    _amount_block_pattern = re.compile(
        r"([0-9][0-9\.,]*)\s+Thuế\s+suất\s+thuế\s+GTGT[^0-9]*([0-9]{1,2})%.*?([0-9][0-9\.,]*)\s+([0-9][0-9\.,]*)",
        re.IGNORECASE,
    )

    @staticmethod
    def _parse_number(value: str) -> float:
        """Convert a formatted monetary string into a float.

        Dots used as thousand separators are removed and commas are
        converted to decimal points. If parsing fails, returns 0.0.

        Parameters
        ----------
        value : str
            A numeric string such as ``"47.272"`` or ``"4.727"``.

        Returns
        -------
        float
            The numeric value of the string.
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

        Parameters
        ----------
        pdf_path : str or Path
            Path to the VNPT invoice PDF.

        Returns
        -------
        dict
            A dictionary with keys ``invoice_no``, ``serial_no``,
            ``invoice_date`` and ``lines``.
        """
        text = extract_text(pdf_path)
        # Collapse multiple whitespace characters to a single space for easier matching
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
                result["invoice_date"] = date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                result["invoice_date"] = ""
        # Summary monetary values. VNPT invoices sometimes place the
        # amounts on separate lines before or after their labels. To
        # robustly capture these numbers we first attempt to locate a
        # block of four tokens around the "Thuế suất thuế GTGT" line.
        base_amount = 0.0
        vat_rate = 0
        vat_amount = 0.0
        total_amount = 0.0
        block_match = self._amount_block_pattern.search(normalised)
        if block_match:
            # Parse each captured token
            base_amount = self._parse_number(block_match.group(1))
            vat_rate = int(block_match.group(2)) if block_match.group(2) else 0
            vat_amount = self._parse_number(block_match.group(3))
            total_amount = self._parse_number(block_match.group(4))
        else:
            # Fallback to original patterns if the block pattern fails
            base_match = self._base_amount_pattern.search(normalised)
            vat_rate_match = self._vat_rate_pattern.search(normalised)
            vat_amount_match = self._vat_amount_pattern.search(normalised)
            total_match = self._total_amount_pattern.search(normalised)
            base_amount = self._parse_number(base_match.group(1)) if base_match else 0.0
            vat_rate = int(vat_rate_match.group(1)) if vat_rate_match else 0
            vat_amount = self._parse_number(vat_amount_match.group(1)) if vat_amount_match else 0.0
            total_amount = self._parse_number(total_match.group(1)) if total_match else 0.0
        # Append a line item if we found at least one monetary value
        if any([base_amount, vat_amount, total_amount]):
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
    """Module‑level convenience function to parse a VNPT invoice.

    Instantiates a :class:`VNPTInvoiceParser` and delegates the
    parsing to its :meth:`parse_pdf` method.

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