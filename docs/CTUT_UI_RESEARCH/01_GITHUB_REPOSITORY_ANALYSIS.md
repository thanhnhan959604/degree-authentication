# 01 – Phân tích repository GitHub

Ngày khảo sát: 16/11/2026. Mỗi repo được clone nông (`git clone --depth 1`) vào thư mục tạm của phiên làm việc, **không** vào dự án CTUT. Giấy phép được đọc trực tiếp từ file LICENSE trong repo và đối chiếu với GitHub API.

Ký hiệu mức độ quan sát:
- **[LIVE]** – mở bằng Chrome và chụp ảnh trực tiếp.
- **[CODE]** – đọc mã nguồn.
- **[ẢNH REPO]** – ảnh có sẵn trong repo.

## Tổng quan

| Repo | Giấy phép | Commit đã khảo sát | Framework | Thư viện UI | Live demo | Được tái sử dụng mã? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Kiranism/next-shadcn-dashboard-starter | MIT | `main` @ dd43d22 (15/11/2026) | Next.js 16.4, React 19.3, Tailwind 4.3 | shadcn/ui (Base UI), TanStack Table 9, TanStack Form, Tabler Icons | Có, trang trong bị khoá bởi Clerk | Có thể (MIT), nhưng CTUT không dùng React → chỉ học bố cục |
| shadcnstore/shadcn-dashboard-landing-template | MIT | `main` @ 8664237 (22/10/2026) | Next.js 16 và Vite (2 bản) | shadcn/ui 2.0 trên Base UI, Tailwind 4, font Inter | Có, **công khai cả trang trong** | Có thể (MIT) → chỉ học bố cục |
| zerostaticthemes/square-ui | **ln-dev UI License (riêng)** | `master` @ 8985cb6 (16/09/2026) | Next.js 16, Tailwind | Radix / Base UI, TanStack Table 8, Lucide, Geist | Có, mỗi template một demo | **Không.** Giấy phép cấm tạo "UI kit / design system based on these Templates" → chỉ quan sát nguyên tắc chung |
| OpenCerts/opencerts-website | Apache-2.0 | `master` @ f429a70 (15/10/2026) | Next.js (pages router), Tailwind, Redux-Saga | Tự xây, font Source Sans Pro + Poppins | Có (opencerts.io) | Có thể (Apache-2.0, cần giữ NOTICE) → chỉ học bố cục kết quả |
| OpenCerts/open-certificate | Apache-2.0 | `master` @ 93e8e6c (24/09/2026) | Thư viện JS + JSON Schema | Không có UI | Không | Không cần – chỉ tham khảo cấu trúc dữ liệu |
| J7-Alwin/Certiport | MIT | `main` @ f5810a9 (25/04/2026) | React 19 (Create React App), Express, MongoDB, Hardhat | CSS thuần theo từng trang, lucide-react | **Không** | Có thể (MIT) → chỉ học nghiệp vụ |

---

## 1. Kiranism – Next Shadcn Dashboard Starter

- **Link:** https://github.com/Kiranism/next-shadcn-dashboard-starter · demo https://shadcn-dashboard.kiranism.dev
- **Đã quan sát:**
  - [LIVE] trang giới thiệu và trang đăng nhập Clerk ở 1440 / 1024 / 390px.
  - [ẢNH REPO] `public/shadcn-dashboard.png`: Overview, Products table, Profile, Kanban, form "Create New Product".
  - [CODE] các file liệt kê dưới đây.
- **Hạn chế:** `/dashboard/overview` chuyển hướng tới `/auth/sign-in` (Clerk). Không tạo tài khoản, không chạy cục bộ, vì repo cần khoá Clerk hoặc phải chạy script `cleanup` để gỡ xác thực.

**Thành phần giao diện quan trọng (đã đọc mã):**

