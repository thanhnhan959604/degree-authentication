# 03 – Nghiên cứu trang đăng nhập

## Nguồn đã quan sát

| Nguồn | Mức độ | Ảnh |
| :--- | :--- | :--- |
| ShadcnStore sign-in 1, 2, 3 | [LIVE] 1440 / 1024 / 390 | `screenshots/login/shadcnstore__sign-in-*` |
| Kiranism (Clerk) | [LIVE] 1440 / 1024 / 390 + [CODE] `sign-in-view.tsx` | `screenshots/login/kiranism__sign-in__*` |
| Certiport | [ẢNH REPO] + [CODE] `Login.js`, `Register.js` | `screenshots/login/certiport__*__pdf.png` |
| Cổng Dịch vụ công Quốc gia | **Không quan sát được.** `dichvucong.gov.vn` trả về "Request Rejected" với trình duyệt tự động. Ảnh mà yêu cầu nhắc tới **chưa được đính kèm** trong hội thoại. Phần đối chiếu dưới đây dựa trên mô tả bằng chữ trong yêu cầu: logo, tên hệ thống, "Đăng nhập", các nhóm tài khoản. | — |

## Quan sát theo từng thành phần

| Thành phần | ShadcnStore | Kiranism | Certiport | Ghi nhận cho CTUT |
| :--- | :--- | :--- | :--- | :--- |
| Logo và tên | Logo nhỏ trên thẻ (#1, #3) hoặc góc trái (#2) | Logo góc trái trên khối thương hiệu | Icon trên thẻ | Logo + **tên trường đầy đủ** + tên hệ thống ở đầu trang, căn giữa (theo mô tả Cổng Dịch vụ công) |
| Tiêu đề | "Welcome back" / "Login to your account" + một dòng mô tả | "Sign in to …" + "Welcome back!" | "Welcome Back" | Một tiêu đề "Đăng nhập" + một dòng hướng dẫn |
| Nhóm tài khoản | Không có | Không có | Không có ở trang đăng nhập; trang đăng ký có ô tự chọn vai trò | 3 nhóm: Sinh viên / Cán bộ nhà trường / Quản trị hệ thống. **Nhóm chỉ đổi nhãn và hướng dẫn, không cấp quyền.** |
| Lựa chọn xác thực | Email + mật khẩu, nút Google / GitHub | GitHub, Google, email (Clerk) | Email + mật khẩu | Chỉ tài khoản do trường cấp. **Không thêm VNeID / Google** (theo yêu cầu) |
| Form | Nhãn trên ô; "Forgot your password?" cùng hàng nhãn mật khẩu; nút chính rộng hết thẻ | Nút xã hội trước, "or", rồi email | Có icon trong ô, ô "Remember me" | Nhãn trên ô, quên mật khẩu cùng hàng nhãn (chỉ cho sinh viên), một nút chính rộng hết |
| Thông báo bảo mật | Dòng nhỏ về điều khoản | "Secured by Clerk" | "Secure • Blockchain-Verified • Tamper-Proof" | Khối thông báo bảo mật ngắn, viết dễ hiểu |
| Liên kết phụ | "Don't have an account? Sign up" | "Sign up" | "Sign up here" | **Không có tự đăng ký.** Thay bằng khối nổi bật "Tra cứu văn bằng công khai – không cần đăng nhập" |
| Footer | Điều khoản | Điều khoản | Không | Footer CTUT dùng chung |
| Mobile 390px | Một cột, bỏ ảnh; chữ lớn, ô cao | Một cột | — | Một cột; **3 nhóm nên thu gọn thành 3 nút ngang** để form hiện ngay màn hình đầu |

## Rủi ro rút ra từ nguồn

1. **Tự chọn vai trò** (`Register.js` của Certiport có ô "I am a"): không được làm. CTUT đã xác định vai trò từ `UserProfile.role` sau khi đăng nhập. Thẻ "Quản trị hệ thống" chỉ dẫn sang trang đăng nhập Django Admin.
2. **Khối thương hiệu chiếm nửa màn hình** (kiểu chia đôi của Kiranism / ShadcnStore #2): đẹp với sản phẩm thương mại, nhưng với cổng của trường thì làm loãng thông tin. Phù hợp hơn là kiểu **thẻ giữa màn hình** của ShadcnStore #1, kết hợp phần đầu trang có logo và tên trường như Cổng Dịch vụ công.
3. **Nút đăng nhập mạng xã hội** – không áp dụng.

## Đề xuất bố cục (một phương án)

```
┌──────────────────────────────────────────────────────────┐
│                  [Logo CTUT]                              │
│     TRƯỜNG ĐẠI HỌC KỸ THUẬT – CÔNG NGHỆ CẦN THƠ           │
│     Hệ thống quản lý, cấp phát và xác thực văn bằng       │
│                                                            │
│                       Đăng nhập                            │
│             Chọn nhóm tài khoản để tiếp tục                │
│  ┌────────────┐ ┌──────────────────┐ ┌─────────────────┐  │
│  │ Sinh viên  │ │ Cán bộ nhà trường│ │ Quản trị hệ thống│  │
│  └────────────┘ └──────────────────┘ └─────────────────┘  │
│  ┌──────────────── form (hiện sau khi chọn) ───────────┐  │
│  │ Số CCCD / Tên đăng nhập        [               ]    │  │
│  │ Mật khẩu          Quên mật khẩu? [             ]    │  │
│  │ [            Đăng nhập            ]                 │  │
│  └─────────────────────────────────────────────────────┘  │
│  ⓘ Thông báo bảo mật (2–3 dòng)                            │
│  ┌──── TRA CỨU VĂN BẰNG CÔNG KHAI – KHÔNG CẦN ĐĂNG NHẬP → ┐ │
└──────────────────────────────────────────────────────────┘
 Footer CTUT
```

- Desktop: vùng nội dung rộng tối đa khoảng 960px. 3 thẻ nhóm nằm một hàng; form rộng khoảng 440px, căn giữa.
- Mobile: 3 thẻ thành 3 nút ngang gọn (icon + nhãn ngắn), form hiện ngay bên dưới.

**So với CTUT hiện tại:** bố cục hiện tại đã đúng hướng (xem `docs/images/ui_after_desktop_03_dang_nhap.png`). Việc còn lại là thu gọn 3 thẻ trên mobile (đã ghi trong kế hoạch Đợt 5).
