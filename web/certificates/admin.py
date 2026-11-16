from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Certificate, ApprovalLog, UserProfile
from .models import ShareToken, VerificationLog  # Update: 2 bảng mới của P3
from .models import DiplomaAccessLog  # Update: nhật ký truy cập ảnh văn bằng
from django.conf import settings  # Update

# Update: Nhận diện CTUT trên trang quản trị Django (tiêu đề, thanh bên)
admin.site.site_header = f"{settings.INSTITUTION['short']} · Quản trị hệ thống văn bằng"
admin.site.site_title = f"{settings.INSTITUTION['short']} · Quản trị"
admin.site.index_title = settings.INSTITUTION['name']


# ── Inline: hiển thị phân quyền ngay trong trang chỉnh sửa User ──────────────

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "Phân quyền vai trò"
    verbose_name_plural = "Phân quyền vai trò"
    fields = ('role',)
    extra = 0


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_active')
    list_select_related = ('profile',)

    @admin.display(description='Vai trò hệ thống')
    def get_role(self, obj):
        try:
            return obj.profile.get_role_display() or '— Chưa phân quyền —'
        except UserProfile.DoesNotExist:
            return '— Chưa phân quyền —'


# Thay thế UserAdmin mặc định bằng UserAdmin đã tuỳ chỉnh
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ── Hồ sơ phân quyền (xem độc lập nếu cần) ───────────────────────────────────

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_editable = ('role',)
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


# ── Văn bằng & Nhật ký ────────────────────────────────────────────────────────

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'student_id', 'student_name', 'major', 'graduation_year', 'classification', 'status')
    search_fields = ('serial_number', 'student_id', 'student_name')
    list_filter = ('status', 'is_rejected', 'major', 'graduation_year')


@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ('certificate', 'action', 'actor', 'created_at', 'tx_hash')
    search_fields = ('certificate__serial_number', 'actor', 'action')
    list_filter = ('action', 'created_at')


# ── Update: liên kết chia sẻ & nhật ký xác minh (chỉ xem) ──

@admin.register(ShareToken)
class ShareTokenAdmin(admin.ModelAdmin):
    list_display = ('certificate', 'recipient', 'expires_at', 'view_count', 'max_views', 'state_display', 'created_at')
    search_fields = ('certificate__serial_number', 'recipient')
    readonly_fields = ('token_hash', 'view_count', 'created_by', 'created_at')

    @admin.display(description='Trạng thái')
    def state_display(self, obj):
        return obj.state_display


@admin.register(VerificationLog)
class VerificationLogAdmin(admin.ModelAdmin):
    list_display = ('certificate', 'channel', 'outcome', 'share', 'created_at')
    list_filter = ('channel', 'outcome', 'created_at')
    search_fields = ('certificate__serial_number',)

    def has_add_permission(self, request):  # nhật ký không được thêm/sửa tay
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(DiplomaAccessLog)
class DiplomaAccessLogAdmin(admin.ModelAdmin):
    """Update: Nhật ký xem / tải ảnh văn bằng gốc"""
    list_display = ('certificate', 'action', 'user', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('certificate__serial_number', 'user__username')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
