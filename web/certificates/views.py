from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q

from .models import Certificate, ApprovalLog, UserProfile
from .blockchain import (
    register_onchain,
    approve_onchain,
    revoke_onchain
)
from .excel_helper import generate_sample_excel, process_excel_upload
from .qr_helper import generate_qr_base64

def get_role(user):
    """
    Lấy vai trò của user từ UserProfile.
    Nếu chưa gán profile, fallback về username để tương thích ngược
    với các tài khoản cũ (qlsv, daotao, hieutruong, admin).
    """
    try:
        role = user.profile.role
        if role:
            return role
    except UserProfile.DoesNotExist:
        pass
    return user.username

def search_view(request):
    """Trang tra cứu công khai văn bằng - ai cũng có thể truy cập"""
    query = request.GET.get('q', '').strip()
    result = None
    qr_data = None

    if query:
        # Tra cứu theo: Số hiệu văn bằng, Mã sinh viên, hoặc Họ và tên
        result = Certificate.objects.filter(
            Q(serial_number__iexact=query) |
            Q(student_id__iexact=query) |
            Q(student_name__icontains=query)
        ).first()

        if result:
            # Sinh mã QR chứa link tra cứu trực tiếp
            verify_url = request.build_absolute_uri(f"/?q={result.serial_number}")
            qr_data = generate_qr_base64(verify_url)

    return render(request, 'certificates/search.html', {
        'result': result,
        'query': query,
        'qr_data': qr_data,
    })


