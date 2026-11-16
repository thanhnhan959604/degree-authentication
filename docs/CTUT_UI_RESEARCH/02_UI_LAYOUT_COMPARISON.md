# 02 – So sánh bố cục giữa các nguồn

Cột **CTUT hiện tại** mô tả giao diện sau đợt chuẩn hoá frontend và Đợt 1 (bảng điều khiển), theo ảnh trong `docs/images/ui_after_*.png` và `docs/images/d1_after_*.png`. Mọi nhận xét về nguồn khác đều dẫn chiếu tới ảnh trong `screenshots/` hoặc file mã đã ghi ở [01](01_GITHUB_REPOSITORY_ANALYSIS.md).

## Header

| Nguồn | Quan sát | Bằng chứng |
| :--- | :--- | :--- |
| Kiranism | Cao 56px, nằm **trong vùng nội dung** (không vắt ngang sidebar). Trái: nút thu gọn + breadcrumb. Phải: tìm kiếm ⌘K, theme, thông báo. | `header.tsx` |
| ShadcnStore | Cùng mô hình: nút thu gọn, ô tìm kiếm, liên kết, nút theme. Không có breadcrumb; tiêu đề trang nằm ở nội dung. | `dashboard/shadcnstore__dashboard__1440.png` |
| Square UI | Header mảnh, chứa tiêu đề trang + nút hành động chính ("New Project", "Export"). | `dashboard/squareui__dashboard-1__1440.png` |
| OpenCerts | Header màu xanh đá đậm, chỉ có logo + FAQ. | `verification/opencerts__home__1440.png` |
| Certiport | Thanh trắng: logo, "Verify Certificate", "Dashboard", lời chào, nút Logout. | `dashboard/certiport__university-dashboard__pdf.png` |
| **CTUT hiện tại** | Header navy vắt ngang toàn màn hình: logo, tên hệ thống, "Tra cứu văn bằng", "Bảng điều khiển", menu tài khoản kèm vai trò. Breadcrumb nằm trong nội dung. | `docs/images/d1_after_admin_desktop.png` |

**Nhận xét:** các dashboard hiện đại (Kiranism, ShadcnStore) đặt header bên trong vùng nội dung để sidebar chạy hết chiều cao. CTUT dùng header ngang toàn trang, giống mô hình cổng thông tin cơ quan (OpenCerts, Cổng Dịch vụ công). Với hệ thống có cả phần công khai lẫn phần nghiệp vụ, **header ngang thống nhất cho mọi phân hệ là lựa chọn hợp lý hơn**: người dùng luôn thấy nhận diện CTUT, tra cứu công khai và tài khoản ở cùng một chỗ.

## Sidebar

| Nguồn | Quan sát | Bằng chứng |
| :--- | :--- | :--- |
| Kiranism | Nhóm menu có nhãn. Mục khai báo trong `nav-config.ts`, lọc theo `role / permission`. Thu gọn thành thanh icon 38px. | `nav-config.ts`, `layout.tsx` |
| ShadcnStore | Nhóm "Dashboards / Apps / Pages", mục có icon nét mảnh, mục con mở rộng bằng mũi tên. Khi thu gọn thì **ẩn hẳn**; trên mobile là ngăn kéo có nền mờ. | `sidebar/shadcnstore__sidebar-*.png` |
| Square UI | Chọn workspace ở đầu, nhóm menu, mục yêu thích / thư mục, Help và Settings ở đáy. | `sidebar/squareui__*-sidebar__1440.png` |
| Certiport | Không có sidebar; điều hướng bằng tab ngang trong trang. | `dashboard/certiport__university-dashboard__pdf.png` |
| **CTUT hiện tại** | Sidebar trắng 256px, nhóm "Hồ sơ văn bằng / Nhập liệu / Hệ thống", số đếm từng mục, đánh dấu mục đang lọc. Trên mobile là ngăn kéo (Esc hoặc chạm nền để đóng). | `components/sidebar.html` |

**Nhận xét:** CTUT đã theo đúng mô hình nhóm menu kèm lọc theo vai trò. Điểm nên học thêm từ Kiranism: **khai báo menu ở một nơi** thay vì viết điều kiện `{% if r == ... %}` rải trong template.

## Dashboard và thẻ số liệu

| Nguồn | Quan sát |
| :--- | :--- |
| Kiranism | 4 thẻ: tiêu đề nhỏ, số lớn, nhãn xu hướng (+12.5%), 2 dòng mô tả. Bên dưới là biểu đồ. |
| ShadcnStore | Như Kiranism. Trang Users: 4 thẻ có icon trái + nhãn xu hướng phải. |
| Square UI | 4 thẻ gọn (nhãn, số, icon phải), biểu đồ lớn ngay dưới. |
| Certiport | 4 thẻ **gradient tím / hồng** đậm, chữ trắng. |
| **CTUT hiện tại** | 4–6 thẻ trắng đều nhau (nhãn 12px, số 24px). Thẻ đang lọc có viền xanh, thẻ cần chú ý chỉ tô đỏ con số. Không có biểu đồ. |

