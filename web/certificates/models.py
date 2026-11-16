from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import hashlib
import secrets  # Update: sinh mã xác minh ngẫu nhiên an toàn mật mã (không dùng random thường)
import unicodedata  # Update: chuẩn hoá Unicode tiếng Việt trước khi băm

# Update: Bảng ký tự cho mã xác minh: 32 ký tự (24 chữ + 8 số)
VERIFY_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
VERIFY_CODE_LENGTH = 10  # Update: độ dài mã (không tính dấu gạch ngang hiển thị)


def generate_verify_code():
    """Update: Sinh mã xác minh ngẫu nhiên dạng 10 ký tự (lưu không có dấu gạch, ví dụ 'K7M29QXD4T')"""
    return ''.join(secrets.choice(VERIFY_CODE_ALPHABET) for _ in range(VERIFY_CODE_LENGTH))


def normalize_verify_code(raw):
    """Update: Chuẩn hoá mã người dùng nhập: bỏ khoảng trắng/dấu gạch, chuyển chữ hoa"""
    return ''.join(ch for ch in (raw or '').upper() if ch.isalnum())


class Certificate(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Chờ duyệt'),
        ('ISSUED', 'Đã cấp'),
        ('REVOKED', 'Đã thu hồi'),
        ('CANCELLED', 'Đã hủy'),        # Update: văn bằng cấp sai/không có giá trị từ đầu (trên chuỗi vẫn ghi là Revoked)
        ('REPLACED', 'Đã thay thế'),    # Update: văn bằng được thay bằng văn bằng khác (trên chuỗi vẫn ghi là Revoked)
    ]

    # Update: Các trạng thái "hết hiệu lực"
    END_STATUSES = ('REVOKED', 'CANCELLED', 'REPLACED')
    # Update: danh sách xếp loại tốt nghiệp dùng chung cho form tạo / sửa và nhập Excel
    CLASSIFICATIONS = ('Xuất sắc', 'Giỏi', 'Khá', 'Trung bình khá', 'Trung bình')
    # Update: Các trạng thái được phép hiện trên trang tra cứu công khai
    PUBLIC_STATUSES = ('ISSUED', 'REVOKED', 'CANCELLED', 'REPLACED')

    # Thông tin cơ bản in trên văn bằng
    serial_number = models.CharField(max_length=50, unique=True, verbose_name="Số hiệu văn bằng")
    student_id = models.CharField(max_length=30, blank=True, default='', verbose_name="Mã sinh viên")
    student_name = models.CharField(max_length=100, verbose_name="Họ và tên sinh viên")
    date_of_birth = models.DateField(verbose_name="Ngày sinh")
    major = models.CharField(max_length=100, verbose_name="Ngành đào tạo")
    graduation_year = models.IntegerField(verbose_name="Năm tốt nghiệp")
    classification = models.CharField(max_length=50, verbose_name="Xếp loại")
    degree_type = models.CharField(max_length=100, default='Bằng Cử nhân', verbose_name="Loại văn bằng")
    issue_date = models.DateField(null=True, blank=True, verbose_name="Ngày cấp")

    # Tiến trình 3 phòng ban phê duyệt
    student_affairs_approved = models.BooleanField(default=False, verbose_name="Phòng QLSV đã xác nhận")
    student_affairs_approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian QLSV duyệt")
    academic_affairs_approved = models.BooleanField(default=False, verbose_name="Phòng Đào tạo đã xác nhận")
    academic_affairs_approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian Đào tạo duyệt")
    rector_approved = models.BooleanField(default=False, verbose_name="Hiệu trưởng đã phê duyệt")
    rector_approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian Hiệu trưởng duyệt")

    # Luồng từ chối (trả về cho người nhập sửa)
    is_rejected = models.BooleanField(default=False, verbose_name="Bị từ chối")
    rejection_reason = models.TextField(blank=True, null=True, verbose_name="Lý do từ chối")
    rejected_by = models.CharField(max_length=50, blank=True, null=True, verbose_name="Người từ chối")

    # Luồng thu hồi (cần cả 3 phòng ban xác nhận)
    student_affairs_revoke = models.BooleanField(default=False, verbose_name="QLSV xác nhận thu hồi")
    academic_affairs_revoke = models.BooleanField(default=False, verbose_name="Đào tạo xác nhận thu hồi")
    rector_revoke = models.BooleanField(default=False, verbose_name="Hiệu trưởng xác nhận thu hồi")
    revoke_reason = models.TextField(blank=True, null=True, verbose_name="Lý do thu hồi")
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian thu hồi")
    # Update: Loại kết thúc hiệu lực mà phòng ban đầu tiên đề xuất: REVOKED (thu hồi) / CANCELLED
    end_type = models.CharField(max_length=20, blank=True, null=True, verbose_name="Loại kết thúc hiệu lực")
    # Update: Văn bằng thay thế (chỉ dùng khi end_type = REPLACED)
    replaced_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='replaces', verbose_name="Được thay thế bởi")

    # Update: Mã xác minh ngẫu nhiên in cạnh QR trên văn bằng
    verify_code = models.CharField(max_length=16, unique=True, null=True, blank=True, editable=False,
                                   verbose_name="Mã xác minh")

    # Update: Liên kết văn bằng với tài khoản sinh viên qua số CCCD
    national_id_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True, editable=False,
                                        verbose_name="Dấu băm CCCD")
    national_id_last4 = models.CharField(max_length=4, blank=True, null=True, verbose_name="4 số cuối CCCD")
    # Update: Số CCCD đầy đủ ở dạng MÃ HOÁ AES-256-GCM (security_helper.encrypt_national_id)
    national_id_encrypted = models.TextField(blank=True, null=True, editable=False, verbose_name="CCCD (mã hoá)")
    # Update: Email nhận link kích hoạt tài khoản sinh viên
    student_email = models.EmailField(blank=True, null=True, verbose_name="Email sinh viên")

    # Update: Phiên bản công thức dấu băm: 1 = công thức cũ (không muối)
    hash_version = models.PositiveSmallIntegerField(default=2, editable=False, verbose_name="Phiên bản dấu băm")
    hash_salt = models.CharField(max_length=64, blank=True, null=True, editable=False, verbose_name="Muối dấu băm")
    # Update: Chữ ký điện tử của Hiệu trưởng trên (hợp đồng, mạng, số hiệu, dấu băm, ngày cấp)
    issuer_signature = models.CharField(max_length=140, blank=True, null=True, editable=False,
                                        verbose_name="Chữ ký điện tử của nhà trường")
    signed_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name="Thời điểm ký")

    # Update: Tên cơ sở đào tạo TẠI THỜI ĐIỂM CẤP (ghi lúc Hiệu trưởng ký phát hành)
    issuer_name = models.CharField(max_length=255, blank=True, default='', verbose_name="Tên cơ sở đào tạo khi cấp")

    # Update: ẢNH VĂN BẰNG (scan / số hoá bản thật do nhà trường cung cấp)
    diploma_original = models.CharField(max_length=255, blank=True, default='', editable=False,
                                        verbose_name="Ảnh văn bằng gốc (đường dẫn nội bộ)")
    diploma_public = models.CharField(max_length=255, blank=True, default='', editable=False,
                                      verbose_name="Ảnh văn bằng công khai đã che (đường dẫn nội bộ)")
    diploma_regions = models.JSONField(default=list, blank=True, verbose_name="Vùng che trên ảnh công khai")
    diploma_public_approved = models.BooleanField(default=False, verbose_name="Đã duyệt ảnh công khai")
    diploma_uploaded_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm tải ảnh lên")
    diploma_uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='uploaded_diplomas', verbose_name="Người tải ảnh lên")

    # Thông tin lưu vết với Blockchain
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Trạng thái")
    data_hash = models.CharField(max_length=66, blank=True, null=True, verbose_name="Dấu băm (Data Hash)")
    tx_hash = models.CharField(max_length=100, blank=True, null=True, verbose_name="Mã giao dịch (Tx Hash)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Văn bằng"
        verbose_name_plural = "Danh sách văn bằng"
        ordering = ['-created_at']
        # Update: Quyền riêng cho ảnh văn bằng gốc
        permissions = [
            ('view_original_diploma', 'Xem / tải ảnh văn bằng gốc'),
            ('manage_diploma_image', 'Tải lên ảnh văn bằng, chỉnh vùng che và duyệt ảnh công khai'),
        ]

    def __str__(self):
        return f"{self.serial_number} - {self.student_name} ({self.student_id})"

    def calculate_data_hash(self):
        """Tính toán dấu băm SHA-256 từ chuỗi chuẩn hóa theo kế hoạch"""
        # Update: Hồ sơ mới (hash_version = 2) dùng công thức có muối
        if (self.hash_version or 1) >= 2:
            return self._calculate_data_hash_v2()
        raw_str = f"{self.serial_number}|{self.student_id}|{self.student_name}|{self.date_of_birth}|{self.major}|{self.graduation_year}|{self.classification}"
        h = hashlib.sha256(raw_str.strip().encode('utf-8')).hexdigest()
        return "0x" + h

    def canonical_fields_v2(self):
        """Update: Các trường đưa vào dấu băm phiên bản 2, theo đúng thứ tự"""
        def norm(value):
            return ' '.join(unicodedata.normalize('NFC', str(value or '')).split())
        dob = self.date_of_birth
        dob_iso = dob.isoformat() if hasattr(dob, 'isoformat') else norm(dob)
        return [norm(self.serial_number), norm(self.student_id), norm(self.student_name), dob_iso,
                norm(self.major), norm(self.graduation_year), norm(self.classification), norm(self.degree_type)]

    def _calculate_data_hash_v2(self):
        """Update: SHA-256("v2|<muối>|<các trường chuẩn hoá nối bằng |>")"""
        if not self.hash_salt:
            self.hash_salt = secrets.token_hex(16)
        raw = "v2|" + self.hash_salt + "|" + "|".join(self.canonical_fields_v2())
        return "0x" + hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        if not self.data_hash:
            self.data_hash = self.calculate_data_hash()
        # Update: Tự cấp mã xác minh cho hồ sơ chưa có (hồ sơ mới, hoặc hồ sơ cũ được lưu lại)
        if not self.verify_code:
            code = generate_verify_code()
            while Certificate.objects.filter(verify_code=code).exists():  # Update: chống trùng
                code = generate_verify_code()
            self.verify_code = code
        super().save(*args, **kwargs)

    @property
    def verify_code_display(self):
        """Update: Mã xác minh dạng dễ đọc để in/hiển thị: 'K7M29QXD4T' → 'K7M2-9QXD-4T'"""
        c = self.verify_code or ''
        return '-'.join(c[i:i + 4] for i in range(0, len(c), 4))

    @property
    def masked_name(self):
        """Update: Họ tên đã che cho trang công khai: giữ họ và tên gọi, che tên đệm"""
        parts = (self.student_name or '').split()
        if not parts:
            return ''
        if len(parts) == 1:
            return parts[0][0] + '***'
        if len(parts) == 2:
            return f"{parts[0]} {parts[1][0]}***"
        middle = ' '.join(p[0] + '***' for p in parts[1:-1])
        return f"{parts[0]} {middle} {parts[-1]}"

    @property
    def national_id_masked(self):
        """Update: CCCD đã che cho cán bộ xem: '•••• •••• 5678'"""
        return f"•••• •••• {self.national_id_last4}" if self.national_id_last4 else ''

    @property
    def is_ended(self):
        """Update: True nếu văn bằng đã hết hiệu lực (thu hồi / hủy / thay thế)"""
        return self.status in self.END_STATUSES

    @property
    def revoke_confirmations(self):
        """Update: số phòng đã xác nhận thu hồi khi văn bằng còn hiệu lực (0–3)"""
        return sum(bool(x) for x in (self.student_affairs_revoke, self.academic_affairs_revoke, self.rector_revoke))

    @property
    def current_step_info(self):
        # Update: Hai trạng thái mới: Đã hủy / Đã thay thế (đặt trước nhánh REVOKED để hiển thị đúng tên)
        if self.status == 'CANCELLED':
            return {
                'step': -2,
                'name': 'Đã hủy',
                'badge': 'dark',
                'desc': 'Văn bằng đã bị hủy (cấp sai / không có giá trị), trên Blockchain ghi nhận trạng thái thu hồi'
            }
        if self.status == 'REPLACED':
            return {
                'step': -2,
                'name': 'Đã thay thế',
                'badge': 'secondary',
                'desc': 'Văn bằng đã được thay thế bằng văn bằng khác, trên Blockchain ghi nhận trạng thái thu hồi'
            }
        if self.status == 'REVOKED':
            return {
                'step': -2,
                'name': 'Đã thu hồi',
                'badge': 'danger',
                'desc': 'Văn bằng đã bị thu hồi hiệu lực trên Blockchain'
            }
        if self.is_rejected:
            if self.rejected_by == 'hieutruong':
                return {
                    'step': 2,
                    'name': 'Hiệu trưởng trả về Đào tạo',
                    'badge': 'warning',
                    'desc': f'Hiệu trưởng từ chối và hoàn trả Phòng Đào tạo xem xét lại. Lý do: {self.rejection_reason or "Cần thẩm định lại"}'
                }
            elif self.rejected_by == 'daotao':
                return {
                    'step': 1,
                    'name': 'Đào tạo trả về QLSV',
                    'badge': 'danger',
                    'desc': f'Phòng Đào tạo từ chối và hoàn trả Phòng QLSV chỉnh sửa. Lý do: {self.rejection_reason or "Sai sót thông tin"}'
                }
            else:
                return {
                    'step': 1,
                    'name': 'QLSV từ chối',
                    'badge': 'secondary',
                    'desc': f'Hồ sơ bị từ chối bởi {self.rejected_by or "cán bộ"}. Lý do: {self.rejection_reason or "Cần chỉnh sửa"}'
                }
        if self.status == 'ISSUED':
            return {
                'step': 4,
                'name': 'Đã cấp',  # Update: bỏ thuật ngữ kỹ thuật
                'badge': 'success',
                'desc': 'Đã hoàn thành phê duyệt 3 cấp và phát hành trên Blockchain'
            }
        if not self.student_affairs_approved:
            return {
                'step': 1,
                'name': 'Chờ QLSV duyệt',
                'badge': 'warning',
                'desc': 'Chờ Phòng Quản lý sinh viên xác nhận danh tính & Mã sinh viên'
            }
        if not self.academic_affairs_approved:
            return {
                'step': 2,
                'name': 'Chờ Đào tạo duyệt',
                'badge': 'info',
                'desc': 'Chờ Phòng Đào tạo xác nhận điểm, chương trình và điều kiện tốt nghiệp'
            }
        if not self.rector_approved:
            return {
                'step': 3,
                'name': 'Chờ Hiệu trưởng ký',
                'badge': 'primary',
                'desc': 'Chờ Ban Giám hiệu / Hiệu trưởng ký duyệt và phát hành'  # Update: bỏ thuật ngữ kỹ thuật
            }
        return {
            'step': 4,
            'name': 'Đã cấp',
            'badge': 'success',
            'desc': 'Đã phát hành'
        }


class ApprovalLog(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name='logs', verbose_name="Văn bằng")
    action = models.CharField(max_length=50, verbose_name="Hành động")
    actor = models.CharField(max_length=100, verbose_name="Người thực hiện")
    comment = models.TextField(blank=True, null=True, verbose_name="Ghi chú / Lý do")
    tx_hash = models.CharField(max_length=100, blank=True, null=True, verbose_name="Mã giao dịch")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")

    class Meta:
        verbose_name = "Nhật ký phê duyệt"
        verbose_name_plural = "Nhật ký phê duyệt"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.certificate.serial_number} - {self.action} ({self.actor})"

    @property
    def action_label(self):
        """Update: tên hành động viết hoa đầu câu để hiển thị (dữ liệu gốc giữ nguyên chữ in hoa)"""
        s = (self.action or '').lower().replace(' & ', ' và ')
        s = s[:1].upper() + s[1:]
        for low, keep in (('qlsv', 'QLSV'), ('cccd', 'CCCD'), ('đào tạo', 'Đào tạo'), ('hiệu trưởng', 'Hiệu trưởng'), ('excel', 'Excel'), ('Qlsv', 'QLSV')):
            s = s.replace(low, keep)
        return s[:-3] + ' SV' if s.endswith(' sv') else s


