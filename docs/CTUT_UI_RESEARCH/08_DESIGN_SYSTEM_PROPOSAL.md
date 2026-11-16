# 08 – Đề xuất Design System CTUT

Phong cách: **Modern Technology – Minimal Enterprise – Institutional UI**. Nền sáng, một màu nhấn, màu trạng thái chỉ dùng để báo trạng thái, chữ dễ đọc, không gradient, không hiệu ứng trang trí.

Mọi giá trị dưới đây đều có lý do kèm nguồn. Phần lớn đã có sẵn trong `web/static/css/design-system.css`, nên đề xuất chủ yếu là **khoá lại và ghi thành quy chuẩn**, không làm lại từ đầu.

## 1. Bảng màu chính thức

Màu chủ đạo của logo CTUT đo được là xanh chàm, khoảng `#3020A0` (đếm màu điểm ảnh của `web/static/img/ctut-logo.png`, bỏ nền trắng). Độ tương phản tính theo công thức WCAG 2.1.

| Token | Màu | Dùng cho | Tương phản trên nền trắng |
| :--- | :--- | :--- | :--- |
| `--ds-bg` | `#F8FAFC` | Nền trang | — |
| `--ds-surface` | `#FFFFFF` | Thẻ, bảng, hộp thoại | — |
| `--ds-surface-muted` | `#F1F5F9` | Đầu bảng, vùng phụ | — |
| `--ds-border` | `#E2E8F0` | Viền mặc định | 1,23 (chỉ để kẻ viền) |
| `--ds-border-strong` | `#CBD5E1` | Viền khi rê chuột, chấm tiến trình chưa tới | 1,48 |
| `--ds-primary` | `#172B4D` | Header, mục sidebar đang chọn, tiêu đề, chấm "đã qua" | 14,10 |
| `--ds-accent` | `#2563EB` | **Màu nhấn duy nhất:** nút chính, liên kết, focus, mục đang chọn | 5,17 |
| `--ds-text` | `#0F172A` | Chữ chính | 17,85 |
| `--ds-text-2` | `#334155` | Chữ thường trong bảng | 10,35 |
| `--ds-text-muted` | `#64748B` | Chữ phụ, nhãn | 4,76 (4,55 trên `#F8FAFC`) |
| `--ds-success` / nền | `#15803D` / `#F0FDF4` | Đã cấp, hợp lệ | 4,79 trên nền nhạt |
| `--ds-warning` / nền | `#B45309` / `#FFFBEB` | Chờ duyệt, chưa phát hành | 4,84 |
| `--ds-danger` / nền | `#B91C1C` / `#FEF2F2` | Thu hồi, bị trả về, thao tác nguy hiểm | 5,91 |
| `--ds-neutral` / nền | `#475569` / `#F1F5F9` | Đã hủy, đã thay thế, không tìm thấy | 6,92 |

**Lý do giữ `#2563EB` làm màu nhấn, thay vì đổi sang xanh chàm của logo:**
1. Xanh chàm `#3020A0` có tương phản 11,41 – rất tối, gần với navy `#172B4D` và chữ `#0F172A`. Liên kết và nút sẽ khó phân biệt với chữ thường.
2. Cả 3 nguồn dashboard đều tách "màu khung" (gần đen / navy) khỏi "màu hành động" (một màu sáng hơn).
3. Xanh chàm lệch về tím. Certiport (`#667eea`) cho thấy tông tím + gradient làm giao diện thiếu nghiêm túc với một cơ sở giáo dục.

Màu logo vẫn xuất hiện nguyên vẹn trên nền trắng của logo ở header. Navy `#172B4D` cùng nhóm lạnh với logo nên hài hoà.

**Quy tắc màu:**
- Một trang chỉ có **một loại nút đặc** (`btn-primary` màu nhấn). Mọi nút khác là viền hoặc nằm trong menu.
- Màu trạng thái **chỉ** dùng trong nhãn trạng thái, khối kết luận xác minh và mục nguy hiểm của menu. Không tô cả thẻ hay cả dòng.
- **Cấm** `#94A3B8` cho chữ (tương phản 2,56 < 4,5). Hiện vẫn còn ở nhãn nhóm sidebar (`.ds-nav-label`) – cần sửa.
- Không gradient, không bóng đổ trên nút (đã áp dụng ở Đợt 1).

