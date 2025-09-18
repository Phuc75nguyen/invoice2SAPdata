"""
Parser for Viettel post‑paid telecom invoices.

This module implements a parser for Viettel (Tập đoàn Công nghiệp –
Viễn thông Quân đội) invoices. Viettel invoices are bilingual and
present their billing information in a structured layout with clearly
labelled fields. The parser reads the PDF text using the ``extract_text``
helper from ``pdf_utils``, normalises whitespace and then extracts
the invoice serial, number, billing date and line items. Monetary
values are returned as floats after stripping thousands separators.

The parser returns a dictionary with at least these keys:

``invoice_no`` : str
    The sequential invoice number printed on the document.

``serial_no`` : str
    The series/serial code (e.g. ``"1K25DAB"``) in the top‑right corner.

``invoice_date`` : str
    The invoice issue date in ISO 8601 format (YYYY‑MM‑DD).

``lines`` : list[dict]
    A list of charge lines. Each dict contains:

    ``base_amount`` : float
        The charge before VAT.

    ``vat_rate`` : int
        The VAT percentage (e.g. 10 for 10 % VAT).

    ``vat_amount`` : float
        The VAT amount.

    ``total_amount`` : float
        The gross amount (base + VAT).

If the invoice contains repeated summary lines (e.g. "CỘNG" totals),
duplicates are automatically removed.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from base_parser import BaseInvoiceParser
from pdf_utils import extract_text


class ViettelInvoiceParser(BaseInvoiceParser):
    """Concrete parser implementation for Viettel invoices.

    Viettel invoices follow a consistent layout: the serial and
    invoice numbers appear in a small box at the top right, the
    invoice date is labelled "Ngày lập" or just "Ngày", and the
    service charges are presented in a table with columns for the
    pre‑tax amount, VAT rate, VAT amount and total. This parser uses
    regular expressions to capture these fields and normalises
    monetary values to floats.
    """

    # Patterns to extract fields. These regexes are deliberately
    # permissive to handle minor variations in spacing and punctuation.
    _serial_pattern = re.compile(r"Ký\s*hiệu\s*[:\s]\s*([A-Z0-9]+)", re.IGNORECASE)
    _number_pattern = re.compile(r"Số\s*[:\s]\s*(\d+)", re.IGNORECASE)
    # Match dates like "Ngày lập: DD/MM/YYYY" or "Ngày DD/MM/YYYY".
    _date_slash_pattern = re.compile(
        r"Ngày\s*(?:lập)?\s*[:\s]*([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})",
        re.IGNORECASE,
    )
    # Match dates like "Ngày DD tháng MM năm YYYY" (less common but possible).
    _date_text_pattern = re.compile(
        r"Ngày\s+([0-9]{1,2})\s+tháng\s+([0-9]{1,2})\s+năm\s+([0-9]{4})",
        re.IGNORECASE,
    )
    # Pattern to capture a service line: base amount, VAT %, VAT amount, total.
    # This expects four numbers separated by whitespace, with a percent sign on
    # the VAT rate. Dots are allowed as thousands separators and commas as
    # decimal separators.
    _line_pattern = re.compile(
        r"([0-9][0-9\.,]*)\s+(\d{1,2})%\s+([0-9][0-9\.,]*)\s+([0-9][0-9\.,]*)",
    )

    @staticmethod
    def _parse_number(value: str) -> float:
        """Convert a formatted monetary string into a float.

        Viettel invoices use dots as thousands separators and commas as
        decimal separators (e.g. "127.273" or "12.727"). This helper
        removes dots and converts commas to periods before casting to
        ``float``. Non‑numeric input returns ``0.0``.
        """
        # Remove non‑breaking spaces and strip surrounding whitespace
        cleaned = value.replace("\xa0", "").strip()
        # Convert comma decimal separator to a dot
        cleaned = cleaned.replace(",", ".")
        # Remove dots used as thousands separators
        cleaned = cleaned.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def parse_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        """Parse a single Viettel invoice PDF into a structured dict.

        This method reads all text from the PDF using ``extract_text``,
        normalises whitespace, and applies regex patterns to extract
        the invoice serial number, invoice number, billing date, and
        service line items. Duplicate line items (such as summary
        totals) are removed.

        Parameters
        ----------
        pdf_path : str or Path
            Path to the PDF file to parse.

        Returns
        -------
        dict
            A dictionary containing at least ``invoice_no``, ``serial_no``,
            ``invoice_date``, and ``lines`` as specified in the base
            parser class.
        """
        text = extract_text(pdf_path)
        # Collapse all sequences of whitespace into single spaces. This
        # simplifies regex matching across line breaks and multiple spaces.
        normalised = re.sub(r"\s+", " ", text)
        result: Dict[str, Any] = {
            "invoice_no": "",
            "serial_no": "",
            "invoice_date": "",
            "lines": [],
        }

        # Extract the serial number (Ký hiệu)
        serial_match = self._serial_pattern.search(normalised)
        if serial_match:
            result["serial_no"] = serial_match.group(1).strip()

        # Extract the invoice number (Số)
        number_match = self._number_pattern.search(normalised)
        if number_match:
            result["invoice_no"] = number_match.group(1).strip()

        # Extract the invoice date: try "DD/MM/YYYY" form first
        date_match = self._date_slash_pattern.search(normalised)
        if date_match:
            day, month, year = date_match.groups()
            try:
                result["invoice_date"] = date(
                    int(year), int(month), int(day)
                ).isoformat()
            except ValueError:
                # If date conversion fails, leave invoice_date blank
                result["invoice_date"] = ""
        else:
            # Fallback: try "Ngày DD tháng MM năm YYYY"
            date_match = self._date_text_pattern.search(normalised)
            if date_match:
                day, month, year = date_match.groups()
                try:
                    result["invoice_date"] = date(
                        int(year), int(month), int(day)
                    ).isoformat()
                except ValueError:
                    result["invoice_date"] = ""

        # Extract service line items
        lines: List[Dict[str, Any]] = []
        for match in self._line_pattern.finditer(normalised):
            base_raw, rate_raw, vat_raw, total_raw = match.groups()
            base_amount = self._parse_number(base_raw)
            vat_rate = int(rate_raw)
            vat_amount = self._parse_number(vat_raw)
            total_amount = self._parse_number(total_raw)
            lines.append(
                {
                    "base_amount": base_amount,
                    "vat_rate": vat_rate,
                    "vat_amount": vat_amount,
                    "total_amount": total_amount,
                }
            )

        # Deduplicate line items: some invoices repeat the values in a
        # "CỘNG" row which is identical to the service line above. Use
        # a set of tuples to filter out duplicates.
        unique: Set[Tuple[float, int, float, float]] = set()
        filtered: List[Dict[str, Any]] = []
        for line in lines:
            key = (
                line["base_amount"],
                line["vat_rate"],
                line["vat_amount"],
                line["total_amount"],
            )
            if key not in unique:
                unique.add(key)
                filtered.append(line)
        result["lines"] = filtered

        return result


def parse_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    """Parse a Viettel invoice from a PDF file path.

    This convenience function instantiates :class:`ViettelInvoiceParser`
    and delegates parsing to it, returning the structured invoice
    dictionary.

    Parameters
    ----------
    pdf_path : str or Path
        Path to the Viettel invoice PDF.

    Returns
    -------
    dict
        The structured invoice data.
    """
    parser = ViettelInvoiceParser()
    return parser.parse_pdf(pdf_path)