class UserProfile(models.Model):
    """Hồ sơ phân quyền vai trò — gán qua trang Admin Django"""

    ROLE_CHOICES = [
        ('qlsv',       'Phòng Quản lý Sinh viên'),
        ('daotao',     'Phòng Đào tạo'),
        ('hieutruong', 'Hiệu trưởng / Ban Giám hiệu'),
        ('admin',      'Quản trị viên hệ thống'),
        ('student',    'Sinh viên'),  # Update: tài khoản sinh viên chủ sở hữu văn bằng (đăng nhập bằng CCCD)
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Tài khoản"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        blank=True,
        null=True,
        verbose_name="Vai trò",
        help_text="Vai trò quyết định luồng phê duyệt văn bằng mà tài khoản này được tham gia."
    )
    # Update: Với tài khoản sinh viên: dấu băm CCCD (giống Certificate.national_id_hash) để
    national_id_hash = models.CharField(max_length=64, unique=True, blank=True, null=True, editable=False,
                                        verbose_name="Dấu băm CCCD (sinh viên)")

    class Meta:
        verbose_name = "Hồ sơ phân quyền"
        verbose_name_plural = "Hồ sơ phân quyền"

    def __str__(self):
        role_display = self.get_role_display() or "Chưa phân quyền"
        return f"{self.user.username} — {role_display}"


