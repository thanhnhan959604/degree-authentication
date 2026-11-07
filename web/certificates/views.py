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
            # Chờ Đào tạo duyệt (QLSV đã duyệt, Đà0o tạo chưa duyệt, chưa bị trả về)
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


@login_required(login_url='login')
def certificate_create(request):
    """Tạo mới hồ sơ văn bằng thủ công (QLSV hoặc Admin)"""
    if request.method != 'POST':
        return redirect('dashboard')

    if get_role(request.user) not in ['qlsv', 'admin']:
        messages.error(request, "Bạn không có quyền thêm mới hồ sơ văn bằng.")
        return redirect('dashboard')

    serial_number = request.POST.get('serial_number', '').strip()
    student_id = request.POST.get('student_id', '').strip()
    student_name = request.POST.get('student_name', '').strip()
    date_of_birth = request.POST.get('date_of_birth', '').strip()
    major = request.POST.get('major', '').strip()
    graduation_year = request.POST.get('graduation_year', '').strip()
    classification = request.POST.get('classification', '').strip()
    degree_type = request.POST.get('degree_type', 'Bằng Cử nhân').strip()
    issue_date = request.POST.get('issue_date', '').strip() or None

    if not all([serial_number, student_id, student_name, date_of_birth, major, graduation_year, classification]):
        messages.error(request, "Vui lòng điền đầy đủ các trường thông tin bắt buộc (*).")
        return redirect('dashboard')

    if Certificate.objects.filter(serial_number=serial_number).exists():
        messages.error(request, f"Số hiệu văn bằng '{serial_number}' đã tồn tại trong hệ thống.")
        return redirect('dashboard')

    try:
        cert = Certificate(
            serial_number=serial_number,
            student_id=student_id,
            student_name=student_name,
            date_of_birth=date_of_birth,
            major=major,
            graduation_year=int(graduation_year),
            classification=classification,
            degree_type=degree_type,
            issue_date=issue_date,
            status='PENDING'
        )
        cert.data_hash = cert.calculate_data_hash()
        cert.save()

        # Thử đăng ký on-chain bằng ví QLSV nếu Besu online
        tx_hash = register_onchain(cert.serial_number, cert.data_hash)
        if tx_hash:
            cert.tx_hash = tx_hash
            cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="TẠO MỚI HỒ SƠ",
            actor=request.user.username,
            comment="Nhập hồ sơ văn bằng thủ công lên hệ thống",
            tx_hash=tx_hash
        )

        messages.success(request, f"Đã thêm hồ sơ văn bằng '{serial_number}' thành công! Hồ sơ đang ở hàng đợi chờ QLSV duyệt.")
    except Exception as e:
        messages.error(request, f"Lỗi tạo hồ sơ: {str(e)}")

    return redirect('dashboard')


@login_required(login_url='login')
def certificate_edit(request, pk):
    """Chỉnh sửa hồ sơ bị từ chối và gửi duyệt lại"""
    cert = get_object_or_404(Certificate, pk=pk)

    if get_role(request.user) not in ['qlsv', 'daotao', 'admin']:
        messages.error(request, "Bạn không có quyền chỉnh sửa hồ sơ này.")
        return redirect('dashboard')

    if request.method == 'POST':
        cert.student_id = request.POST.get('student_id', cert.student_id).strip()
        cert.student_name = request.POST.get('student_name', cert.student_name).strip()
        cert.date_of_birth = request.POST.get('date_of_birth', cert.date_of_birth)
        cert.major = request.POST.get('major', cert.major).strip()
        cert.graduation_year = int(request.POST.get('graduation_year', cert.graduation_year))
        cert.classification = request.POST.get('classification', cert.classification).strip()
        cert.degree_type = request.POST.get('degree_type', cert.degree_type).strip()

        # Reset lại cờ từ chối
        cert.is_rejected = False
        cert.rejection_reason = None
        cert.rejected_by = None
        cert.data_hash = cert.calculate_data_hash()

        if get_role(request.user) == 'daotao':
            # Nếu Đào tạo sửa sau khi Hiệu trưởng trả về: giữ xác nhận QLSV
            cert.academic_affairs_approved = False
            cert.rector_approved = False
        else:
            # QLSV sửa: đưa về chờ QLSV duyệt
            cert.student_affairs_approved = False
            cert.academic_affairs_approved = False
            cert.rector_approved = False

        cert.status = 'PENDING'
        cert.save()

        # Đăng ký lại on-chain
        tx_hash = register_onchain(cert.serial_number, cert.data_hash)
        if tx_hash:
            cert.tx_hash = tx_hash
            cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="CHỈNH SỬA & GỬI LẠI",
            actor=request.user.username,
            comment=f"Cán bộ {request.user.username} đã cập nhật thông tin và đưa lại vào hàng đợi duyệt",
            tx_hash=tx_hash
        )

        messages.success(request, f"Đã cập nhật hồ sơ '{cert.serial_number}' thành công.")
        return redirect('dashboard')

    return redirect('dashboard')


