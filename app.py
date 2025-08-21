# app.py (Streamlit)
import streamlit as st
from invoice_parsers import mobifone_parser, viettel_parser, vnpt_parser
from excel_export import export_to_excel

st.title("Invoice Data Extraction Tool")
uploaded_files = st.file_uploader("Upload PDF invoices", type=["pdf"], accept_multiple_files=True)
if st.button("Extract and Convert"):
    all_invoices_data = []
    for file in uploaded_files:
        # Lưu file tạm hoặc đọc trực tiếp bytes
        pdf_path = save_temp(file)
        # Xác định loại hóa đơn
        provider = identify_provider(pdf_path)  # hàm đọc nhanh vài dòng đầu tìm tên nhà mạng
        # Gọi parser tương ứng
        if provider == "Mobifone":
            data = mobifone_parser.parse(pdf_path)
        elif provider == "Viettel":
            data = viettel_parser.parse(pdf_path)
        elif provider == "VNPT":
            data = vnpt_parser.parse(pdf_path)
        else:
            data = generic_parser.parse(pdf_path)  # parser dự phòng hoặc thông báo không xác định
        all_invoices_data.append(data)
    # Xuất tất cả dữ liệu ra file Excel
    output_path = export_to_excel(all_invoices_data, template="template.xlsx")
    st.success(f"Đã xử lý {len(all_invoices_data)} hóa đơn")
    st.download_button("Tải file Excel", data=open(output_path, "rb").read(), file_name="Invoices.xlsx")
