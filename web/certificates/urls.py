from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Tra cứu công khai
    path('', views.search_view, name='search'),

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
