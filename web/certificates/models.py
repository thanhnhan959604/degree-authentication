from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import hashlib

class Certificate(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Chờ duyệt'),
        ('ISSUED', 'Đã cấp'),
        ('REVOKED', 'Đã thu hồi'),
    ]

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

    def __str__(self):
        return f"{self.serial_number} - {self.student_name} ({self.student_id})"

    def calculate_data_hash(self):
        """Tính toán dấu băm SHA-256 từ chuỗi chuẩn hóa theo kế hoạch"""
        raw_str = f"{self.serial_number}|{self.student_id}|{self.student_name}|{self.date_of_birth}|{self.major}|{self.graduation_year}|{self.classification}"
        h = hashlib.sha256(raw_str.strip().encode('utf-8')).hexdigest()
        return "0x" + h

    def save(self, *args, **kwargs):
        if not self.data_hash:
            self.data_hash = self.calculate_data_hash()
        super().save(*args, **kwargs)

    @property
    def current_step_info(self):
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
                'name': 'Đã cấp (On-Chain)',
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
                'desc': 'Chờ Ban Giám hiệu / Hiệu trưởng ký duyệt và phát hành On-Chain'
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


class UserProfile(models.Model):
    """Hồ sơ phân quyền vai trò — gán qua trang Admin Django"""

    ROLE_CHOICES = [
        ('qlsv',       'Phòng Quản lý Sinh viên'),
        ('daotao',     'Phòng Đào tạo'),
        ('hieutruong', 'Hiệu trưởng / Ban Giám hiệu'),
        ('admin',      'Quản trị viên hệ thống'),
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

    class Meta:
        verbose_name = "Hồ sơ phân quyền"
        verbose_name_plural = "Hồ sơ phân quyền"

    def __str__(self):
        role_display = self.get_role_display() or "Chưa phân quyền"
        return f"{self.user.username} — {role_display}"


# ── Signals: tự động tạo/lưu UserProfile khi tạo User mới ────────────────────

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()