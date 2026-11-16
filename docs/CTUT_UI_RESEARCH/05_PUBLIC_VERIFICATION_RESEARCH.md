# 05 – Nghiên cứu cổng tra cứu và xác minh công khai

Nguồn: OpenCerts website [LIVE + CODE], Open Certificate [CODE], Certiport [ẢNH REPO + CODE].

## 1. Bố cục trang nhập

| Nguồn | Quan sát | Bằng chứng |
| :--- | :--- | :--- |
| OpenCerts | Trái: tiêu đề lớn + 1 câu ("Whether you are a student or an employer…"). Phải: **ô kéo-thả file** nét đứt + nút "Select File". Bên dưới là logo các đơn vị cấp (tạo lòng tin). Mobile: thay ô kéo-thả bằng nút "Click me for a demo certificate!". | `verification/opencerts__home__*.png` |
| Certiport | Hero tiêu đề + thẻ "Verify Certificate": ô nhập Blockchain ID, "OR", nút "Upload QR Code". Bên phải là khối "How it works" 3 bước. | `verification/certiport__public-verify__pdf.png` |
| **CTUT hiện tại** | Hero + ô nhập mã xác minh (icon QR) + nút "Xác minh", 3 bước hướng dẫn bên dưới. | `docs/images/ui_after_desktop_01_tra_cuu.png` |

**Phát hiện từ mã:** nút "Upload QR Code" của Certiport **chưa thật sự đọc QR** – `PublicVerify.js` dòng 83–88 chỉ hiện `alert(...)` yêu cầu nhập tay. Ảnh chụp giao diện có nút này không có nghĩa là chức năng đã hoạt động.

## 2. Bố cục kết quả xác minh

| Hạng mục | OpenCerts | Certiport | Nhận xét cho CTUT |
| :--- | :--- | :--- | :--- |
| Kết luận | **Một khối, một dòng:** icon ✓ + "Certificate issued by OPENCERTS.IO" (xanh) | Tiêu đề "Certificate Verified ✓" + 1 câu | Theo OpenCerts: kết luận nằm trên cùng, một dòng, kèm tên đơn vị cấp |
| Bằng chứng | Bấm để mở "Details": ✓ "has not been tampered with", ✓ "has not been revoked". Tên đơn vị cấp lấy từ bằng chứng tên miền DNS-TXT. | Không có; chỉ in Blockchain ID | Mở rộng được: ✓ "Dữ liệu khớp sổ cái", ✓ "Chưa bị thu hồi", ✓ "Có chữ ký điện tử của nhà trường". Viết dễ hiểu, không đưa hash ra mặc định. |
| Không hợp lệ | Khung đỏ nét đứt, "This certificate is not valid", **lý do cụ thể**, câu hướng dẫn, nút "What should I do?" + "Try another" | Một dòng lỗi "Certificate not found or invalid" (`PublicVerify.js` dòng 34) | Mỗi trạng thái (thu hồi / không tìm thấy / chưa phát hành) cần lý do + việc người tra cứu nên làm |
| Nội dung văn bằng | Hiển thị văn bằng đã dựng (tab Certificate / Transcript / Media) | Bảng thông tin: **Student Name, Enrollment Number hiện đầy đủ** | Ảnh văn bằng đã che + thông tin tối thiểu |
| Thao tác | Print, Email, Download, "View another" | Download | In / tải bản công khai; "Tra cứu văn bằng khác" |

Bằng chứng: `verification/opencerts__demo-valid-checks-expanded__1440.png`, `verification/opencerts__demo-result__390.png`, `verification/opencerts__invalid-wrong-network__1440.png`.

## 3. Bảo vệ thông tin cá nhân

- **Open Certificate** (`README.md` phần "Obfuscating Fields", `src/index.js`): `obfuscateFields(cert, paths[])` ẩn các trường như `recipient.nric` mà chứng chỉ vẫn xác minh được, vì mỗi trường được băm kèm muối.
  - **Nguyên tắc rút ra:** người tra cứu chỉ cần biết văn bằng có thật, do ai cấp, còn hiệu lực không. Họ không cần số định danh cá nhân.
- **Certiport:** trả về tên và mã số sinh viên đầy đủ cho bất kỳ ai có Blockchain ID. CTUT **không làm** như vậy.
- **CTUT đã có:** ảnh công khai che thông tin phía server, họ tên che một phần ("Hoàng T*** Lan"), CCCD không bao giờ hiện ra. Liên kết chia sẻ do sinh viên tạo mới mở thêm thông tin, có thời hạn và số lượt xem.

## 4. Đề xuất bố cục kết quả (một phương án)

```
┌────────────────────────────────────────────────────────────────┐
│ ✓  Văn bằng hợp lệ – do Trường ĐH Kỹ thuật – Công nghệ Cần Thơ cấp  [Chi tiết ▾] │
│    ✓ Dữ liệu khớp sổ cái   ✓ Chưa bị thu hồi   ✓ Có chữ ký của nhà trường          │
├──────────────────────────────────────┬─────────────────────────┤
│  Ảnh văn bằng (đã che thông tin)       │ Người được cấp: Hoàng T*** Lan │
│                                        │ Văn bằng: Cử nhân CNTT  │
│                                        │ Số hiệu, ngày cấp       │
│                                        │ [In] [Tra cứu văn bằng khác] │
└──────────────────────────────────────┴─────────────────────────┘
 ⓘ Vì sao tin được kết quả này (2–3 dòng, không thuật ngữ kỹ thuật)
```

Trạng thái và màu:

| Trạng thái | Màu khối kết luận | Câu kết luận | Việc người tra cứu nên làm |
| :--- | :--- | :--- | :--- |
| Hợp lệ | Xanh lá | Văn bằng hợp lệ | — |
| Đã thu hồi / hủy / thay thế | Đỏ | Văn bằng không còn hiệu lực (kèm loại và ngày) | Liên hệ nhà trường để xác nhận |
| Chưa phát hành | Vàng | Hồ sơ chưa được phát hành | Kiểm tra lại sau hoặc liên hệ người sở hữu |
| Không tìm thấy | Xám | Không tìm thấy văn bằng với mã này | Kiểm tra lại mã trên văn bằng |

Mobile: khối kết luận → thông tin → ảnh (ảnh đặt sau, vì người tra cứu cần kết luận trước).
