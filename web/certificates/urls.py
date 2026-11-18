from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Tra cứu công khai & Chia sẻ
    path('', views.search_view, name='search'),
    path('blockchain/', views.blockchain_explorer, name='blockchain_explorer'),
    path('api/blockchain/tx/<str:tx_hash>/', views.blockchain_tx_detail_api, name='blockchain_tx_detail_api'),
    path('share/<str:code>/', views.share_redirect_view, name='share_redirect'),
    path('api/shares/create/', views.create_share_link, name='create_share_link'),
    path('api/shares/<int:pk>/revoke/', views.revoke_share_link, name='revoke_share_link'),
    path('api/qr/', views.qr_image_view, name='qr_image_view'),
    path('certificates/<str:pk>/diploma.png', views.public_diploma_image, name='public_diploma_image'),
    path('me/diploma/<str:pk>.png', views.owner_diploma_image, name='owner_diploma_image'),

    # Các cổng phân hệ GovTech (Prototypes tích hợp)
    path('portal/sinh-vien/', views.student_portal, name='student_portal'),
    path('portal/qlsv/', views.qlsv_portal, name='qlsv_portal'),
    path('portal/daotao/', views.daotao_portal, name='daotao_portal'),
    path('portal/hieu-truong/', views.hieutruong_portal, name='hieutruong_portal'),

    # Bảng điều khiển nội bộ
    path('dashboard/', views.dashboard, name='dashboard'),

    # Thao tác văn bằng
    path('certificates/create/', views.certificate_create, name='certificate_create'),
    path('certificates/batch-approve/', views.batch_approve, name='batch_approve'),
    path('certificates/<str:pk>/edit/', views.certificate_edit, name='certificate_edit'),
    path('certificates/<str:pk>/approve/', views.certificate_approve, name='certificate_approve'),
    path('certificates/<str:pk>/reject/', views.certificate_reject, name='certificate_reject'),
    path('certificates/<str:pk>/revoke/', views.certificate_revoke, name='certificate_revoke'),
    path('certificates/<str:pk>/print/', views.certificate_print_view, name='certificate_print'),

    # Xử lý Excel
    path('excel/import/', views.import_excel, name='import_excel'),
    path('excel/template/', views.download_excel_template, name='download_excel_template'),


    # Xác thực người dùng
    path('login/', views.login_view, name='login'),
    path('api/auth/login/', views.login_view, name='api_login'),
    path('logout/', views.logout_view, name='logout'),
]

