# 04 – Nghiên cứu Dashboard, bảng dữ liệu và form

Nguồn chính: ShadcnStore [LIVE + CODE], Kiranism [CODE + ẢNH REPO], Square UI [LIVE, chỉ quan sát], Certiport [ẢNH REPO + CODE].

## 1. Cấu trúc trang dashboard

Mọi nguồn có cùng một trình tự từ trên xuống:

1. Breadcrumb (Kiranism) hoặc tiêu đề trong header (Square UI).
2. **Tiêu đề trang + mô tả 1 dòng + nút hành động chính ở bên phải.** Kiranism ép bố cục này qua `PageContainer` (`pageTitle`, `pageDescription`, `pageHeaderAction`).
3. Hàng thẻ số liệu (4 thẻ ở mọi nguồn).
4. Nội dung chính: biểu đồ (Kiranism, ShadcnStore, Square UI) hoặc bảng (trang Users / Tasks / Employees).

**Áp dụng cho CTUT:** giữ 1 → 2 → 3, còn bước 4 là **bảng hồ sơ**, không có biểu đồ. Nghiệp vụ là xử lý hàng đợi hồ sơ. Biểu đồ xu hướng không giúp cán bộ duyệt nhanh hơn, và với khoảng chục hồ sơ mỗi đợt thì không có ý nghĩa thống kê.

## 2. Thẻ số liệu

| Đặc điểm | ShadcnStore / Kiranism | Square UI | Certiport | Kết luận cho CTUT |
| :--- | :--- | :--- | :--- | :--- |
| Thành phần | Nhãn, số lớn, nhãn xu hướng %, 1–2 dòng mô tả | Nhãn, số, icon | Icon, số, nhãn trên nền gradient | Nhãn + số. Không xu hướng, không icon trang trí |
| Bấm được | Không | Không | Không | **Có** – mỗi thẻ là một bộ lọc (CTUT đã làm ở Đợt 1) |
| Màu | Trung tính; xu hướng xanh / đỏ | Trung tính | Gradient tím / hồng | Trung tính; chỉ tô màu con số khi cần chú ý |

## 3. Bảng dữ liệu

Bằng chứng: `dashboard/shadcnstore__users-table__1440.png`, `dashboard/shadcnstore__users-row-menu__1440.png`, `dashboard/shadcnstore__users-filter__1440.png`, `src/components/data-table/*` (Kiranism), `dashboard/certiport__issued-table__pdf.png`.

| Hạng mục | Mẫu tốt quan sát được | Mẫu cần tránh |
| :--- | :--- | :--- |
| Thanh công cụ | Ô tìm kiếm có icon bên trái; bộ lọc là Select **có nhãn**; nút "Reset" chỉ hiện khi đang lọc (Kiranism) | Certiport: 5 ô lọc cùng hàng, không có nhãn |
| Tiêu đề cột | Viết hoa đầu câu, có nút sắp xếp ở cột dài (Name, Joined Date) | Kiranism `users-table/columns.tsx` trộn `'Name'` với `'PHONE'`, `'STATUS'` |
| Ô nhiều dòng | Dòng chính đậm vừa + dòng phụ nhỏ màu xám (User: tên + email) | Nhồi 4 dòng thông tin vào một ô |
| Thao tác dòng | 1–2 thao tác hay dùng + menu "⋯"; mục nguy hiểm đỏ, tách bằng đường kẻ, cuối menu (ShadcnStore). Xoá phải qua hộp xác nhận (Kiranism `AlertModal`) | Certiport: nút "Revoke" đỏ đặc nằm cạnh "View" trên mọi dòng → dễ bấm nhầm |
| Nhãn trạng thái | Pill nhỏ, nền nhạt, chữ đậm màu (Active / Pending / Inactive) | ShadcnStore: 5 màu cho 5 vai trò |
| Phân trang | "Rows per page" + "Page x of y" + nút trước / sau (Kiranism `data-table-pagination.tsx`) | — |
| Trạng thái rỗng / đang tải | Skeleton khi tải (`data-table-skeleton.tsx`, `PageContainer`); thông báo khi không có quyền | — |

## 4. Form và hộp thoại

Bằng chứng: `forms/shadcnstore__users-add-dialog__1440.png`, `forms/shadcnstore__settings-account__1440.png`, `forms/certiport__issue-certificate-form__pdf.png`, `user-form-dialog.tsx`.

- **Hộp thoại tạo / sửa:** rộng khoảng 672px; trường ngắn xếp 2 cột (Role / Plan); nhãn nằm trên ô; nút chính ở góc phải dưới; có nút đóng ×.
- **Form dài:** chia khối có tiêu đề + 1 dòng mô tả; **khối nguy hiểm tách riêng ở cuối** (ShadcnStore "Danger Zone").
- **Thao tác nguy hiểm** (xoá, thu hồi): luôn qua hộp xác nhận riêng, nêu rõ đối tượng bị tác động.
- **Thông báo kết quả:** Kiranism dùng `sonner` (toast góc màn hình). CTUT dùng thông báo đầu trang (Django messages), vẫn phù hợp vì mỗi thao tác đều tải lại trang.

## 5. Trang lỗi

`forms/shadcnstore__error-forbidden__1440.png`: mã lỗi, tiêu đề, một câu giải thích, 2 nút hành động. CTUT nên có trang 403 / 404 cùng mẫu này, thay cho trang mặc định của Django.

## 6. Mật độ và khoảng cách (đo bằng `getComputedStyle` trên live demo, viewport 1440px)

| Nguồn | Chữ ô / tiêu đề cột | Đệm ô (trên) | Chiều cao dòng | Tiêu đề cột viết hoa? |
| :--- | :--- | :--- | :--- | :--- |
| ShadcnStore Users (ô 2 tầng: tên + email) | 14px / 14px | 8px | 57px | Không |
| ShadcnStore Tasks (ô 1 tầng) | 14px / 14px | 8px | 49px | Không |
| Square UI Dashboard 2, Employees | 14px / 14px | 8px | 49px | Không |
| Kiranism | `text-sm` = 14px (đọc từ mã) | — | — | Lẫn lộn (xem mục 3) |
| **CTUT sau Đợt 1** | 14px (phụ 12px) / 12px | 14px | 72px (2 tầng) | Không |

**Kết luận:**
- Cả 3 nguồn đo được đều dùng chữ 14px, đệm ô 8px, tiêu đề cột không viết hoa.
- CTUT đang thoáng hơn: dòng cao 72px so với 57px của ShadcnStore cho cùng kiểu ô 2 tầng.
- Nếu muốn mật độ tương đương, hạ đệm ô của CTUT từ 14px xuống khoảng 8–10px (dòng còn khoảng 60px).