@login_required(login_url='login')
def certificate_approve(request, pk):
    """Xử lý phê duyệt hồ sơ theo đúng 3 bước vai trò tuần tự"""
    if request.method != 'POST':
        return redirect('dashboard')

    cert = get_object_or_404(Certificate, pk=pk)
    role = get_role(request.user)

    now = timezone.now()
    tx_hash = None

    if role == 'qlsv' or (role == 'admin' and not cert.student_affairs_approved):
        # Bước 1: Phòng QLSV xác nhận danh tính & Mã sinh viên
        cert.student_affairs_approved = True
        cert.student_affairs_approved_at = now
        cert.is_rejected = False
        cert.rejection_reason = None
        cert.rejected_by = None
        cert.save()

        tx_hash = approve_onchain(cert.serial_number, cert.data_hash, 'qlsv')

        ApprovalLog.objects.create(
            certificate=cert,
            action="QLSV XÁC NHẬN DANH TÍNH",
            actor=role,
            comment="Đã xác thực thông tin cá nhân và Mã sinh viên trùng khớp hồ sơ. Chuyển hồ sơ sang Phòng Đào tạo.",
            tx_hash=tx_hash
        )
        messages.success(request, f"✓ Phòng QLSV đã duyệt văn bằng '{cert.serial_number}'. Hồ sơ đã hiển thị trên giao diện Phòng Đào tạo.")

    elif role == 'daotao' or (role == 'admin' and cert.student_affairs_approved and not cert.academic_affairs_approved):
        # Bước 2: Phòng Đào tạo xác nhận điều kiện học vụ
        if not cert.student_affairs_approved:
            messages.error(request, "Cần Phòng QLSV xác nhận danh tính trước.")
            return redirect('dashboard')

        cert.academic_affairs_approved = True
        cert.academic_affairs_approved_at = now
        cert.is_rejected = False
        cert.rejection_reason = None
        cert.rejected_by = None
        cert.save()

        tx_hash = approve_onchain(cert.serial_number, cert.data_hash, 'daotao')

        ApprovalLog.objects.create(
            certificate=cert,
            action="ĐÀO TẠO XÁC NHẬN HỌC VỤ",
            actor=role,
            comment="Đã thẩm định điểm rèn luyện, chương trình đào tạo và điều kiện tốt nghiệp. Chuyển hồ sơ lên Ban Giám hiệu.",
            tx_hash=tx_hash
        )
        messages.success(request, f"✓ Phòng Đào tạo đã duyệt văn bằng '{cert.serial_number}'. Hồ sơ đã hiển thị trên giao diện Hiệu trưởng.")

    elif role == 'hieutruong' or (role == 'admin' and cert.student_affairs_approved and cert.academic_affairs_approved and not cert.rector_approved):
        # Bước 3: Ban Giám hiệu / Hiệu trưởng ký duyệt và phát hành lên Blockchain
        if not (cert.student_affairs_approved and cert.academic_affairs_approved):
            messages.error(request, "Hồ sơ chưa đủ 2 bước duyệt của Phòng QLSV và Phòng Đào tạo.")
            return redirect('dashboard')

        cert.rector_approved = True
        cert.rector_approved_at = now
        cert.is_rejected = False
        cert.rejection_reason = None
        cert.rejected_by = None
        cert.status = 'ISSUED'
        if not cert.issue_date:
            cert.issue_date = now.date()

        tx_hash = approve_onchain(cert.serial_number, cert.data_hash, 'hieutruong')
        if tx_hash:
            cert.tx_hash = tx_hash
        cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="HIỆU TRƯỞNG KÝ DUYỆT PHÁT HÀNH",
            actor=role,
            comment="Hiệu trưởng ký số phát hành chính thức văn bằng lên Blockchain Besu",
            tx_hash=tx_hash or cert.tx_hash
        )
        messages.success(request, f"Hiệu trưởng đã ký duyệt thành công! Văn bằng '{cert.serial_number}' đã được phát hành On-Chain.")

    else:
        messages.error(request, "Tài khoản của bạn không có thẩm quyền duyệt ở bước này.")

    return redirect('dashboard')

    
