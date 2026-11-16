# 06 – Nghiên cứu cổng sinh viên

Nguồn: Certiport Student Dashboard [ẢNH REPO + CODE `StudentDashboard.js`], OpenCerts trang kết quả [LIVE], ShadcnStore Account Settings [LIVE].

## Quan sát

| Hạng mục | Certiport | OpenCerts | ShadcnStore | Bằng chứng |
| :--- | :--- | :--- | :--- | :--- |
| Thông tin tài khoản | Băng tím đầu trang: avatar, tên, email, nhãn "Verified Student", nút "View Profile" | — | Trang riêng chia khối (Personal Information, Change Password) | `dashboard/certiport__student-dashboard__pdf.png`, `forms/shadcnstore__settings-account__1440.png` |
| Danh sách văn bằng | **Lưới thẻ**: icon, loại, trường, ngành, ngày cấp, nhãn ISSUED, Blockchain ID + nút sao chép, 2 nút View / Download | — | — | `dashboard/certiport__student-cert-cards__pdf.png` |
| Trình xem văn bằng | Mở file PDF trên IPFS | Văn bằng dựng ngay trong trang, tab Certificate / Transcript / Media | — | `verification/opencerts__demo-valid__1440.png` |
| Tải xuống / chia sẻ | Download | Print, **Email**, Download | — | như trên |
| Lịch sử xác minh | Không có | Không có | — | — |
| Thông báo | Không có | — | — | — |

**Nhận xét:**
- Certiport cho thấy cách trình bày "văn bằng là một thẻ có mã và nút sao chép" rất dễ hiểu với người dùng phổ thông.
- Tuy vậy Certiport đưa **Blockchain ID** lên làm thông tin chính. Với sinh viên CTUT, thứ cần đưa ra là **mã xác minh và mã QR** in trên văn bằng; mã kỹ thuật nên ẩn đi.
- Không nguồn nào có **lịch sử xác minh** hay **liên kết chia sẻ có thời hạn**. Đây là hai điểm CTUT đã làm vượt các nguồn tham khảo, nên cần giữ và làm rõ hơn.

## Đề xuất cho CTUT (một phương án)

Nguyên tắc: người dùng phổ thông, ít thuật ngữ, mỗi văn bằng là một thẻ, thao tác chính luôn nhìn thấy.

```
Tổng quan:  [Văn bằng đã cấp: 1]  [Hồ sơ đang xét duyệt: 0]  [Thông tin tài khoản →]

┌ Bằng Cử nhân · Công nghệ thông tin ───────────────── [Đã cấp] ┐
│ Số hiệu VB-2026-001 · cấp ngày 13/11/2026                       │
│ Tab:  Văn bằng | Chia sẻ | Lịch sử xác minh                     │
│ ── Văn bằng ──────────────────────────────────────────────────  │
│ [Ảnh văn bằng đầy đủ của chính mình]   Mã xác minh: B8TC-NDTJ-AS [Sao chép] │
│                                        [QR]  [Tải ảnh] [In]      │
│ ── Chia sẻ ──  Tạo liên kết (người nhận, hạn dùng, số lượt xem) │
│               "Người nhận sẽ thấy: họ tên đầy đủ, ngày sinh, …"  │
│               Danh sách liên kết đang hiệu lực + nút Thu hồi     │
│ ── Lịch sử xác minh ── bảng: thời điểm, cách tra cứu, kết quả   │
└──────────────────────────────────────────────────────────────────┘
```

- **Quyền xem ảnh:** sinh viên xem **ảnh đầy đủ của chính mình**. Backend đã kiểm tra quyền sở hữu ở `owner_diploma_image`; giao diện chỉ hiển thị kết quả, không tự quyết quyền.
- **CCCD:** giữ cách hiện tại (mặc định che, có nút mắt để hiện).
- **Mobile:** thẻ văn bằng chiếm hết chiều ngang; tab chuyển thành 3 nút ngang; ảnh văn bằng đặt sau mã xác minh.
