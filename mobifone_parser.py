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
    """Concrete parser implementation for Mobifone invoices.

    This implementation attempts to cope with the layout of Mobifone's
    electronic invoices where the serial number, invoice number and
    amount fields may not appear in the expected order. The parser
    first tries to extract the serial and invoice numbers together (the
    serial appears before the invoice number) and falls back to more
    generic patterns if that fails. Service lines are detected by
    locating four numeric fields in the order total–VAT–VAT rate–base
    immediately before the service description. Duplicate lines are
    removed before returning the results.
    """

    # Combined pattern matching "<serial> <invoice> Ký hiệu Số"
    _serial_number_combo_pattern = re.compile(
        r"\b([A-Z0-9]{4,})\s+(\d{4,})\s+Ký\s*hiệu\s*Số",
        re.IGNORECASE,
    )
    # Fallback patterns to extract serial and invoice separately
    _serial_pattern = re.compile(
        r"Ký\s*hiệu[^:]*[:\s]\s*([A-Z0-9]{4,})",
        re.IGNORECASE,
    )
    _number_pattern = re.compile(
        r"Số\s*(?:\(No\.\))?[^:]*[:\s]\s*(\d+)",
        re.IGNORECASE,
    )
    _date_pattern = re.compile(
        r"Ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        re.IGNORECASE,
    )
    # Pattern matching four numeric fields: total, VAT, rate, base before the word "Cước"
    _line_pattern = re.compile(
        r"([0-9][0-9\.\,]*)\s+([0-9][0-9\.\,]*)\s+(\d{1,2})%\s+([0-9][0-9\.\,]*)\s+Cước",
        re.IGNORECASE,
    )

    @staticmethod
    def _parse_number(value: str) -> float:
        """
        Convert a formatted monetary string into a float. Thousands
        separators (either dot or space) are removed and a comma is
        converted to a dot for decimal separation. If conversion fails
        the function returns 0.0.

        Parameters
        ----------
        value : str
            The monetary amount as printed on the invoice.

        Returns
        -------
        float
            The numeric value of the amount.
        """
        if not value:
            return 0.0
        cleaned = value.replace("\xa0", " ").strip()
        # replace commas with dots and remove any remaining spaces
        cleaned = cleaned.replace(",", ".").replace(" ", "")
        # remove thousands separators (periods)
        cleaned = cleaned.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def parse_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        """
        Parse a Mobifone PDF invoice and extract key fields.

        Parameters
        ----------
        pdf_path : str or Path
            Path to the PDF file.

        Returns
        -------
        dict
            A dictionary with keys ``invoice_no``, ``serial_no``,
            ``invoice_date`` and ``lines``. ``lines`` is a list of
            dictionaries each containing ``base_amount``, ``vat_rate``,
            ``vat_amount`` and ``total_amount``.
        """
        # Extract raw text from PDF and normalise whitespace
        text = extract_text(pdf_path)
        normalised = re.sub(r"\s+", " ", text)
        result: Dict[str, Any] = {
            "invoice_no": "",
            "serial_no": "",
            "invoice_date": "",
            "lines": [],
        }
        # Attempt to capture serial and invoice numbers together
        combo_match = self._serial_number_combo_pattern.search(normalised)
        if combo_match:
            serial, number = combo_match.groups()
            result["serial_no"] = serial.strip()
            result["invoice_no"] = number.strip()
        else:
            # Fallback: separate patterns
            serial_match = self._serial_pattern.search(normalised)
            if serial_match:
                result["serial_no"] = serial_match.group(1).strip()
            number_match = self._number_pattern.search(normalised)
            if number_match:
                result["invoice_no"] = number_match.group(1).strip()
        # Date extraction
        date_match = self._date_pattern.search(normalised)
        if date_match:
            day, month, year = date_match.groups()
            try:
                invoice_date = date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                invoice_date = ""
            result["invoice_date"] = invoice_date
        # Extract service lines
        raw_lines: List[Dict[str, Any]] = []
        for match in self._line_pattern.finditer(normalised):
            total_raw, vat_raw, rate_raw, base_raw = match.groups()
            base_amount = self._parse_number(base_raw)
            vat_rate = int(rate_raw)
            vat_amount = self._parse_number(vat_raw)
            total_amount = self._parse_number(total_raw)
            raw_lines.append(
                {
                    "base_amount": base_amount,
                    "vat_rate": vat_rate,
                    "vat_amount": vat_amount,
                    "total_amount": total_amount,
                }
            )
        # Deduplicate lines because the invoice may repeat the same totals
        seen: set[tuple] = set()
        unique_lines: List[Dict[str, Any]] = []
        for line in raw_lines:
            key = (
                line["base_amount"],
                line["vat_rate"],
                line["vat_amount"],
                line["total_amount"],
            )
            if key not in seen:
                seen.add(key)
                unique_lines.append(line)
        result["lines"] = unique_lines
        return result


# Provide a module level convenience function
def parse_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    """Parse a Mobifone PDF invoice via the default parser.

    This function instantiates a :class:`MobifoneInvoiceParser` and
    delegates to its :meth:`parse_pdf` method.
    """
    parser = MobifoneInvoiceParser()
    return parser.parse_pdf(pdf_path)