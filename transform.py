"""
Transformation utilities for invoice data.

This module converts the intermediate invoice representation produced
by individual invoice parsers into a list of accounting journal entries.
Each entry corresponds to a row in the SAP import template. The
conversion encapsulates business rules such as which general ledger
accounts to debit or credit, how to determine the tax group from the
VAT rate, and how to populate descriptive fields.

The primary function exposed by this module is
``invoices_to_ledger_rows``. It accepts a list of parsed invoices and
returns a list of dictionaries keyed by the SAP template column names.
Callers can then convert this list into a ``pandas.DataFrame`` and
export it to Excel using the :mod:`excel_export` module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class TransformConfig:
    """Configuration for mapping invoice data to ledger rows.

    Attributes
    ----------
    vendor_code : str
        Business partner code identifying the telecom provider in SAP.

    vendor_name : str
        Human readable name of the provider.

    vendor_tax_code : str
        The vendor's tax ID (Mã số thuế).

    vendor_address : str
        Address of the vendor.

    expense_account : str
        G/L account to debit for service charges (e.g. phone expense).

    vat_account : str
        G/L account to debit for input VAT.

    payable_account : str
        Accounts payable control account for the vendor.

    project_code : str
        Value to fill in the ``Project/Khế ước`` column.

    default_branch : str
        Value for the ``Branch`` column if none specified.

    tax_group_map : dict[int, str]
        Mapping from VAT percentage to tax group code (e.g. {10: "PVN1", 0: "PVN3"}).

    remarks_template : str
        Optional remarks template to populate the ``Remarks Template`` column.

    description_template : str
        Template for generating the ``Diễn giải`` field. It should include
        placeholders ``{period}`` and ``{invoice_no}`` which will be
        replaced with the billing period and invoice number respectively.

    period : str
        Billing period identifier (e.g. "T12.24" for December 2024). Used
        in descriptions to contextualise the invoice.

    cfw_id : str
        The CFWId (possibly a cost centre or distribution key) to fill
        into the ``CFWId`` column. Leave blank if not used.
    """
    vendor_code: str
    vendor_name: str
    vendor_tax_code: str
    vendor_address: str
    expense_account: str = "64271001"
    vat_account: str = "13311001"
    payable_account: str = "33111001"
    project_code: str = "TTG"
    default_branch: str = ""
    tax_group_map: Dict[int, str] = field(default_factory=lambda: {10: "PVN1", 0: "PVN3"})
    remarks_template: str = ""
    description_template: str = "CP DIEN THOAI MOBIFONE {period} - HD{invoice_no}"
    period: str = ""
    cfw_id: str = ""


def invoices_to_ledger_rows(
    invoices: Iterable[Dict[str, Any]],
    config: TransformConfig,
    document_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convert parsed invoices into a list of ledger entry rows.

    Each invoice produces one or more rows: an expense row for each
    service line, an optional VAT row for each taxable line, and a
    credit row to balance the payable to the vendor. The rows
    returned conform to the SAP import template columns.

    Parameters
    ----------
    invoices : iterable of dict
        Parsed invoice dictionaries (as returned by the parser). Each
        dict must contain ``invoice_no``, ``serial_no``, ``invoice_date``
        and ``lines``. See :mod:`invoice2SAPdata.base_parser` for
        details.

    config : TransformConfig
        Configuration specifying vendor details and account mappings.

    document_date : str, optional
        Default posting date (YYYY‑MM‑DD). If not provided, the
        invoice's billing date will be used for each row.

    Returns
    -------
    list of dict
        A list of dictionaries keyed by column names expected by the
        SAP template. Empty values are represented as empty strings.
    """
    rows: List[Dict[str, Any]] = []
    # Define the complete set of output columns to ensure consistent ordering
    columns = [
        "G/L Acct/BP Code",
        "G/L Acct/BP Name",
        "Control Acct",
        "Credit",
        "Debit (SC)",
        "Credit (SC)",
        "Remarks Template",
        "Document Date",
        "Project/Khế ước",
        "Tax Group",
        "Federal Tax ID",
        "Receipt Number",
        "Tax Amount",
        "Gross Value",
        "Base Amount",
        "Primary Form Item",
        "Distr. Rule",
        "Branch",
        "Seri HĐ",
        "Debit USD S1",
        "Credit USD S1",
        "InvType",
        "Tình trạng kê khai",
        "Kỳ kê khai",
        "CFWId",
        "Số HĐKM",
        "Seri HĐKM",
        "Diễn giải HĐKM",
        "Nhãn tính C.Nợ",
        "Invoice?",
        "Đảo?",
        "BD: Exp",
        "Mẫu số HĐ",
        "AdjTran",
        "Mã đối tác",
        "Tên đối tác",
        "Địa chỉ",
        "MST",
        "Diễn giải",
        "RemarksJE",
        "Bank Account",
        "BP Bank Account",
        "Share Holder No",
    ]

    for invoice in invoices:
        inv_no = invoice.get("invoice_no", "").strip()
        serial = invoice.get("serial_no", "").strip()
        inv_date = invoice.get("invoice_date") or document_date
        if inv_date is None or not inv_date:
            # Default to today in ISO format if no date provided
            inv_date = date.today().isoformat()
        # Compute total per invoice
        total_invoice_amount = sum(
            line.get("total_amount", 0) for line in invoice.get("lines", [])
        )
        # Generate description string
        description = config.description_template.format(
            period=config.period, invoice_no=inv_no
        )
        for line in invoice.get("lines", []):
            base = line.get("base_amount", 0)
            vat_rate = int(line.get("vat_rate", 0))
            vat_amount = line.get("vat_amount", 0)
            # Expense row (debit)
            expense_row = {col: "" for col in columns}
            expense_row["G/L Acct/BP Code"] = config.expense_account
            expense_row["G/L Acct/BP Name"] = "Chi phí dịch vụ mua ngoài"
            expense_row["Control Acct"] = config.expense_account
            expense_row["Credit"] = ""
            expense_row["Debit (SC)"] = base
            expense_row["Credit (SC)"] = ""
            expense_row["Remarks Template"] = config.remarks_template
            expense_row["Document Date"] = inv_date
            expense_row["Project/Khế ước"] = config.project_code
            expense_row["Tax Group"] = config.tax_group_map.get(vat_rate, "")
            expense_row["Federal Tax ID"] = config.vendor_tax_code
            expense_row["Receipt Number"] = inv_no
            expense_row["Tax Amount"] = ""
            expense_row["Gross Value"] = ""
            expense_row["Base Amount"] = ""
            expense_row["Primary Form Item"] = ""
            expense_row["Distr. Rule"] = ""
            expense_row["Branch"] = config.default_branch
            expense_row["Seri HĐ"] = serial
            expense_row["Debit USD S1"] = ""
            expense_row["Credit USD S1"] = ""
            expense_row["InvType"] = ""
            expense_row["Tình trạng kê khai"] = "Kê khai"
            expense_row["Kỳ kê khai"] = config.period
            expense_row["CFWId"] = config.cfw_id
            expense_row["Số HĐKM"] = ""
            expense_row["Seri HĐKM"] = ""
            expense_row["Diễn giải HĐKM"] = ""
            expense_row["Nhãn tính C.Nợ"] = ""
            expense_row["Invoice?"] = "No"
            expense_row["Đảo?"] = "No"
            expense_row["BD: Exp"] = ""
            expense_row["Mẫu số HĐ"] = ""
            expense_row["AdjTran"] = ""
            expense_row["Mã đối tác"] = config.vendor_code
            expense_row["Tên đối tác"] = config.vendor_name
            expense_row["Địa chỉ"] = config.vendor_address
            expense_row["MST"] = config.vendor_tax_code
            expense_row["Diễn giải"] = description
            expense_row["RemarksJE"] = description
            expense_row["Bank Account"] = ""
            expense_row["BP Bank Account"] = ""
            expense_row["Share Holder No"] = ""
            rows.append(expense_row)
            # VAT row (debit) if applicable
            if vat_amount:
                vat_row = {col: "" for col in columns}
                vat_row["G/L Acct/BP Code"] = config.vat_account
                vat_row["G/L Acct/BP Name"] = "Thuế GTGT được khấu trừ của hàng hóa, dịch vụ"
                vat_row["Control Acct"] = config.vat_account
                vat_row["Credit"] = ""
                vat_row["Debit (SC)"] = vat_amount
                vat_row["Credit (SC)"] = ""
                vat_row["Remarks Template"] = config.remarks_template
                vat_row["Document Date"] = inv_date
                vat_row["Project/Khế ước"] = config.project_code
                vat_row["Tax Group"] = config.tax_group_map.get(vat_rate, "")
                vat_row["Federal Tax ID"] = config.vendor_tax_code
                vat_row["Receipt Number"] = inv_no
                vat_row["Tax Amount"] = ""
                vat_row["Gross Value"] = ""
                vat_row["Base Amount"] = ""
                vat_row["Primary Form Item"] = ""
                vat_row["Distr. Rule"] = ""
                vat_row["Branch"] = config.default_branch
                vat_row["Seri HĐ"] = serial
                vat_row["InvType"] = ""
                vat_row["Tình trạng kê khai"] = "Kê khai"
                vat_row["Kỳ kê khai"] = config.period
                vat_row["CFWId"] = config.cfw_id
                vat_row["Invoice?"] = "No"
                vat_row["Đảo?"] = "No"
                vat_row["Mã đối tác"] = config.vendor_code
                vat_row["Tên đối tác"] = config.vendor_name
                vat_row["Địa chỉ"] = config.vendor_address
                vat_row["MST"] = config.vendor_tax_code
                vat_row["Diễn giải"] = description
                vat_row["RemarksJE"] = description
                rows.append(vat_row)
        # Vendor credit row (credit)
        if total_invoice_amount:
            credit_row = {col: "" for col in columns}
            credit_row["G/L Acct/BP Code"] = config.vendor_code
            credit_row["G/L Acct/BP Name"] = config.vendor_name
            credit_row["Control Acct"] = config.payable_account
            credit_row["Credit"] = total_invoice_amount
            credit_row["Debit (SC)"] = ""
            credit_row["Credit (SC)"] = ""
            credit_row["Remarks Template"] = config.remarks_template
            credit_row["Document Date"] = inv_date
            credit_row["Project/Khế ước"] = config.project_code
            # Tax Group not needed on credit line
            credit_row["Federal Tax ID"] = config.vendor_tax_code
            credit_row["Receipt Number"] = inv_no
            credit_row["Seri HĐ"] = serial
            credit_row["InvType"] = ""
            credit_row["Tình trạng kê khai"] = "Kê khai"
            credit_row["Kỳ kê khai"] = config.period
            credit_row["CFWId"] = config.cfw_id
            credit_row["Invoice?"] = "No"
            credit_row["Đảo?"] = "No"
            credit_row["Mã đối tác"] = config.vendor_code
            credit_row["Tên đối tác"] = config.vendor_name
            credit_row["Địa chỉ"] = config.vendor_address
            credit_row["MST"] = config.vendor_tax_code
            credit_row["Diễn giải"] = description
            credit_row["RemarksJE"] = description
            rows.append(credit_row)
    return rows