@login_required(login_url='login')
def certificate_reject(request, pk):
    """Từ chối hồ sơ kèm lý do, trả về đúng phòng ban liền trước đó"""
    if request.method != 'POST':
        return redirect('dashboard')

    cert = get_object_or_404(Certificate, pk=pk)
    reason = request.POST.get('reason', 'Thông tin chưa chính xác, yêu cầu kiểm tra lại').strip()
    role = get_role(request.user)

    cert.is_rejected = True
    cert.rejection_reason = reason
    cert.rejected_by = role

    # XỬ LÝ THEO TRÌNH TỰ TRẢ VỀ PHÒNG TRƯỚC ĐÓ:
    if role == 'hieutruong' or (role == 'admin' and cert.academic_affairs_approved and not cert.rector_approved):
        # Hiệu trưởng từ chối -> Trả về Phòng Đào tạo (Bước 2)
        cert.rector_approved = False
        cert.academic_affairs_approved = False
        # Giữ nguyên cert.student_affairs_approved = True
        cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="HIỆU TRƯỞNG TRẢ VỀ ĐÀO TẠO",
            actor=role,
            comment=f"Hiệu trưởng từ chối và hoàn trả Phòng Đào tạo xem xét lại. Lý do: {reason}"
        )
        messages.warning(request, f"Đã hoàn trả hồ sơ '{cert.serial_number}' về Phòng Đào tạo. Lý do: {reason}")

    elif role == 'daotao' or (role == 'admin' and cert.student_affairs_approved and not cert.academic_affairs_approved):
        # Phòng Đào tạo từ chối -> Trả về Phòng Quản lý sinh viên (Bước 1)
        cert.academic_affairs_approved = False
        cert.student_affairs_approved = False
        cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="ĐÀO TẠO TRẢ VỀ QLSV",
            actor=role,
            comment=f"Phòng Đào tạo từ chối và hoàn trả Phòng QLSV chỉnh sửa lại. Lý do: {reason}"
        )
        messages.warning(request, f"Đã hoàn trả hồ sơ '{cert.serial_number}' về Phòng QLSV. Lý do: {reason}")

    elif role == 'qlsv' or role == 'admin':
        # Phòng QLSV từ chối hồ sơ đầu vào
        cert.student_affairs_approved = False
        cert.academic_affairs_approved = False
        cert.rector_approved = False
        cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="QLSV TỪ CHỐI HỒ SƠ",
            actor=role,
            comment=f"Phòng QLSV từ chối hồ sơ đầu vào. Lý do: {reason}"
        )
        messages.warning(request, f"Phòng QLSV đã từ chối hồ sơ '{cert.serial_number}'. Lý do: {reason}")
    else:
        messages.error(request, "Bạn không có quyền thực hiện thao tác này.")

    return redirect('dashboard')
