# Parser for Viettel post‑paid telecom invoices.
#
# Viettel invoices are bilingual (Vietnamese and English) and present the core
# billing information in a structured layout. This parser extracts the invoice
# serial, number, billing date and monetary line items (service charge, VAT rate,
# VAT amount and gross amount) using regular expressions. Thousands separators
# (dots) are removed before converting amounts to floats. Duplicate lines
# resulting from the "CỘNG" (total) row are filtered out.

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from .base_parser import BaseInvoiceParser
from .pdf_utils import extract_text


class ViettelInvoiceParser(BaseInvoiceParser):
    """Concrete parser implementation for Viettel invoices."""

    # Regular expressions to extract key fields. Patterns are deliberately
    # permissive to handle minor variations in spacing and punctuation.
    _serial_pattern = re.compile(r"Ký\s*hiệu\s*[:\s]\s*([A-Z0-9]+)", re.IGNORECASE)
    _number_pattern = re.compile(r"Số\s*[:\s]\s*(\d+)", re.IGNORECASE)
    # Match dates like "Ngày lập: DD/MM/YYYY" or "Ngày DD/MM/YYYY"
    _date_slash_pattern = re.compile(r"Ngày\s*(?:lập)?\s*[:\s]*([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", re.IGNORECASE)
    # Match dates like "Ngày DD tháng MM năm YYYY" (less common)
    _date_text_pattern = re.compile(r"Ngày\s+([0-9]{1,2})\s+tháng\s+([0-9]{1,2})\s+năm\s+([0-9]{4})", re.IGNORECASE)
    # Pattern matching a service line: base amount, VAT %, VAT amount, total
    _line_pattern = re.compile(r"([0-9][0-9\.,]*)\s+(\d{1,2})%\s+([0-9][0-9\.,]*)\s+([0-9][0-9\.,]*)")

    @staticmethod
    def _parse_number(value: str) -> float:
        """Convert a formatted monetary string into a float."""
        cleaned = value.replace("\xa0", "").strip()
        cleaned = cleaned.replace(",", ".")
        cleaned = cleaned.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def parse_pdf(self, pdf_path):
        """Parse a single Viettel invoice PDF into a structured dict."""
        text = extract_text(pdf_path)
        # Collapse all whitespace to single spaces for easier matching
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
        date_match = self._date_slash_pattern.search(normalised)
        if date_match:
            day, month, year = date_match.groups()
            try:
                invoice_date = date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                invoice_date = ""
            result["invoice_date"] = invoice_date
        else:
            date_match = self._date_text_pattern.search(normalised)
            if date_match:
                day, month, year = date_match.groups()
                try:
                    invoice_date = date(int(year), int(month), int(day)).isoformat()
                except ValueError:
                    invoice_date = ""
                result["invoice_date"] = invoice_date
        # Extract service lines
        lines: List[Dict[str, Any]] = []
        for match in self._line_pattern.finditer(normalised):
            base_raw, rate_raw, vat_raw, total_raw = match.groups()
            base_amount = self._parse_number(base_raw)
            vat_rate = int(rate_raw)
            vat_amount = self._parse_number(vat_raw)
            total_amount = self._parse_number(total_raw)
            lines.append({
                "base_amount": base_amount,
                "vat_rate": vat_rate,
                "vat_amount": vat_amount,
                "total_amount": total_amount,
            })
        # Remove duplicate line items (e.g. the "CỘNG" row) by using a set
        unique: Set[Tuple[float, int, float, float]] = set()
        filtered: List[Dict[str, Any]] = []
        for line in lines:
            key = (line["base_amount"], line["vat_rate"], line["vat_amount"], line["total_amount"])
            if key not in unique:
                unique.add(key)
                filtered.append(line)
        result["lines"] = filtered
        return result


# Convenience wrapper to parse a Viettel invoice.
def parse_pdf(pdf_path):
    """Parse a Viettel invoice from a PDF file path.

    This helper instantiates :class:`ViettelInvoiceParser` and delegates
    parsing to it, returning the structured invoice dictionary.
    """
    parser = ViettelInvoiceParser()
    return parser.parse_pdf(pdf_path)