class ShareToken(models.Model):
    """Update: Liên kết chia sẻ văn bằng có thời hạn do SINH VIÊN tạo cho một đơn vị/người xác minh"""
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name='shares', verbose_name="Văn bằng")
    token_hash = models.CharField(max_length=64, unique=True, editable=False, verbose_name="Dấu băm mã chia sẻ")
    recipient = models.CharField(max_length=120, blank=True, default='', verbose_name="Người / đơn vị nhận")
    show_full_name = models.BooleanField(default=True, verbose_name="Cho xem họ tên đầy đủ")
    show_dob = models.BooleanField(default=False, verbose_name="Cho xem ngày sinh")
    show_student_id = models.BooleanField(default=False, verbose_name="Cho xem mã sinh viên")
    show_classification = models.BooleanField(default=False, verbose_name="Cho xem xếp loại tốt nghiệp")
    expires_at = models.DateTimeField(verbose_name="Hết hạn lúc")
    max_views = models.PositiveIntegerField(null=True, blank=True, verbose_name="Số lượt xem tối đa")
    view_count = models.PositiveIntegerField(default=0, verbose_name="Số lượt đã xem")
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="Thu hồi lúc")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Người tạo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tạo lúc")

    class Meta:
        verbose_name = "Liên kết chia sẻ"
        verbose_name_plural = "Liên kết chia sẻ"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.certificate.serial_number} → {self.recipient or 'không ghi người nhận'}"

    @property
    def state(self):
        """Trạng thái hiện tại: 'revoked' / 'expired' / 'used_up' / 'active'."""
        if self.revoked_at:
            return 'revoked'
        if timezone.now() >= self.expires_at:
            return 'expired'
        if self.max_views is not None and self.view_count >= self.max_views:
            return 'used_up'
        return 'active'

    @property
    def is_active(self):
        return self.state == 'active'

    @property
    def state_display(self):
        return {'revoked': 'Đã thu hồi', 'expired': 'Đã hết hạn', 'used_up': 'Đã hết lượt xem',
                'active': 'Đang hiệu lực'}[self.state]