| File | Nội dung rút ra |
| :--- | :--- |
| `src/app/dashboard/layout.tsx` | Khung chung: `SidebarProvider` → `AppSidebar` + `SidebarInset` (Header + một vùng cuộn duy nhất `page-scroller`). Có link "Skip to content". Trạng thái đóng/mở sidebar lưu cookie. Thanh icon khi thu gọn rộng 2.375rem. |
| `src/components/layout/header.tsx` | Header cao 56px (`h-14`): nút thu gọn sidebar, dấu ngăn, **breadcrumb**; bên phải là tìm kiếm, theme, thông báo. |
| `src/components/layout/page-container.tsx` | Mỗi trang khai báo `pageTitle`, `pageDescription`, `pageHeaderAction`. Khoảng đệm `p-4 md:p-6`, tiêu đề cách nội dung 24px. Có sẵn **skeleton khi tải** và thông báo **"không có quyền truy cập"** (`access=false`). |
| `src/config/nav-config.ts` | Menu khai báo theo nhóm (`navGroups`). Mỗi mục có `access: { role, permission, requireOrg, plan }` → sidebar và Cmd+K **lọc theo quyền** từ một nguồn cấu hình. |
| `src/components/data-table/*` | Thanh công cụ: bộ lọc theo từng cột, nút "Reset", chọn cột hiển thị. Phân trang có "Rows per page" (10–50) và "Page x of y". |
| `src/features/users/components/users-table/cell-action.tsx` | Thao tác dòng nằm trong **dropdown "⋯"** (Edit / Delete), xoá phải qua `AlertModal` xác nhận. |
| `src/features/users/components/users-table/columns.tsx` | **Không nhất quán:** tiêu đề cột lẫn kiểu `'Name'` và `'PHONE'`, `'STATUS'` viết hoa. Đây là ví dụ cần tránh. |
| `src/features/auth/components/sign-in-view.tsx` | Đăng nhập chia đôi: trái là khối thương hiệu (logo, hoạ tiết lưới, trích dẫn), phải là form. Dưới 1024px chỉ còn form. |
| `src/styles/themes/*.css` | 8 theme bằng biến CSS (oklch), `--radius: 0.5rem`. Font đổi theo theme (ví dụ Vercel dùng Geist). |

## 2. ShadcnStore – Dashboard & Landing Template

- **Link:** https://github.com/shadcnstore/shadcn-dashboard-landing-template · demo `https://shadcnstore.com/templates/dashboard/shadcn-dashboard-landing-template/*`
- **Đã quan sát:**
  - [LIVE] ở 3 kích thước: `/dashboard`, `/dashboard-2`, `/users`, `/tasks`, `/auth/sign-in`, `/auth/sign-in-2`, `/auth/sign-in-3`, `/settings/account`, `/errors/forbidden`.
  - [LIVE] thao tác: mở hộp thoại "Add New User", menu "More actions" của dòng, bộ lọc "Select Role", thu gọn sidebar, sidebar dạng ngăn kéo trên mobile.
  - [CODE] `vite-version/src`.
- **Hạn chế:** không có. Có 2 nút nổi ("Upgrade to Pro", bánh răng theme) đè lên bảng – đây là quảng cáo của demo, không tính vào thiết kế.

| File / màn hình | Nội dung rút ra |
| :--- | :--- |
| `src/index.css` | Token: `--font-sans: Inter`, `--radius: 0.625rem`. Màu nền trắng, chữ gần đen, `--primary` gần đen. **Có sẵn token `--success`, `--warning`, `--info`, `--destructive`**, cùng nhóm token riêng cho sidebar. |
| `src/components/ui/*` | 45 component dùng chung (button, input, select, dialog, sheet, dropdown-menu, tabs, table, badge, alert, toast, skeleton, tooltip…). Mỗi trang chỉ ghép component, không tự viết CSS. |
| `app/users/components/user-form-dialog.tsx` | Hộp thoại rộng `sm:max-w-2xl`, trường xếp **2 cột** (Role / Plan, Billing / Status), nút chính "Save User" ở góc phải dưới. |
| `app/users/components/data-table.tsx` | Bộ lọc là các **Select có nhãn** (Role, Plan, Status, Column Visibility). Thao tác dòng: icon Xem, icon Sửa và menu "⋯" (View Details, Send Email, Reset Password, **đường kẻ**, **Delete User màu đỏ**). Nhãn vai trò dùng 5 màu khác nhau – **quá nhiều màu**, CTUT không nên theo. |
| `/auth/sign-in`, `-2`, `-3` | 3 kiểu: (1) thẻ giữa màn hình, logo phía trên; (2) chia đôi, form trái, ảnh phải; (3) một thẻ gồm 2 ô form + ảnh. Cả 3 đều có "Forgot your password?" nằm cùng hàng với nhãn mật khẩu. |
| `/settings/account` | Form chia **khối có tiêu đề + mô tả** (Personal Information, Change Password, Danger Zone). Khối nguy hiểm tách riêng ở cuối. |
| `/errors/forbidden` | Trang 403 đơn giản: mã lỗi, tiêu đề, một câu giải thích, 2 nút (về trang chủ, liên hệ). |