## 2. Typography

| Hạng mục | Quy chuẩn | Lý do / nguồn |
| :--- | :--- | :--- |
| Font | **Inter** cho mọi chữ, kể cả tiêu đề | Đã kiểm tra Google Fonts trả về bộ ký tự `vietnamese` cho Inter 400–700. ShadcnStore dùng Inter (`--font-sans: var(--font-inter)`). Một font giúp giảm tải trang. |
| Font số / mã | `ui-monospace, SFMono-Regular, Consolas` | Chỉ cho mã băm, mã giao dịch, mã xác minh. Không tải font ngoài. |
| Thang cỡ chữ | 12 · 14 · 16 · 20 · 24px | 14px là cỡ chữ bảng ở cả 3 nguồn đo được ([04](04_DASHBOARD_RESEARCH.md) mục 6) |
| Độ đậm | 400 thường · 500 nhấn nhẹ · 600 tiêu đề, số liệu | Không dùng 700 trong vùng nội dung, trừ tên trường trên header |
| Line height | 1,5 cho chữ thường; 1,3 cho tiêu đề | Dấu tiếng Việt (ẳ, ỗ, ự) cần khoảng trống phía trên |
| Viết hoa | Viết hoa đầu câu ở mọi nơi; không viết hoa toàn bộ, trừ nhãn nhóm sidebar 11–12px | Đợt 1 đã bỏ 13 chỗ viết hoa toàn bộ |

| Cấp | Cỡ / đậm | Dùng cho |
| :--- | :--- | :--- |
| Tiêu đề trang | 24 / 600 | `ds-page-title` |
| Tiêu đề khối | 16 / 600 | Tiêu đề thẻ, hộp thoại |
| Nội dung | 14 / 400–500 | Bảng, form, mô tả |
| Phụ | 12 / 400–500 | Dòng phụ trong ô, nhãn thẻ số liệu, tiêu đề cột |
| Số liệu | 24 / 600 | Thẻ số liệu |

## 3. Layout

| Thành phần | Quy chuẩn |
| :--- | :--- |
| Header | Cao 60px, nền navy, vắt ngang mọi phân hệ: logo + "CTUT · Cổng xác minh văn bằng" (mobile chỉ "CTUT"), "Tra cứu văn bằng", menu tài khoản kèm vai trò |
| Sidebar | 256px, nền trắng, nhóm có nhãn, mục cao khoảng 40px (đệm 8px), mục đang chọn nền `--ds-primary-soft` `#E8EDF5` + chữ navy đậm, số đếm bên phải. Dưới 992px: ngăn kéo có nền mờ, đóng bằng Esc. **Cần sửa:** nhãn nhóm hiện dùng `#94A3B8` (tương phản 2,56) → đổi sang `--ds-text-muted`. |
| Vùng nội dung | Rộng tối đa 1280px; đệm 24px trên / 32px hai bên ở desktop, 16px ở mobile (như CSS hiện tại) |
| Breadcrumb | Trên tiêu đề trang, 12–13px, màu phụ |
| Tiêu đề trang | Tiêu đề + 1 dòng mô tả bên trái, nút hành động bên phải (mẫu `PageContainer` của Kiranism) |
| Lưới | Bootstrap 12 cột; trang chi tiết chia 7/5; thẻ số liệu dùng `grid auto-fit minmax(150px, 1fr)` |
| Khoảng cách | Bội số 4: 4 · 8 · 12 · 16 · 24 · 32 · 48px |
| Bo góc | 8px (`--ds-radius`: nút, ô nhập, thẻ, bảng, menu) · 12px (`--ds-radius-lg`: hộp thoại) · 999px (nhãn trạng thái) – đúng như CSS hiện tại |
| Footer | Logo + tên trường + liên kết tra cứu; mờ, không màu nhấn |

## 4. Component