class VerificationLog(models.Model):
    """Update: Nhật ký các lượt xác minh văn bằng (để sinh viên biết ai đã xem văn bằng của mình)"""
    CHANNEL_CHOICES = [
        ('public_code', 'Quét QR / nhập mã xác minh'),
        ('public_serial', 'Tra theo số hiệu'),
        ('share', 'Mở liên kết chia sẻ'),
    ]
    OUTCOME_CHOICES = [
        ('shown', 'Đã xem thông tin'),
        ('denied', 'Bị từ chối (liên kết hết hiệu lực)'),
    ]
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name='verification_logs',
                                    verbose_name="Văn bằng")
    share = models.ForeignKey(ShareToken, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='logs', verbose_name="Liên kết chia sẻ")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, verbose_name="Hình thức")
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES, default='shown', verbose_name="Kết quả")
    ip_hash = models.CharField(max_length=16, blank=True, default='', verbose_name="Dấu băm IP")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")

    class Meta:
        verbose_name = "Nhật ký xác minh"
        verbose_name_plural = "Nhật ký xác minh"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.certificate.serial_number} - {self.get_channel_display()} ({self.created_at:%d/%m/%Y %H:%M})"


class DiplomaAccessLog(models.Model):
    """Update: Nhật ký truy cập ẢNH văn bằng: xem / tải ảnh gốc, tải lên, duyệt bản công khai, bị từ chối"""
    ACTION_CHOICES = [
        ('view_original', 'Cán bộ xem ảnh gốc'),
        ('download_original', 'Cán bộ tải ảnh gốc'),
        ('view_owner', 'Sinh viên xem ảnh của mình'),
        ('download_owner', 'Sinh viên tải ảnh của mình'),
        ('upload', 'Tải lên ảnh scan'),
        ('regions', 'Chỉnh vùng che'),
        ('approve_public', 'Duyệt ảnh công khai'),
        ('denied', 'Bị từ chối truy cập ảnh gốc'),
    ]
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name='diploma_logs',
                                    verbose_name="Văn bằng")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tài khoản")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Hành động")
    ip_hash = models.CharField(max_length=16, blank=True, default='', verbose_name="Dấu băm IP")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")

    class Meta:
        verbose_name = "Nhật ký truy cập ảnh văn bằng"
        verbose_name_plural = "Nhật ký truy cập ảnh văn bằng"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.certificate.serial_number} - {self.get_action_display()} ({self.created_at:%d/%m/%Y %H:%M})"


# ── Signals: tự động tạo/lưu UserProfile khi tạo User mới ────────────────────

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()