@login_required(login_url='login')
def dashboard(request):
    """Bảng điều khiển nội bộ và Hàng đợi duyệt hồ sơ theo đúng phân quyền tuần tự"""
    role = get_role(request.user)  # qlsv, daotao, hieutruong, admin
    filter_type = request.GET.get('filter', 'all')
    search_kw = request.GET.get('s', '').strip()

    # 1. Phân vùng dữ liệu cơ sở theo đúng phạm vi hiển thị của từng vai trò:
    # - daotao: CHỈ thấy hồ sơ sau khi QLSV đã duyệt
    # - hieutruong: CHỈ thấy hồ sơ sau khi cả QLSV và Đào tạo đã duyệt
    # - qlsv / admin: thấy toàn bộ hệ thống
    if role == 'daotao':
        base_qs = Certificate.objects.filter(student_affairs_approved=True)
    elif role == 'hieutruong':
        base_qs = Certificate.objects.filter(student_affairs_approved=True, academic_affairs_approved=True)
    else:  # qlsv, admin
        base_qs = Certificate.objects.all()

    # Áp dụng tìm kiếm từ khoá trong phạm vi được phép
    qs = base_qs
    if search_kw:
        qs = qs.filter(
            Q(serial_number__icontains=search_kw) |
            Q(student_id__icontains=search_kw) |
            Q(student_name__icontains=search_kw) |
            Q(major__icontains=search_kw)
        )

    # 2. Thống kê KPI (luôn tính trên toàn hệ thống, không phụ thuộc role):
    total_count = base_qs.count()
    issued_count = base_qs.filter(status='ISSUED').count()
    revoked_count = base_qs.filter(status='REVOKED').count()

    pending_qlsv_count = Certificate.objects.filter(
        status='PENDING', is_rejected=False, student_affairs_approved=False
    ).count()
    pending_daotao_count = Certificate.objects.filter(
        status='PENDING', is_rejected=False,
        student_affairs_approved=True, academic_affairs_approved=False
    ).count()
    pending_hieutruong_count = Certificate.objects.filter(
        status='PENDING', is_rejected=False,
        student_affairs_approved=True, academic_affairs_approved=True, rector_approved=False
    ).count()

    # Hồ sơ bị trả về theo từng luồng:
    # returned_to_qlsv: bị trả về cho QLSV (do Đào tạo từ chối, student_affairs_approved=False)
    returned_to_qlsv_count = Certificate.objects.filter(
        status='PENDING', is_rejected=True, student_affairs_approved=False
    ).count()
    # returned_to_daotao: Hiệu trưởng trả về cho Đào tạo
    returned_to_daotao_count = Certificate.objects.filter(
        status='PENDING', is_rejected=True,
        student_affairs_approved=True, academic_affairs_approved=False,
        rejected_by='hieutruong'
    ).count()
    # Tổng tất cả hồ sơ bị từ chối / trả về (dùng cho admin)
    rejected_total_count = Certificate.objects.filter(is_rejected=True).count()

    # 3. Áp dụng bộ lọc tab:
    if filter_type == 'pending_qlsv':
        qs = qs.filter(status='PENDING', is_rejected=False, student_affairs_approved=False)

    elif filter_type == 'pending_daotao':
        qs = qs.filter(status='PENDING', is_rejected=False, student_affairs_approved=True, academic_affairs_approved=False)

    elif filter_type == 'pending_hieutruong':
        qs = qs.filter(status='PENDING', is_rejected=False, student_affairs_approved=True, academic_affairs_approved=True, rector_approved=False)

    elif filter_type == 'returned':
        # Mỗi vai trò chỉ thấy hồ sơ bị trả về thuộc trách nhiệm của mình:
        if role == 'qlsv':
            # Hồ sơ bị trả lại cho QLSV (do Đào tạo từ chối)
            qs = qs.filter(is_rejected=True, student_affairs_approved=False)
        elif role == 'daotao':
            # Hồ sơ Hiệu trưởng trả về Đào tạo
            qs = qs.filter(is_rejected=True, student_affairs_approved=True, academic_affairs_approved=False, rejected_by='hieutruong')
        elif role == 'hieutruong':
            # Hồ sơ Hiệu trưởng đã trả về (để theo dõi)
            qs = qs.filter(is_rejected=True, rejected_by='hieutruong', academic_affairs_approved=False)
        else:
            # Admin thấy tất cả bị trả về
            qs = qs.filter(is_rejected=True)

    elif filter_type == 'rejected':
        # Alias của 'returned' dành cho admin (card KPI hiển thị tổng bị từ chối)
        qs = qs.filter(is_rejected=True)

    elif filter_type == 'forwarded':
        if role == 'qlsv':
            qs = qs.filter(status='PENDING', student_affairs_approved=True)
        elif role == 'daotao':
            qs = qs.filter(status='PENDING', student_affairs_approved=True, academic_affairs_approved=True)
        else:
            qs = qs.filter(status='PENDING')

    elif filter_type == 'issued':
        qs = qs.filter(status='ISSUED')

    elif filter_type == 'revoked':
        qs = qs.filter(status='REVOKED')

    elif filter_type == 'my_queue':
        if role == 'qlsv':
            # Chờ QLSV duyệt + hồ sơ bị trả về cần QLSV xử lý
            qs = qs.filter(
                Q(status='PENDING', is_rejected=False, student_affairs_approved=False) |
                Q(status='PENDING', is_rejected=True, student_affairs_approved=False)
            )
        elif role == 'daotao':
            # Chờ Đào tạo duyệt (QLSV đã duyệt, Đào tạo chưa duyệt, chưa bị trả về)
            qs = qs.filter(status='PENDING', is_rejected=False, student_affairs_approved=True, academic_affairs_approved=False)
        elif role == 'hieutruong':
            # Chờ Hiệu trưởng ký (cả 2 phòng đã duyệt, chưa bị từ chối)
            qs = qs.filter(status='PENDING', is_rejected=False, student_affairs_approved=True, academic_affairs_approved=True, rector_approved=False)

    return render(request, 'certificates/dashboard.html', {
        'certificates': qs,
        'role': role,
        'filter_type': filter_type,
        'search_kw': search_kw,
        'total_count': total_count,
        'pending_qlsv_count': pending_qlsv_count,
        'pending_daotao_count': pending_daotao_count,
        'pending_hieutruong_count': pending_hieutruong_count,
        'returned_to_qlsv_count': returned_to_qlsv_count,
        'returned_to_daotao_count': returned_to_daotao_count,
        'rejected_total_count': rejected_total_count,
        'issued_count': issued_count,
        'revoked_count': revoked_count,
    })