## 3. Square UI

- **Link:** https://github.com/zerostaticthemes/square-ui · danh mục https://square.lndevui.com
- **Giấy phép:** file `LICENSE.md` là **"ln-dev UI License"**, không phải giấy phép mã nguồn mở. Giấy phép cho phép dùng trong sản phẩm cuối, nhưng **cấm** "Create or distribute a UI kit, component library, template collection, or design system based on these Components or Templates".
  - **Kết luận:** CTUT **không lấy mã, không dựa design system vào Square UI.** Chỉ ghi nhận các nguyên tắc bố cục phổ biến mà nhiều nguồn khác cũng có.
- **Đã quan sát:**
  - [LIVE] 4 template miễn phí ở 3 kích thước: Dashboard 1, Dashboard 2 (CRM "Cliento"), Employees, Leads.
  - [LIVE] trang danh mục và demo Pro "Skyport" (chỉ xem).
  - [CODE] `templates/dashboard-2/components/dashboard/*` (sidebar, header, stats-cards, deals-table).
- **Hạn chế:** khi lăn chuột, trang không cuộn vì dùng vùng cuộn nội bộ, nên ảnh "scrolled" gần như không đổi.

| Quan sát | Ghi chú |
| :--- | :--- |
| Mật độ cao: chữ bảng 14px, đệm ô 8px, dòng 49px (đo bằng `getComputedStyle`); 4 thẻ số liệu mỗi hàng, icon nằm phải | Phù hợp người dùng chuyên nghiệp xem nhiều số liệu |
| Biểu đồ chiếm nửa trên trang | **Không phù hợp CTUT** – nghiệp vụ văn bằng là xử lý hồ sơ, không phải phân tích |
| Thanh công cụ bảng: tìm kiếm + Filter + Columns + Import | Gọn, mọi bộ lọc dồn vào một nút |
| Sidebar: chọn workspace ở đầu, nhóm menu, mục yêu thích, Help / Settings ở đáy | Phân nhóm rõ ràng |
| Mobile 390px: thẻ số liệu xếp 1 cột | Phải cuộn rất xa mới tới bảng – **nên tránh** |

## 4. OpenCerts – Website xác minh

- **Link:** https://github.com/OpenCerts/opencerts-website · https://www.opencerts.io
- **Đã quan sát:**
  - [LIVE] trang chủ ở 3 kích thước.
  - [LIVE] **chứng chỉ demo hợp lệ**: ở 390px qua nút chính thức "Click me for a demo certificate!"; ở 1440 và 1024px qua ô chọn file với file demo chính thức `/static/demo/homestead.opencert`.
  - [LIVE] mở khối chi tiết kiểm tra.
  - [LIVE] **trạng thái không hợp lệ**: do người nghiên cứu nạp nhầm file demo của mạng Sepolia.
  - [CODE] `src/components/CertificateVerifyBlock/*`, `CertificateDropZone/*`, `tailwind.config.js`.
- **Hạn chế:** không có.

| Thành phần | Nội dung rút ra |
| :--- | :--- |
| Khối kết luận (`CertificateVerifyBlock.tsx`) | **Một dòng kết luận** có icon và màu: "Certificate issued by OPENCERTS.IO" (xanh). Bấm vào mở "Details" với từng bước kiểm tra có dấu ✓: "Certificate has not been tampered with", "Certificate has not been revoked". Tên đơn vị cấp lấy từ bằng chứng tên miền (DNS-TXT); nếu không xác định được thì hiện "Unknown". |
| Trạng thái lỗi (`CertificateDropZone/Views`) | Khung đỏ nét đứt, tiêu đề "This certificate is not valid", **lý do cụ thể** ("Certificate store address cannot be found"), một câu hướng dẫn, nút "What should I do?" và "Try another". |
| Thao tác sau xác minh | Print, Email, Download; tab Certificate / Transcript / Media; nút "View another". |
| Typography (`tailwind.config.js`) | Thang cỡ chữ 14/16/18/20/24/32/40px, line-height ghi kèm từng cỡ. |