| Component | Quy chuẩn |
| :--- | :--- |
| Button | Đặc (màu nhấn) cho hành động chính; viền xám cho hành động phụ; chữ đỏ trong menu cho thao tác nguy hiểm. Cao 40px (nhỏ 32px). Nhãn là động từ ("Duyệt", "Ký phát hành"). Nút chỉ có icon phải có `aria-label` và tooltip. |
| Input / Select | Cao 40px, viền `--ds-border`, focus viền xanh + vòng 3px. Nhãn trên ô; dấu `*` cho trường bắt buộc; lỗi đỏ 12px ngay dưới ô. |
| Search | Ô có icon kính lúp bên trái; Enter để tìm; nút × xoá từ khoá khi có giá trị. |
| Card | Nền trắng, viền 1px, bo 8px, không bóng (bóng chỉ dành cho hộp thoại và menu). |
| Table | Tiêu đề cột 12px viết hoa đầu câu; ô 2 tầng (chính 14px + phụ 12px); 1 nút chính + menu "⋯"; không quá 6 cột; dưới 768px chuyển thành thẻ. |
| Pagination | "Hiển thị 1–20 / 134 hồ sơ" + chọn số dòng (20/50/100) + trước / sau (theo Kiranism). **Cần sửa view** – chờ duyệt riêng. |
| Modal | Rộng 560px (xác nhận) hoặc 720px (form); tiêu đề nêu đối tượng; nút huỷ trái, nút chính phải; thao tác nguy hiểm dùng nút đỏ + lý do bắt buộc. |
| Tabs | Gạch chân màu nhấn cho tab đang chọn (OpenCerts); trên mobile có thể chuyển thành nút ngang. |
| Dropdown | Bóng `--ds-shadow-md`; mục có icon 16px; mục nguy hiểm cuối, chữ đỏ, tách bằng đường kẻ (ShadcnStore). |
| Status badge | Một component duy nhất (`components/status_badge.html`): pill, nền nhạt, chữ đậm màu, icon nhỏ. 4 nhóm: success / warning / danger / neutral. |
| Alert | Viền + nền nhạt theo loại, icon đầu dòng, nút đóng không đè chữ. |
| Notification | Giữ Django messages đầu trang (mỗi thao tác đều tải lại trang); không thêm toast. |
| Diploma viewer | Một component cho 3 chế độ (công khai / sinh viên / cán bộ); thanh công cụ thu phóng; nhãn nói rõ đang xem ảnh nào ("Ảnh đã che thông tin", "Ảnh gốc", "Mẫu minh hoạ DEMO"); khung co theo tỉ lệ ảnh. |
| Empty state | Icon nét mảnh + 1 câu + 1 nút hành động (nếu vai trò được phép). |
| Loading state | Nút đang gửi: vô hiệu + chữ "Đang xử lý…" (chống bấm 2 lần khi ghi blockchain); ảnh văn bằng: khung xám cùng kích thước. |
| Error state | Trang 403 / 404 / 500 theo mẫu ShadcnStore: mã lỗi, tiêu đề, 1 câu, nút "Về trang chủ" và "Tra cứu văn bằng". |

## 5. Icon

- **Bootstrap Icons 1.11.3** – giữ nguyên, không thêm thư viện.
  - Kiranism dùng Tabler; ShadcnStore, Square UI và Certiport dùng Lucide. Cả hai đều là icon nét mảnh, nên chuyển đổi không đem lại lợi ích.
- **Biến thể nét (outline)** cho menu, nút, thanh công cụ. **Biến thể đặc (`-fill`)** chỉ dùng trong nhãn trạng thái và khối kết luận xác minh.
- Cỡ 16px ở nút, menu và sidebar (sidebar dành khung rộng 18px để các icon thẳng hàng).

## 6. Responsive

| Kích thước | Header | Sidebar | Thẻ số liệu | Bảng | Trang chi tiết |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Desktop 1440 | Đầy đủ | Cố định 256px | 4–6 thẻ một hàng | Đủ cột | 7/5 |
| Laptop 1280 | Đầy đủ | Cố định | 4–6 thẻ (auto-fit) | Đủ cột | 7/5 |
| Tablet 768–1024 | Ẩn dòng tên trường | Ngăn kéo (dưới 992px) | 3 thẻ một hàng | Đủ cột, cuộn ngang trong thẻ nếu cần | 1 cột |
| Mobile 390 | Logo + "CTUT" + tìm kiếm + tài khoản | Ngăn kéo | 2 cột, thẻ lẻ cuối chiếm cả hàng | **Thẻ hồ sơ**, nút ở cuối | 1 cột, kết luận / thông tin trước, ảnh sau |
