# Sinh và Sửa lỗi Kiểm thử Python bằng Ngữ cảnh Mã nguồn và Phản hồi Thực thi

Mã nguồn thực nghiệm và công cụ tái lập kết quả phục vụ Tiểu luận môn học Công nghệ Phần mềm Tiên tiến.

## 1. Giới thiệu tổng quan

Kho lưu trữ này cung cấp triển khai chuẩn hóa của hệ thống sinh và sửa lỗi kiểm thử đơn vị Python tự động gồm 3 thành phần cốt lõi:
1. **Trích xuất bao đóng ngữ cảnh AST (Algorithm 3.1):** Trích xuất chữ ký, lớp bao bọc và các hàm bổ trợ cục bộ từ cây cú pháp trừu tượng.
2. **Thăm dò thiết lập động (Dynamic Setup Probing):** Phân tích ràng buộc tham số nhằm tạo khung khởi tạo đối tượng, bảo toàn tính đúng đắn của Test Oracle.
3. **Vòng lặp phản biện thích ứng và Hộp cát Pytest (Algorithm 3.2):** Thực thi kiểm thử cô lập, kiểm soát thời gian chạy, đo độ phủ và tự động sửa lỗi qua 2 vòng phản hồi chẩn đoán.

## 2. Cấu trúc thư mục

```text
├── data/
│   ├── curated_benchmark/      # Dữ liệu 21 đối tượng chuẩn hóa và 187 đột biến AST
│   └── large_scale_3870/       # Dữ liệu 3.870 lượt thực thi trên 21 dự án
├── reports/
│   ├── Tieu_Luan_CNPMTT_Test4Py_Hoan_Chinh.docx
│   ├── Tieu_Luan_CNPMTT_Test4Py_Hoan_Chinh.pdf
│   └── figures/                # Biểu đồ và hình ảnh dùng trong bài báo cáo
├── scripts/
│   ├── demo.py                 # Kịch bản chạy thử nghiệm quy trình sinh và sửa lỗi
│   └── reproduce_paper_metrics.py  # Kịch bản tái lập toàn bộ bảng số liệu trong tiểu luận
├── src/
│   ├── ast_context.py          # Trích xuất cấu trúc mã nguồn AST
│   ├── setup_probing.py        # Thăm dò tham số và tạo khung gọi hàm
│   ├── sandbox.py              # Hộp cát thực thi Pytest và cổng kiểm soát chất lượng
│   ├── critic.py               # Phân tích traceback và điều phối sửa lỗi
│   └── generator.py            # Tổng hợp chỉ thị và điều phối quy trình
└── requirements.txt
```

## 3. Cài đặt môi trường

Yêu cầu Python >= 3.10.

```bash
pip install -r requirements.txt
```

## 4. Hướng dẫn chạy thử nghiệm (Demo)

Chạy kịch bản minh họa quy trình trích xuất AST, sinh kiểm thử, bắt lỗi thất bại trong hộp cát và tự động sửa khẳng định vi mô:

```bash
python scripts/demo.py
```

## 5. Hướng dẫn tái lập số liệu thực nghiệm

Tái lập toàn bộ các bảng kết quả nghiên cứu trong bài báo cáo (Bảng 4.2, Bảng 4.5, Bảng 4.6, Bảng 4.7):

```bash
python scripts/reproduce_paper_metrics.py
```
