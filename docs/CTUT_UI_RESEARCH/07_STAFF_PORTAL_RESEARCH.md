# 07 – Nghiên cứu cổng cán bộ: dashboard, trang chi tiết, hộp thoại nghiệp vụ

Các mẫu chung về dashboard, bảng và form đã ghi ở [04](04_DASHBOARD_RESEARCH.md). File này áp dụng các mẫu đó vào 3 vai trò cán bộ của CTUT (QLSV, Đào tạo, Hiệu trưởng) và vai trò quản trị.

## 1. Phân quyền giao diện – đối chiếu nguồn

| Nguồn | Cách phân quyền giao diện | Bằng chứng |
| :--- | :--- | :--- |
| Kiranism | Menu khai báo một nơi (`nav-config.ts`), mỗi mục có `access: { role, permission }`. Mỗi trang **vẫn tự gọi `auth.protect()`** ở server ("defense in depth"). Trang không đủ quyền hiện thông báo thay vì lỗi. | `src/config/nav-config.ts`, `src/app/dashboard/layout.tsx`, `page-container.tsx` |
| Certiport | 3 dashboard tách biệt theo route (`/university`, `/student`, `/admin`), chuyển trang theo vai trò sau đăng nhập | `Login.js`, `App.js` |
| **CTUT** | Một bảng điều khiển, nội dung theo `UserProfile.role`; mọi view kiểm tra quyền ở backend | `views.py`, `components/sidebar.html` |

**Kết luận:** mô hình của CTUT (một khung, nội dung theo vai trò, backend quyết định quyền) giống Kiranism. Điều nên học thêm là **khai báo menu tập trung**, và có **mẫu trang "không có quyền"** thay cho chuyển hướng im lặng.

## 2. Dashboard theo vai trò

| Vai trò | Thẻ số liệu (bấm để lọc) | Nút chính trên dòng | Thao tác khác (menu "⋯") |
| :--- | :--- | :--- | :--- |
| Phòng QLSV | Tất cả / Chờ duyệt / Bị trả về / Đã chuyển Đào tạo / Đã cấp | Duyệt; Sửa và gửi lại (khi bị trả về) | Xem chi tiết, In phôi, Tài khoản sinh viên, Từ chối hồ sơ, Thu hồi văn bằng (khi đã cấp) |
| Phòng Đào tạo | Tất cả / Chờ duyệt / Hiệu trưởng trả về / Đã chuyển Hiệu trưởng / Đã cấp | Duyệt (hoặc Duyệt lại) | Xem chi tiết, In phôi, Trả hồ sơ về QLSV, Thu hồi văn bằng (khi đã cấp) |
| Hiệu trưởng | Tất cả / Chờ ký / Đã trả về Đào tạo / Đã cấp | Ký phát hành | Xem chi tiết, In phôi, Trả hồ sơ về Đào tạo, Thu hồi văn bằng (khi đã cấp) |
| Quản trị | Tất cả / Chờ từng cấp / Bị trả về / Đã cấp | Theo bước của hồ sơ | Toàn bộ |

Đợt 1 đã triển khai bảng này, theo đúng điều kiện hiển thị hiện có trong `dashboard.html` (nút thu hồi hiện với mọi vai trò cán bộ khi văn bằng đã cấp; view `certificate_revoke` ghi nhận ý kiến từng phòng và chỉ chuyển trạng thái khi đủ 3 phòng xác nhận hoặc admin thu hồi). Còn thiếu so với nguồn: **phân trang** (Kiranism) và **trang 403** (ShadcnStore).

## 3. Trang chi tiết văn bằng

Không nguồn nào có trang chi tiết đúng nghiệp vụ văn bằng. Gần nhất là:
- **OpenCerts:** kết luận + bằng chứng + văn bằng dựng sẵn.
- **ShadcnStore:** trang chia khối có tiêu đề + mô tả.
- **Certiport:** thẻ văn bằng có ID + sao chép.

Đề xuất bố cục (desktop ≥ 1200px):

```
Breadcrumb · Văn bằng VB-2026-007                 [Quay lại] [In phôi] [Trang công khai]
┌ Tổng quan: Số hiệu | Người được cấp | Trạng thái | Bước đang xử lý | Ngày cấp ┐
├──────────────────────────────── 7/12 ─────┬──────────── 5/12 ───────────┤
│ Ảnh văn bằng                                 │ Thông tin hồ sơ            │
│  - có quyền: ảnh gốc + nhãn "Ảnh gốc"         │ (họ tên, ngày sinh, ngành, │
│  - không quyền: ảnh công khai + nhãn          │  xếp loại, CCCD đã che…)   │
│    "Không có quyền xem ảnh gốc"               │ Bằng chứng xác thực        │
│ Quản lý ảnh (thu gọn, chỉ người có quyền)     │  ✓ Khớp sổ cái ✓ Có chữ ký │
│                                               │  Mã băm 0x309b…f9ce5 [Sao chép] │
├──────────────────────────────────────────────┴─────────────────────────┤
│ Tab: Lịch sử phê duyệt | Lịch sử truy cập ảnh (5 dòng gần nhất + "Xem thêm") │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Bằng chứng xác thực** theo mẫu OpenCerts: kết luận trước, danh sách kiểm tra ✓, mã kỹ thuật rút gọn kèm nút sao chép.
- **Mobile:** Tổng quan → Thông tin → Bằng chứng → Ảnh → Lịch sử. Nút đầu trang gom vào menu "⋯".
- **Quyền xem ảnh gốc** do view `staff_diploma_image` quyết định (permission `view_original_diploma`). Giao diện chỉ phản ánh: hiện ảnh gốc hay ảnh công khai, kèm nhãn giải thích.

## 4. Hộp thoại nghiệp vụ

| Hộp thoại | Mẫu áp dụng | Chi tiết |
| :--- | :--- | :--- |
| Tạo hồ sơ / Sửa hồ sơ | ShadcnStore "Add New User" | Rộng khoảng 672px; trường ngắn 2 cột (Ngày sinh / Năm tốt nghiệp, Ngành / Xếp loại); nhãn trên ô; dấu `*` cho trường bắt buộc; lỗi hiện ngay dưới ô; nút chính góc phải dưới |
| Nhập Excel | Kiranism (`react-dropzone` cho tải file) | Ô chọn file lớn có hướng dẫn; tên file sau khi chọn; danh sách cột bắt buộc; nút tải mẫu ngay trong hộp thoại |
| Duyệt / Ký phát hành | — | Nút một bước như hiện tại (form POST + CSRF). Có thể thêm câu xác nhận ngắn cho bước Ký phát hành, vì bước này ghi lên blockchain và không đảo ngược được. |
| Trả hồ sơ / Từ chối | Kiranism `AlertModal`, ShadcnStore "Danger Zone" | Tiêu đề nêu số hiệu và tên sinh viên; **lý do bắt buộc**; nút xác nhận màu đỏ; nút huỷ là nút mặc định |
| Thu hồi văn bằng | như trên | Giữ ô chọn loại hiện có (Thu hồi / Hủy / Thay thế + số hiệu văn bằng thay thế); thêm dòng cảnh báo "Thao tác ghi lên sổ cái, không hoàn tác" |
| Thông báo kết quả | Django messages (hiện tại) | Thông báo đầu trang, có màu theo loại; giữ nguyên |
