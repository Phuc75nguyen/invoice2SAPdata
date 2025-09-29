"""
Example Streamlit application for invoice extraction and SAP export.

This script demonstrates how to build a simple user interface around
the parsing and transformation utilities provided by the
``invoice2SAPdata`` package. Users can upload one or more PDF
invoices, select the provider, and download an Excel workbook
containing the corresponding accounting entries.

To run this application locally, execute the following command from
the root of the project:

    streamlit run invoice2SAPdata/app.py

"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

import streamlit as st

# Always import from the invoice2SAPdata package to ensure we use
# the fully implemented parsers and utilities.  Using the top-level
# modules here can lead to loading placeholder parsers that only
# support single invoices.
from invoice2SAPdata import get_parser
from invoice2SAPdata.transform import TransformConfig, invoices_to_ledger_rows
from invoice2SAPdata.excel_export import export_rows_to_excel


def main() -> None:
    st.title("Invoice to SAP Data Extraction")
    st.write(
        "Tải lên các file PDF hóa đơn và trích xuất dữ liệu vào file Excel theo định dạng SAP."
    )
    provider = st.selectbox(
        "Nhà cung cấp dịch vụ", options=["Mobifone", "VNPT", "Viettel"]
    )
    uploaded_files = st.file_uploader(
        "Chọn một hoặc nhiều file PDF", type=["pdf"], accept_multiple_files=True
    )
    vendor_code = st.text_input("Mã đối tác (BP Code)", value="V00000262")
    vendor_name = st.text_input(
        "Tên đối tác", value="CÔNG TY DỊCH VỤ MOBIFONE KHU VỰC 2"
    )
    vendor_tax = st.text_input("Mã số thuế (MST)", value="0100686209-002")
    vendor_address = st.text_input(
        "Địa chỉ đối tác", value="MM18 Trương Sơn, Phường 14, Quận 10, Thành phố Hồ Chí Minh"
    )
    period = st.text_input("Kỳ (period)", value="T12.24")
    if st.button("Trích xuất và tạo Excel"):
        # Ensure at least one file is uploaded
        if not uploaded_files:
            st.warning("Vui lòng tải lên ít nhất một file PDF.")
            return
        # Attempt to load the appropriate parser module
        try:
            parser_module = get_parser(provider.lower())
        except ImportError as e:
            st.error(str(e))
            return
        # Collect parsed invoices
        invoices: List[dict] = []
        for file in uploaded_files:
            # Write the uploaded bytes to a temporary PDF file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                tmp_path = Path(tmp.name)
            try:
                invoice_data = parser_module.parse_pdf(tmp_path)
                # Flatten lists of invoices returned by the parser
                if isinstance(invoice_data, list):
                    invoices.extend(invoice_data)
                else:
                    invoices.append(invoice_data)
            except Exception as e:
                st.error(f"Lỗi khi phân tích file {file.name}: {e}")
            finally:
                tmp_path.unlink(missing_ok=True)
        # If nothing was parsed, notify the user and abort
        if not invoices:
            st.warning("Không có hóa đơn nào được phân tích thành công.")
            return
        # Build transformation configuration
        config = TransformConfig(
            vendor_code=vendor_code,
            vendor_name=vendor_name,
            vendor_tax_code=vendor_tax,
            vendor_address=vendor_address,
            period=period,
            description_template=f"CP DIEN THOAI {provider.upper()} {{period}} - HD{{invoice_no}}",
            remarks_template="",
            cfw_id="",
        )
        # Convert invoices into accounting ledger rows
        rows = invoices_to_ledger_rows(invoices, config)
        if not rows:
            st.warning("Không có dữ liệu nào để xuất ra file Excel.")
            return
        # Generate an in-memory Excel workbook
        excel_buffer = export_rows_to_excel(rows, sheet_name="SAP_Import", index=False)
        # Offer the Excel file for download
        st.download_button(
            label="Tải file Excel kết quả",
            data=excel_buffer.getvalue(),
            file_name=f"export_{provider.lower()}_{period}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()