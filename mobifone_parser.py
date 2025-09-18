"""
Parser for Mobifone post‑paid telecom invoices.

Mobifone invoices are bilingual (Vietnamese and English) and display
most critical information in a tabular format. The parser makes a
best‑effort attempt to locate the invoice number, series, date and
monetary amounts using regular expressions. If some fields cannot be
found, empty strings will be returned for those fields.

Numbers printed on invoices typically use a dot as the thousands
separator (e.g. "44.545" for forty‑four thousand five hundred and
forty‑five). This parser removes all separators before converting
amounts to floats.

This implementation is intentionally conservative: it is designed to
fail gracefully rather than throw exceptions if a pattern is not
matched. Caller code should validate the returned dictionary and
handle missing fields appropriately.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from .base_parser import BaseInvoiceParser
from .pdf_utils import extract_text


class MobifoneInvoiceParser(BaseInvoiceParser):
    """Concrete parser implementation for Mobifone invoices."""

    # Regular expressions to extract key fields
    _serial_pattern = re.compile(r"Ký\s*hiệu[^:]*[:\s]\s*([A-Z0-9]{4,})", re.IGNORECASE)
    _number_pattern = re.compile(r"Số\s*(?:\(No\.\))?[^:]*[:\s]\s*(\d+)", re.IGNORECASE)
    _date_pattern = re.compile(
        r"Ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE
    )
    # Pattern matching a service line: base amount, VAT %, VAT amount, total
    _line_pattern = re.compile(
        r"([0-9][0-9\.,]*)\s+(\d{1,2})%\s+([0-9][0-9\.,]*)\s+([0-9][0-9\.,]*)"
    )

    @staticmethod
    def _parse_number(value: str) -> float:
        """Convert a formatted monetary string into a float.

        Parameters
        ----------
        value : str
            The monetary amount as printed on the invoice. Dots and commas
            used as thousands separators will be stripped. Commas used as
            decimal separators will be converted to a dot before
            conversion.

        Returns
        -------
        float
            The numeric value of the amount.
        """
        # Remove spaces
        cleaned = value.replace("\xa0", "").strip()
        # Replace any comma decimal separator with a dot
        cleaned = cleaned.replace(",", ".")
        # Remove thousands separators (periods)
        cleaned = cleaned.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def parse_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        text = extract_text(pdf_path)
        # Remove excessive whitespace and unify separators
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
        # Date
        date_match = self._date_pattern.search(normalised)
        if date_match:
            day, month, year = date_match.groups()
            try:
                invoice_date = date(
                    int(year), int(month), int(day)
                ).isoformat()
            except ValueError:
                invoice_date = ""
            result["invoice_date"] = invoice_date
        # Parse service lines
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
        result["lines"] = lines
        return result


# Provide a module level convenience function
def parse_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    """Parse a Mobifone PDF invoice via the default parser.

    This function instantiates a :class:`MobifoneInvoiceParser` and
    delegates to its :meth:`parse_pdf` method.
    """
    parser = MobifoneInvoiceParser()
    return parser.parse_pdf(pdf_path)