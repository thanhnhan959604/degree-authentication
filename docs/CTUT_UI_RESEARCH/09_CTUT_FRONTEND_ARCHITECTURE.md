# 09 – Kiến trúc giao diện áp dụng cho CTUT (Django Templates + Bootstrap 5.3.3)

Công nghệ giữ nguyên: Django 5.2, Django Templates, Bootstrap 5.3.3, Bootstrap Icons 1.11.3, JavaScript thuần, CSS tuỳ chỉnh. Các repo GitHub chỉ là nguồn học bố cục; **không chuyển sang React / Next.js, không chép mã.**

## 1. Ánh xạ từ nguồn tham khảo sang Django / Bootstrap

| Thành phần tham khảo | Đặc điểm thiết kế | Cách áp dụng vào Django / Bootstrap |
| :--- | :--- | :--- |
| Dashboard (Kiranism `PageContainer`, ShadcnStore) | Tiêu đề + mô tả + nút hành động; hàng thẻ số liệu; nội dung chính | `layouts/portal.html` có sẵn block `page_title`, `page_subtitle`, `page_actions`; thẻ số liệu là `components/kpi_card.html` (`{% include ... with key= label= value= %}`) |
| Sidebar (Kiranism `nav-config.ts`) | Menu khai báo một nơi, lọc theo vai trò | **Đề xuất:** chuyển các nhánh `{% if r == ... %}` trong `components/sidebar.html` thành một danh sách Python (ví dụ `certificates/navigation.py`), context processor lọc theo `UserProfile.role` rồi template chỉ lặp. Quyền thật vẫn kiểm tra ở view. |
| Header (Kiranism, OpenCerts) | Thanh cố định: nhận diện + điều hướng chính + tài khoản | `components/header.html` (giữ header ngang toàn trang cho mọi phân hệ) |
| Login (ShadcnStore #1 + mô tả Cổng Dịch vụ công) | Thẻ giữa màn hình, logo và tên trên cùng, nhóm tài khoản | `layouts/auth.html` + `certificates/login.html` (đã có). JS `[data-login-kind]` chỉ đổi nhãn, **không** gửi vai trò để cấp quyền. |
| Data table (ShadcnStore, Kiranism) | Thanh công cụ, ô 2 tầng, menu "⋯", phân trang | Bảng Bootstrap + lớp `ds-cert-table`; dropdown Bootstrap với `data-bs-popper-config='{"strategy":"fixed"}'` để menu không bị cắt; phân trang bằng `django.core.paginator.Paginator` + component `components/pagination.html` (mới) |
| Form / Modal (ShadcnStore Add User, Account Settings) | Trường 2 cột, nhãn trên ô, khối nguy hiểm tách riêng | Modal Bootstrap; lưới `row g-3` + `col-md-6`; lỗi dùng `.invalid-feedback`; hộp xác nhận dùng `modal-dialog` 560px |
| Diploma viewer (OpenCerts) | Văn bằng dựng ngay trong trang, thao tác In / Tải, nhãn chế độ xem | `certificates/_diploma_viewer.html` (đã có, dùng chung 3 chế độ); ảnh lấy từ view có kiểm tra quyền |
| Kết quả xác minh (OpenCerts `CertificateVerifyBlock`) | Một dòng kết luận + danh sách kiểm tra mở rộng được | Component mới `components/verify_result.html`; mở rộng bằng `<details>` hoặc Bootstrap `collapse` (không cần JS riêng) |
| Trang lỗi (ShadcnStore 403) | Mã lỗi + 1 câu + 2 nút | `templates/403.html`, `404.html`, `500.html` kế thừa `layouts/public.html` (Django tự dùng khi `DEBUG=False`) |

## 2. Kiến trúc phân hệ

```
base.html  (head, font Inter, Bootstrap, design-system.css, skip link, main.js)
├── layouts/public.html   ← Public Portal: search.html (tra cứu, xác minh, liên kết chia sẻ), 403/404/500
├── layouts/auth.html     ← Authentication: login.html; kích hoạt / quên mật khẩu (đề xuất chuyển sang đây)
├── layouts/portal.html   ← Student Portal + Staff Portal (header + sidebar theo vai trò + breadcrumb + page header)
│   ├── student_portal.html (mode=portal)
│   ├── dashboard.html
│   └── certificate_detail.html
├── print_view.html       ← trang in độc lập (giữ nguyên)
└── admin/base_site.html  ← Administration: Django Admin, chỉ đổi nhận diện
```

| Phân hệ | Layout | Component dùng chung | Component đặc thù |
| :--- | :--- | :--- | :--- |
| Public Portal | `public.html` | header, footer, alerts, status_badge, diploma_viewer | verify_result (mới), hero tìm kiếm |
| Authentication | `auth.html` | footer, alerts | thẻ nhóm tài khoản, thông báo bảo mật |
| Student Portal | `portal.html` | header, sidebar, alerts, status_badge, diploma_viewer | thẻ văn bằng, tạo / thu hồi liên kết chia sẻ, lịch sử xác minh |
| Staff Portal | `portal.html` | header, sidebar, alerts, status_badge, diploma_viewer, kpi_card | bảng hồ sơ, các hộp thoại nghiệp vụ, khối bằng chứng xác thực |
| Administration | Django Admin | — | `admin/base_site.html` |
| Diploma Viewer | (component) | — | 3 chế độ: `public` / `owner` / `staff` |

## 3. Quyền xem ảnh văn bằng – giao diện phản ánh backend

| Người xem | Ảnh nhận được | Nơi quyết định | Giao diện hiển thị |
| :--- | :--- | :--- | :--- |
| Người tra cứu công khai | Ảnh đã che (`public_diploma_image`); qua liên kết chia sẻ thì theo phạm vi sinh viên cho phép (`share_diploma_image`) | View: chỉ trả ảnh đã che; ảnh gốc không có URL công khai | Nhãn "Ảnh đã che thông tin cá nhân" |
| Sinh viên | Ảnh đầy đủ **của chính mình** (`owner_diploma_image`) | View kiểm tra văn bằng thuộc tài khoản đang đăng nhập | Nhãn "Văn bằng của bạn" |
| Cán bộ có quyền | Ảnh gốc (`staff_diploma_image`, variant gốc) | Permission `certificates.view_original_diploma`; mỗi lượt xem / tải được ghi nhật ký | Nhãn "Ảnh văn bằng gốc" + dòng "Mỗi lượt xem được ghi nhật ký" |
| Cán bộ không có quyền | Ảnh công khai | Như trên; lượt từ chối được ghi nhật ký | Nhãn "Không có quyền xem ảnh gốc" |

Nguyên tắc: **template không bao giờ chọn URL ảnh gốc chỉ dựa vào biến hiển thị.** View trả về biến `can_view_original` (đã tính từ permission), và chính view ảnh kiểm tra lại quyền lần nữa, như Kiranism "defense in depth".

## 4. Thành phần cần chuẩn hoá, giữ lại, bổ sung

| Loại | Thành phần |
| :--- | :--- |
| **Giữ nguyên** | `base.html`, 3 layout, header, footer, alerts, status_badge, kpi_card, `_diploma_viewer.html`, `print_view.html`, `admin/base_site.html`, token trong `design-system.css`, toàn bộ view / URL / quyền |
| **Chuẩn hoá** | Các hộp thoại nghiệp vụ (kiểu cũ) → theo mục 4 của [07](07_STAFF_PORTAL_RESEARCH.md); `.ds-nav-label` đổi màu `#94A3B8` → `--ds-text-muted`; trang kích hoạt / quên mật khẩu chuyển sang `layouts/auth.html`; sidebar chuyển sang khai báo tập trung |
| **Bổ sung** | `components/pagination.html` + phân trang ở view `dashboard` (cần duyệt vì sửa view); `components/verify_result.html`; `templates/403.html`, `404.html`, `500.html`; nút "Sao chép" cho mã xác minh và mã băm; trạng thái "Đang xử lý…" cho nút gửi form |
| **Loại bỏ dần** | Các lớp cũ trong `style.css` sau khi mọi trang đã dùng lớp `ds-*` (chỉ xoá khi đã kiểm chứng không còn trang nào dùng) |

## 5. Thứ tự triển khai đề xuất (khớp kế hoạch các đợt đã thống nhất)

| Đợt | Nội dung | Áp dụng từ nghiên cứu |
| :--- | :--- | :--- |
| 1 (đã xong) | Bảng điều khiển cán bộ | 04, 07 |
| 2 | Trang chi tiết văn bằng | 07 mục 3; khối bằng chứng theo OpenCerts |
| 3 | Hộp thoại nghiệp vụ | 07 mục 4; ShadcnStore Add User, Kiranism AlertModal |
| 4 | Cổng sinh viên | 06 |
| 5 | Trang công khai + đăng nhập | 03, 05 |
| 6 | Phôi in, Django Admin, trang lỗi, phân trang | 08 mục 4, 09 mục 4 |

Mỗi đợt kiểm tra như Đợt 1: chụp ảnh trước / sau ở 1440 / 1024 / 390px, đo cỡ chữ / màu / số nút, chạy 64 test backend và bộ kiểm tra thao tác trên Chrome.