**Nhận xét:** nhãn xu hướng (+12.5%) và biểu đồ phục vụ kinh doanh, **không mang thông tin nghiệp vụ** với hồ sơ văn bằng. CTUT nên giữ thẻ đơn giản như hiện tại, mỗi thẻ là một hàng đợi bấm được.

## Bảng dữ liệu

| Nguồn | Tìm kiếm / lọc | Thao tác dòng | Phân trang | Nhãn trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| Kiranism | Lọc theo từng cột + "Reset", chọn cột hiển thị, trạng thái lưu trên URL (`nuqs`) | Menu "⋯" + hộp xác nhận khi xoá | "Rows per page" 10–50, "Page x of y" | Badge trung tính |
| ShadcnStore | Ô tìm kiếm + 3 Select có nhãn + chọn cột | Icon xem, icon sửa, menu "⋯" (mục nguy hiểm màu đỏ, tách bằng đường kẻ) | "0 of 15 row(s) selected" + chuyển trang | 5 màu cho 5 vai trò – **quá nhiều** |
| Square UI | Tìm kiếm + nút Filter + Columns + Import | Menu "⋯" | Có (Dashboard 2) | Nhãn màu theo phòng ban |
| Certiport | Từ khoá + loại + khoá học + khoảng ngày | 2 nút chữ "View" (xanh), "Revoke" (đỏ) | Không thấy | "ISSUED" xanh lá |
| **CTUT hiện tại** | Ô tìm kiếm + ô chọn trạng thái (tự lọc), số hồ sơ | 1 nút chính (Duyệt / Ký phát hành) + menu "⋯" (mục nguy hiểm màu đỏ, tách bằng đường kẻ) | **Chưa có** | Một hệ nhãn (đã cấp / thu hồi / hủy / thay thế) + chấm tiến trình |

**Nhận xét:** thao tác dòng của CTUT đã trùng với mẫu tốt nhất quan sát được (ShadcnStore + Kiranism). Còn thiếu **phân trang** và **lưu bộ lọc trên URL** – thực ra CTUT đã lưu `?filter=&s=` trên URL, chỉ còn thiếu phân trang.

## Form và hộp thoại

| Nguồn | Quan sát |
| :--- | :--- |
| ShadcnStore – Add User | Hộp thoại rộng (~672px), trường **2 cột**, nhãn trên ô, nút chính góc phải dưới, có nút đóng ×. |
| ShadcnStore – Account Settings | Chia khối có tiêu đề + mô tả. **Khối nguy hiểm tách riêng ở cuối.** |
| Kiranism – Create Product | Form toàn trang, ô tải ảnh lớn ở đầu. |
| Certiport – Issue Certificate | Form dài 1 cột trong tab, ô nhập viền mảnh, dấu `*` cho trường bắt buộc. |
| **CTUT hiện tại** | Hộp thoại Bootstrap kiểu cũ, chưa theo design system (dự kiến Đợt 3). |

## Đăng nhập

Xem chi tiết ở [03](03_LOGIN_PAGE_RESEARCH.md). Tóm tắt:

| Nguồn | Bố cục |
| :--- | :--- |
| ShadcnStore #1 | Thẻ giữa màn hình, logo trên thẻ |
| ShadcnStore #2 / Kiranism | Chia đôi: form + khối thương hiệu / ảnh |
| ShadcnStore #3 | Một thẻ gồm 2 ô (form + ảnh) |
| Certiport | Thẻ giữa trên nền gradient tím, nút cam |
| **CTUT hiện tại** | Logo + tên trường ở đầu, 3 thẻ nhóm tài khoản, form hiện sau khi chọn nhóm, thông báo bảo mật, khối "Tra cứu văn bằng công khai" |

## Responsive

| Nguồn | 1024px | 390px |
| :--- | :--- | :--- |
| ShadcnStore | Sidebar vẫn hiện, thẻ số liệu chuyển 2 cột | Sidebar thành ngăn kéo; thẻ số liệu 1 cột, rất cao (icon + số + xu hướng) |
| Square UI | Sidebar vẫn hiện | Thẻ số liệu 1 cột, nút đầu trang rất lớn |
| Kiranism (đăng nhập) | Bỏ khối thương hiệu, chỉ còn form | Chỉ còn form |
| OpenCerts | Ô kéo-thả thu nhỏ | Thay ô kéo-thả bằng nút "Click me for a demo certificate!" |
| **CTUT hiện tại** | Sidebar thành ngăn kéo dưới 992px | Thẻ số liệu 2 cột; bảng hồ sơ chuyển thành thẻ; không cuộn ngang |

**Nhận xét:** trên mobile, cả ShadcnStore và Square UI đều để thẻ số liệu chiếm gần hết màn hình đầu tiên. Cách 2 cột của CTUT giúp người dùng tới danh sách hồ sơ nhanh hơn.