## 5. Open Certificate

- **Link:** https://github.com/OpenCerts/open-certificate
- **Đã quan sát:** [CODE] `README.md`, `schema/*`, `src/index.js`. Repo không có giao diện.
- **Cấu trúc chứng chỉ** (từ `schema/certificate-of-awards/1.0/example.json`):
  - `id`, `issuedOn`, `name`, `description`.
  - `issuers[]`: `name`, `did`, `url`, `email`, `documentStore`, `identityProof { type: DNS-TXT, location }`.
  - `recipient`: `name`, `nric` (số định danh), `studentId`.
  - `award`, và `signature { name, designation }`.
- **Kiểm tra:** `validateSchema` (đúng cấu trúc) → `verifySignature` (không bị sửa) → `certificateData` (lấy nội dung).
- **Ẩn thông tin cá nhân:** `obfuscateFields(certificate, paths[])` ẩn trường theo đường dẫn JSON. Chứng chỉ vẫn xác minh được, vì mỗi trường được băm kèm muối.
  - Đây đúng là mô hình CTUT đang dùng: CCCD chỉ lưu dạng đã che, dấu băm có muối, ảnh công khai đã che thông tin.

## 6. Certiport

- **Link:** https://github.com/J7-Alwin/Certiport
- **Đã quan sát:**
  - [CODE] `frontend/certiport-frontend/src`: 7 trang, CSS riêng từng trang, khoảng 8.400 dòng.
  - [ẢNH REPO] 15 ảnh giao diện trích từ `Certiport-documentation.pdf`: đăng nhập, đăng ký, trang giới thiệu, xác minh công khai, dashboard trường, form cấp văn bằng, bảng văn bằng đã cấp, dashboard sinh viên, dashboard quản trị, duyệt đăng ký trường.
- **Hạn chế:** không có live demo. Các trang dashboard cần JWT từ backend thật. Không chạy cục bộ, không giả token.

| Thành phần | Nội dung rút ra |
| :--- | :--- |
| Routes (`App.js`) | `/` giới thiệu, `/verify` xác minh công khai, `/login`, `/register`, `/university`, `/student`, `/admin` |
| Đăng nhập (`Login.js`) | **Không chọn vai trò khi đăng nhập**; vai trò lấy từ tài khoản sau khi đăng nhập rồi chuyển trang. Đây cũng là yêu cầu của CTUT. |
| Đăng ký (`Register.js`) | Có ô "I am a" để **tự chọn vai trò** – CTUT **không được làm** như vậy. |
| Dashboard trường | 3 tab: Upload Templates / Issue Certificates / Issued Certificates. Bảng đã cấp có lọc theo từ khoá, loại, khoá học, khoảng ngày; trạng thái ISSUED; nút View / Revoke. |
| Dashboard sinh viên | Lưới thẻ văn bằng, mỗi thẻ có Blockchain ID kèm nút sao chép, nút View / Download |
| Xác minh công khai | Ô nhập Blockchain ID hoặc tải ảnh QR, khối "How it works" 3 bước |
| Màu và kiểu chữ | `#667eea` (tím, 28 lần), `#37bde6`, nền `#0e1123`, nút cam, gradient tím trên thẻ. Font: Poppins, hệ thống, Courier New. **Quá nhiều gradient và màu – không phù hợp phong cách CTUT.** |

## Kết luận về nguồn

- **Tham khảo bố cục chính:** Kiranism (cấu trúc khung, cấu hình menu theo quyền, khung trang) và ShadcnStore (component, form, bảng, đăng nhập – quan sát trực tiếp được nhiều nhất).
- **Tham khảo nghiệp vụ xác minh:** OpenCerts website + Open Certificate.
- **Tham khảo nghiệp vụ văn bằng blockchain:** Certiport (luồng và phân vai, **không** học phong cách hình ảnh).
- **Square UI:** chỉ ghi nhận nguyên tắc chung, không dựa vào do giấy phép.
