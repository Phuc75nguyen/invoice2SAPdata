# Project structure
```
invoice_etl_tool/
├── app.py                   # Code Streamlit (UI)
├── invoice_parsers/         # Package chứa các parser theo nhà cung cấp
│   ├── __init__.py
│   ├── base_parser.py       # (tuỳ chọn) Lớp cơ sở cho parser, định nghĩa interface chung
│   ├── mobifone_parser.py   # Hàm parse cụ thể cho hóa đơn Mobifone
│   ├── viettel_parser.py    # Parser cho Viettel
│   ├── vnpt_parser.py       # Parser cho VNPT
│   └── pdf_utils.py         # Hàm dùng chung (extract_text, ocr_image, etc.)
├── data_extraction.py       # Hàm trích xuất trường từ text (nếu không gộp vào parser luôn)
├── transform.py             # Hàm chuẩn hóa + mapping JSON (nếu cần tách riêng)
├── excel_export.py          # Hàm tạo DataFrame và xuất Excel
└── requirements.txt
```