from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Certificate, ApprovalLog, UserProfile


# ── Inline: hiển thị phân quyền ngay trong trang chỉnh sửa User 

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


# ── Hồ sơ phân quyền 

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_editable = ('role',)
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


# ── Văn bằng và Nhật ký 

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
