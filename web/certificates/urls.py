from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Tra cứu công khai
    path('', views.search_view, name='search'),
    # Update: Trang đích của mã QR in trên văn bằng
    path('verify/<str:code>/', views.verify_view, name='verify'),
    # Update: Trang xác minh Cấp độ 2 mở từ liên kết chia sẻ có thời hạn của sinh viên
    path('verify/s/<str:token>/', views.share_view, name='share_verify'),

    # Update: Khu vực sinh viên: trang cá nhân, kích hoạt / quên mật khẩu
    path('me/', views.student_portal, name='student_portal'),
    path('me/share/<int:pk>/create/', views.student_share_create, name='student_share_create'),
    path('me/share/<int:share_id>/revoke/', views.student_share_revoke, name='student_share_revoke'),
    path('student/activate/<str:uidb64>/<str:token>/', views.student_activate, name='student_activate'),
    path('student/forgot/', views.student_forgot, name='student_forgot'),
    # Update: Ảnh văn bằng — mỗi đường dẫn kiểm tra quyền riêng ở backend (xem views.py mục P6)
    path('verify/<str:code>/diploma.png', views.public_diploma_image, name='public_diploma_image'),
    path('verify/s/<str:token>/diploma.png', views.share_diploma_image, name='share_diploma_image'),
    path('me/diploma/<int:pk>.png', views.owner_diploma_image, name='owner_diploma_image'),
    path('certificates/<int:pk>/diploma/<str:variant>.png', views.staff_diploma_image, name='staff_diploma_image'),
    path('certificates/<int:pk>/detail/', views.certificate_detail, name='certificate_detail'),
    path('certificates/<int:pk>/diploma/manage/', views.diploma_manage, name='diploma_manage'),

    # Update: Cán bộ cập nhật CCCD/email sinh viên và gửi (lại) link kích hoạt
    path('certificates/<int:pk>/student-account/', views.certificate_student_account, name='certificate_student_account'),

    # Bảng điều khiển nội bộ
    path('dashboard/', views.dashboard, name='dashboard'),

    # Thao tác văn bằng
    path('certificates/create/', views.certificate_create, name='certificate_create'),
    path('certificates/<int:pk>/edit/', views.certificate_edit, name='certificate_edit'),
    path('certificates/<int:pk>/approve/', views.certificate_approve, name='certificate_approve'),
    path('certificates/<int:pk>/reject/', views.certificate_reject, name='certificate_reject'),
    path('certificates/<int:pk>/revoke/', views.certificate_revoke, name='certificate_revoke'),
    path('certificates/<int:pk>/print/', views.certificate_print_view, name='certificate_print'),

    # Xử lý Excel
    path('excel/import/', views.import_excel, name='import_excel'),
    path('excel/template/', views.download_excel_template, name='download_excel_template'),


    # Xác thực người dùng
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]
