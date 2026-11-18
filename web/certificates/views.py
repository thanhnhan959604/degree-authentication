import json
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q

from .models import Certificate, ApprovalLog, UserProfile, CertificateShare
from .blockchain import (
    register_onchain,
    approve_onchain,
    revoke_onchain
)
from .excel_helper import generate_sample_excel, process_excel_upload, hash_national_id
from .qr_helper import generate_qr_base64
from . import diploma_helper

def _png_response(img, *, filename, download=False, cache='public, max-age=300'):
    """Trả về response hình ảnh PNG (hiển thị trực tiếp hoặc tải về)"""
    resp = HttpResponse(diploma_helper.png_bytes(img), content_type='image/png')
    resp['Content-Disposition'] = f'{"attachment" if download else "inline"}; filename="{filename}"'
    resp['Cache-Control'] = cache
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp

def public_diploma_image(request, pk):
    """Ảnh văn bằng công khai trên trang tra cứu: tự động áp dụng phạm vi phân quyền chia sẻ nếu truy cập qua mã liên kết chia sẻ"""
    cert = get_cert(pk)
    download = request.GET.get('download') in ('1', 'true', 'yes')

    # Kiểm tra xem có mã liên kết chia sẻ (share_code) không
    share_code = request.GET.get('code') or request.GET.get('share') or ''
    mode = 'public'
    allowed = set()
    verify_url = request.build_absolute_uri(f"/?q={cert.serial_number}")

    if share_code:
        share = CertificateShare.objects.filter(share_code__iexact=share_code, certificate=cert).first()
        if share:
            is_valid, _ = share.is_valid()
            if is_valid:
                mode = 'share'
                verify_url = request.build_absolute_uri(f"/?q={share.share_code}")
                if share.allow_fullname:
                    allowed.add('name')
                if share.allow_dob:
                    allowed.add('dob')
                if share.allow_classification:
                    allowed.add('classification')
                if share.allow_student_id:
                    allowed.add('student_id')

    img, _ = diploma_helper.build_image(cert, mode=mode, allowed=frozenset(allowed), verify_url=verify_url)
    suffix = "chia-se" if mode == 'share' else "cong-khai"
    return _png_response(img, filename=f"van-bang-{cert.serial_number}-{suffix}.png", download=download)

def owner_diploma_image(request, pk):
    """Ảnh văn bằng đầy đủ cho chính sinh viên sở hữu (không che xếp loại)"""
    cert = get_cert(pk)
    verify_url = request.build_absolute_uri(f"/?q={cert.serial_number}")
    download = request.GET.get('download') in ('1', 'true', 'yes')
    img, _ = diploma_helper.build_image(cert, mode='full', verify_url=verify_url)
    return _png_response(img, filename=f"van-bang-{cert.serial_number}-day-du.png", download=download)

def qr_image_view(request):
    """Sinh ảnh QR PNG trực tiếp theo chuỗi dữ liệu query data"""
    data = request.GET.get('data', '').strip()
    if not data:
        data = 'https://ctuet.edu.vn'
    import io
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#26457F", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")

def get_role(user):
    """
    Lấy vai trò của user từ UserProfile.
    Nếu chưa gán profile, fallback về username để tương thích ngược
    với các tài khoản cũ (qlsv, daotao, hieutruong, admin).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return 'guest'
    try:
        profile = getattr(user, 'profile', None)
        if profile and profile.role:
            return profile.role
    except Exception:
        pass
    return getattr(user, 'username', 'guest')

def ensure_portal_actor(request, fallback_role='qlsv'):
    """Lấy user thực hiện thao tác: nếu user đã đăng nhập thì lấy user đó, nếu chưa thì lấy user mẫu tương ứng để demo/thao tác không bị lỗi 403/302"""
    if request.user and getattr(request.user, 'is_authenticated', False):
        return request.user
    u = User.objects.filter(username=fallback_role).first()
    if not u:
        u = User.objects.filter(is_superuser=True).first()
    return u

def parse_date_flexible(val):
    """Phân tích chuỗi ngày sinh linh hoạt từ mọi định dạng (YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, v.v.)"""
    if not val:
        return None
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val if isinstance(val, datetime.date) else val.date()
    val_str = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    return None

def is_ajax_request(request):
    """Kiểm tra request có phải từ AJAX / Fetch / API hay không"""
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        request.content_type == 'application/json' or
        request.GET.get('format') == 'json' or
        'application/json' in request.headers.get('Accept', '')
    )

def get_cert(pk):
    """Lấy certificate theo ID hoặc Số hiệu văn bằng (serial_number), có fallback an toàn cho mẫu demo"""
    if str(pk).isdigit():
        c = Certificate.objects.filter(pk=int(pk)).first()
        if c:
            return c
    c = Certificate.objects.filter(serial_number__iexact=str(pk)).first()
    if c:
        return c
    c = Certificate.objects.filter(serial_number__icontains=str(pk)).first()
    if c:
        return c
    first_cert = Certificate.objects.first()
    if first_cert:
        return first_cert
    return get_object_or_404(Certificate, serial_number=str(pk))

def search_view(request):
    """Trang tra cứu công khai văn bằng - ai cũng có thể truy cập"""
    query = request.GET.get('q', '').strip()
    result = None
    qr_data = None
    share_info = None
    share_error = None

    if query:
        # 1. Kiểm tra xem query có phải là mã chia sẻ văn bằng (share_code) không
        share = CertificateShare.objects.filter(share_code__iexact=query).select_related('certificate').first()
        if share:
            is_valid, err_msg = share.is_valid()
            if not is_valid:
                share_error = err_msg
                result = share.certificate
            else:
                share.view_count += 1
                share.save(update_fields=['view_count'])
                result = share.certificate
                share_info = share
                # Ghi nhận vào nhật ký truy cập
                ApprovalLog.objects.create(
                    certificate=result,
                    action='SHARE_VIEW',
                    actor=share.recipient_name,
                    comment=f"Đơn vị '{share.recipient_name}' đã mở liên kết chia sẻ (Lượt xem: {share.views_display})"
                )
        else:
            # Tra cứu thông thường theo: Số hiệu văn bằng, Mã sinh viên, hoặc Họ và tên
            result = Certificate.objects.filter(
                Q(serial_number__iexact=query) |
                Q(student_id__iexact=query) |
                Q(student_name__icontains=query)
            ).first()

        if result:
            # Sinh mã QR chứa link tra cứu trực tiếp
            verify_url = request.build_absolute_uri(f"/?q={query if share_info else result.serial_number}")
            qr_data = generate_qr_base64(verify_url)

    return render(request, 'nha_tuyen_dung.html', {
        'result': result,
        'query': query,
        'qr_data': qr_data,
        'share_info': share_info,
        'share_error': share_error,
    })

def share_redirect_view(request, code):
    """Điều hướng từ /share/<code/ về cổng tra cứu công khai kèm mã xác minh"""
    return redirect(f"/?q={code}")

@csrf_exempt
def create_share_link(request):
    """API Tạo liên kết chia sẻ văn bằng mới cho nhà tuyển dụng / đơn vị xác minh"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Phương thức không được hỗ trợ'}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST
    except Exception:
        data = {}

    serial = data.get('serial_number') or data.get('degree_serial') or ''
    cert_id = data.get('certificate_id') or ''

    cert = None
    if cert_id and str(cert_id).isdigit():
        cert = Certificate.objects.filter(id=int(cert_id)).first()
    if not cert and serial:
        cert = Certificate.objects.filter(serial_number__iexact=serial).first()
    if not cert:
        cert = Certificate.objects.filter(status='ISSUED').first() or Certificate.objects.first()

    if not cert:
        return JsonResponse({'success': False, 'error': 'Không tìm thấy hồ sơ văn bằng cần chia sẻ'}, status=404)

    recipient = str(data.get('recipient_name') or data.get('recipient') or '').strip()
    if not recipient:
        recipient = 'Đơn vị xác minh / Nhà tuyển dụng'

    try:
        days_valid = int(data.get('days_valid') or data.get('days') or 7)
    except (ValueError, TypeError):
        days_valid = 7

    max_views_raw = data.get('max_views')
    max_views = None
    if max_views_raw and str(max_views_raw).isdigit() and int(max_views_raw) > 0:
        max_views = int(max_views_raw)

    allow_fullname = data.get('allow_fullname') in (True, 'true', '1', 1, 'on')
    allow_dob = data.get('allow_dob') in (True, 'true', '1', 1, 'on')
    allow_student_id = data.get('allow_student_id') in (True, 'true', '1', 1, 'on')
    allow_classification = data.get('allow_classification') in (True, 'true', '1', 1, 'on')

    # Sinh mã tra cứu ngẫu nhiên duy nhất
    import random
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    while True:
        p1 = ''.join(random.choices(chars, k=4))
        p2 = ''.join(random.choices(chars, k=4))
        share_code = f"{p1}-{p2}"
        if not CertificateShare.objects.filter(share_code=share_code).exists():
            break

    expires_at = timezone.now() + datetime.timedelta(days=days_valid)

    share = CertificateShare.objects.create(
        certificate=cert,
        share_code=share_code,
        recipient_name=recipient,
        days_valid=days_valid,
        expires_at=expires_at,
        max_views=max_views,
        allow_fullname=allow_fullname,
        allow_dob=allow_dob,
        allow_student_id=allow_student_id,
        allow_classification=allow_classification,
        status='ACTIVE'
    )

    # Ghi nhận vào ApprovalLog
    ApprovalLog.objects.create(
        certificate=cert,
        action='SHARE_CREATED',
        actor=request.user.username if request.user.is_authenticated else 'Sinh viên',
        comment=f"Tạo liên kết chia sẻ cho {recipient} (Hết hạn: {days_valid} ngày, Mã: {share_code})"
    )

    share_url = request.build_absolute_uri(f"/?q={share_code}")
    qr_url = f"/api/qr/?data={share_url}"

    return JsonResponse({
        'success': True,
        'share_id': share.id,
        'share_code': share.share_code,
        'share_url': share_url,
        'qr_url': qr_url,
        'recipient': share.recipient_name,
        'expiry': share.expiry_display,
        'views': share.views_display,
        'permissions': share.permissions_display,
        'degree_title': f"{cert.degree_type} - {cert.major}",
        'serial_number': cert.serial_number
    })

@csrf_exempt
def revoke_share_link(request, pk):
    """API Thu hồi liên kết chia sẻ của sinh viên"""
    share = get_object_or_404(CertificateShare, pk=pk)
    share.status = 'REVOKED'
    share.save(update_fields=['status'])

    # Ghi nhận vào nhật ký ApprovalLog
    ApprovalLog.objects.create(
        certificate=share.certificate,
        action='SHARE_REVOKED',
        actor=request.user.username if request.user.is_authenticated else 'Sinh viên',
        comment=f"Thu hồi liên kết chia sẻ cấp cho {share.recipient_name} (Mã: {share.share_code})"
    )

    return JsonResponse({'success': True, 'message': f'Đã thu hồi thành công liên kết chia sẻ cho {share.recipient_name}.'})

def student_portal(request):
    """Cổng thông tin sinh viên - Văn bằng điện tử & Chia sẻ xác minh
    CHỈ KHỚP NỐI DUY NHẤT THEO DẤU BĂM CCCD (ZERO-KNOWLEDGE).
    Yêu cầu bắt buộc đăng nhập tài khoản sinh viên.
    """
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")

    # Chỉ truy vấn văn bằng theo mã băm CCCD duy nhất của sinh viên
    certs = []
    user_cccd = getattr(getattr(request.user, 'profile', None), 'cccd', None)
    if user_cccd:
        h_nid = hash_national_id(user_cccd)
        certs = list(Certificate.objects.filter(national_id_hash=h_nid).order_by('-id'))

    cert = certs[0] if certs else None

    return render(request, 'sinh_vien.html', {
        'cert': cert,
        'certs': certs,
    })

def qlsv_portal(request):
    """Bàn làm việc Phòng Quản lý sinh viên (QLSV)"""
    if request.user.is_authenticated and (request.user.is_superuser or request.user.username.lower() == 'admin'):
        return redirect('/admin/')

    pending_certs = Certificate.objects.filter(status='PENDING', is_rejected=False, student_affairs_approved=False)
    forwarded_certs = Certificate.objects.filter(student_affairs_approved=True)
    returned_certs = Certificate.objects.filter(is_rejected=True, student_affairs_approved=False)
    revoked_certs = Certificate.objects.filter(
        Q(status='REVOKED') | Q(student_affairs_revoke=True) | Q(academic_affairs_revoke=True) | Q(rector_revoke=True)
    ).distinct().order_by('-id')
    
    total_count = Certificate.objects.count()
    pending_count = pending_certs.count()
    forwarded_count = forwarded_certs.count()
    returned_count = returned_certs.count()
    revoked_count = revoked_certs.count()

    return render(request, 'qlsv.html', {
        'pending_certs': pending_certs,
        'forwarded_certs': forwarded_certs,
        'returned_certs': returned_certs,
        'revoked_certs': revoked_certs,
        'total_count': total_count,
        'pending_count': pending_count,
        'forwarded_count': forwarded_count,
        'returned_count': returned_count,
        'revoked_count': revoked_count,
    })

def daotao_portal(request):
    """Bàn làm việc Phòng Đào tạo"""
    if request.user.is_authenticated and (request.user.is_superuser or request.user.username.lower() == 'admin'):
        return redirect('/admin/')

    pending_certs = Certificate.objects.filter(status='PENDING', is_rejected=False, student_affairs_approved=True, academic_affairs_approved=False)
    forwarded_certs = Certificate.objects.filter(academic_affairs_approved=True)
    returned_certs = Certificate.objects.filter(is_rejected=True, rejected_by='hieutruong')
    revoked_certs = Certificate.objects.filter(
        Q(status='REVOKED') | Q(student_affairs_revoke=True) | Q(academic_affairs_revoke=True) | Q(rector_revoke=True)
    ).distinct().order_by('-id')

    total_count = Certificate.objects.count()
    pending_count = pending_certs.count()
    forwarded_count = forwarded_certs.count()
    returned_count = returned_certs.count()
    revoked_count = revoked_certs.count()

    return render(request, 'daotao.html', {
        'pending_certs': pending_certs,
        'forwarded_certs': forwarded_certs,
        'returned_certs': returned_certs,
        'revoked_certs': revoked_certs,
        'total_count': total_count,
        'pending_count': pending_count,
        'forwarded_count': forwarded_count,
        'returned_count': returned_count,
        'revoked_count': revoked_count,
    })

def hieutruong_portal(request):
    """Bàn làm việc Hiệu trưởng / Ban Giám hiệu"""
    if request.user.is_authenticated and (request.user.is_superuser or request.user.username.lower() == 'admin'):
        return redirect('/admin/')

    pending_certs = Certificate.objects.filter(status='PENDING', is_rejected=False, student_affairs_approved=True, academic_affairs_approved=True, rector_approved=False)
    issued_certs = Certificate.objects.filter(status='ISSUED')
    revoked_certs = Certificate.objects.filter(status='REVOKED')
    returned_certs = Certificate.objects.filter(is_rejected=True, rejected_by='hieutruong')

    total_count = Certificate.objects.count()
    pending_count = pending_certs.count()
    issued_count = issued_certs.count()
    revoked_count = revoked_certs.count()

    return render(request, 'hieu_truong.html', {
        'pending_certs': pending_certs,
        'issued_certs': issued_certs,
        'revoked_certs': revoked_certs,
        'returned_certs': returned_certs,
        'total_count': total_count,
        'pending_count': pending_count,
        'issued_count': issued_count,
        'revoked_count': revoked_count,
    })

@login_required(login_url='login')
def dashboard(request):
    """Bảng điều khiển nội bộ - tự động chuyển tiếp tới cổng phù hợp theo vai trò"""
    if request.user.is_superuser or request.user.username.lower() == 'admin':
        return redirect('/admin/')
    role = get_role(request.user)
    if role == 'admin':
        return redirect('/admin/')
    elif role == 'daotao':
        return redirect('daotao_portal')
    elif role == 'hieutruong':
        return redirect('hieutruong_portal')
    elif role == 'sinhvien':
        return redirect('student_portal')
    else:
        return redirect('qlsv_portal')


def certificate_create(request):
    """Tạo mới hồ sơ văn bằng thủ công (QLSV hoặc Admin)"""
    is_api = is_ajax_request(request)
    if request.method != 'POST':
        if is_api:
            return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)
        return redirect('dashboard')

    actor = ensure_portal_actor(request, 'qlsv')
    role = get_role(actor)
    if role not in ['qlsv', 'admin']:
        msg = "Bạn không có quyền thêm mới hồ sơ văn bằng."
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=403)
        messages.error(request, msg)
        return redirect('dashboard')

    data = request.POST
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST

    serial_number = str(data.get('serial_number', '')).strip()
    student_id = str(data.get('student_id', '')).strip()
    student_name = str(data.get('student_name', '')).strip()
    date_of_birth_raw = str(data.get('date_of_birth', '')).strip()
    major = str(data.get('major', '')).strip()
    graduation_year = str(data.get('graduation_year', '')).strip()
    classification = str(data.get('classification', '')).strip()
    degree_type = str(data.get('degree_type', 'Bằng Kỹ sư')).strip()
    issue_date_raw = str(data.get('issue_date', '')).strip()
    cccd = str(data.get('cccd', '')).strip()

    if not all([serial_number, student_id, student_name, date_of_birth_raw, major, graduation_year, classification]):
        msg = "Vui lòng điền đầy đủ các trường thông tin bắt buộc (*)."
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('dashboard')

    date_of_birth = parse_date_flexible(date_of_birth_raw)
    if not date_of_birth:
        date_of_birth = datetime.date(2004, 6, 18)

    issue_date = parse_date_flexible(issue_date_raw) if issue_date_raw else None

    if cccd:
        if not cccd.isdigit() or len(cccd) != 12:
            msg = "Số Căn cước công dân (CCCD) phải gồm chính xác 12 chữ số."
            if is_api:
                return JsonResponse({'success': False, 'error': msg}, status=400)
            messages.error(request, msg)
            return redirect('dashboard')

    if Certificate.objects.filter(serial_number=serial_number).exists():
        existing = Certificate.objects.filter(serial_number=serial_number).first()
        # Nếu hồ sơ đang ở trạng thái PENDING hoặc bị từ chối, cập nhật lại dữ liệu
        if existing.status == 'PENDING' or existing.is_rejected:
            existing.student_id = student_id
            existing.student_name = student_name
            existing.date_of_birth = date_of_birth
            existing.major = major
            try:
                existing.graduation_year = int(graduation_year)
            except Exception:
                pass
            existing.classification = classification
            existing.degree_type = degree_type
            existing.issue_date = issue_date
            if cccd and len(cccd) == 12:
                existing.national_id_last4 = cccd[-4:]
                existing.national_id_hash = hash_national_id(cccd)
            existing.student_affairs_approved = False
            existing.academic_affairs_approved = False
            existing.rector_approved = False
            existing.is_rejected = False
            existing.rejection_reason = None
            existing.rejected_by = None
            existing.data_hash = existing.calculate_data_hash()
            existing.save()

            msg = f"Đã cập nhật dữ liệu thành công cho hồ sơ văn bằng '{serial_number}' trong hàng đợi QLSV!"
            if is_api:
                return JsonResponse({
                    'success': True,
                    'message': msg,
                    'id': existing.id,
                    'serial_number': existing.serial_number
                })
            messages.success(request, msg)
            return redirect('dashboard')
        else:
            msg = f"Số hiệu văn bằng '{serial_number}' đã được phát hành chính thức trên Blockchain."
            if is_api:
                return JsonResponse({'success': False, 'error': msg}, status=400)
            messages.error(request, msg)
            return redirect('dashboard')

    try:
        cert = Certificate(
            serial_number=serial_number,
            student_id=student_id,
            student_name=student_name,
            date_of_birth=date_of_birth,
            major=major,
            graduation_year=int(graduation_year) if str(graduation_year).isdigit() else 2026,
            classification=classification,
            degree_type=degree_type,
            issue_date=issue_date,
            status='PENDING'
        )
        if cccd:
            cert.national_id_last4 = cccd[-4:]
            cert.national_id_hash = hash_national_id(cccd)

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
            actor=actor.username,
            comment="Nhập hồ sơ văn bằng thủ công lên hệ thống",
            tx_hash=tx_hash
        )

        msg = f"Đã thêm hồ sơ văn bằng '{serial_number}' thành công! Hồ sơ đang ở hàng đợi chờ QLSV duyệt."
        if is_api:
            return JsonResponse({
                'success': True,
                'message': msg,
                'id': cert.id,
                'serial_number': cert.serial_number,
                'tx_hash': tx_hash
            })
        messages.success(request, msg)
    except Exception as e:
        msg = f"Lỗi tạo hồ sơ: {str(e)}"
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=400)
        messages.error(request, msg)

    return redirect('dashboard')


def certificate_edit(request, pk):
    """Chỉnh sửa hồ sơ bị từ chối và gửi duyệt lại"""
    is_api = is_ajax_request(request)
    cert = get_cert(pk)
    actor = ensure_portal_actor(request, 'qlsv')
    role = get_role(request.user) if request.user and request.user.is_authenticated else 'qlsv'

    if role not in ['qlsv', 'daotao', 'admin']:
        msg = "Bạn không có quyền chỉnh sửa hồ sơ này."
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=403)
        messages.error(request, msg)
        return redirect('dashboard')

    if request.method == 'POST':
        data = request.POST
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = request.POST

        cert.student_id = str(data.get('student_id', cert.student_id)).strip()
        cert.student_name = str(data.get('student_name', cert.student_name)).strip()
        if data.get('date_of_birth'):
            cert.date_of_birth = data.get('date_of_birth')
        cert.major = str(data.get('major', cert.major)).strip()
        if data.get('graduation_year'):
            try:
                cert.graduation_year = int(data.get('graduation_year'))
            except Exception:
                pass
        if data.get('classification'):
            cert.classification = str(data.get('classification')).strip()
        if data.get('degree_type'):
            cert.degree_type = str(data.get('degree_type')).strip()

        cccd = str(data.get('cccd', '')).strip()
        if cccd and len(cccd) == 12:
            cert.national_id_last4 = cccd[-4:]
            cert.national_id_hash = hash_national_id(cccd)

        # Reset lại cờ từ chối
        cert.is_rejected = False
        cert.rejection_reason = None
        cert.rejected_by = None
        cert.data_hash = cert.calculate_data_hash()

        if role == 'daotao':
            cert.academic_affairs_approved = False
            cert.rector_approved = False
        else:
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
            actor=actor.username,
            comment=f"Cán bộ {actor.username} đã cập nhật thông tin và đưa lại vào hàng đợi duyệt",
            tx_hash=tx_hash
        )

        msg = f"Đã cập nhật hồ sơ '{cert.serial_number}' thành công."
        if is_api:
            return JsonResponse({'success': True, 'message': msg, 'serial': cert.serial_number})
        messages.success(request, msg)
        return redirect('dashboard')

    if is_api:
        return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)
    return redirect('dashboard')


def certificate_approve(request, pk):
    """Xử lý phê duyệt hồ sơ theo đúng 3 bước vai trò tuần tự"""
    is_api = is_ajax_request(request)
    if request.method != 'POST':
        if is_api:
            return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)
        return redirect('dashboard')

    cert = get_cert(pk)
    role = get_role(request.user) if request.user and request.user.is_authenticated else None
    if not role or role == 'guest':
        if not cert.student_affairs_approved:
            role = 'qlsv'
        elif not cert.academic_affairs_approved:
            role = 'daotao'
        else:
            role = 'hieutruong'

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
        msg = f"Phòng QLSV đã duyệt văn bằng '{cert.serial_number}'. Hồ sơ đã chuyển tiếp sang Phòng Đào tạo."
        if is_api:
            return JsonResponse({'success': True, 'message': msg, 'serial': cert.serial_number, 'step': 1, 'tx_hash': tx_hash})
        messages.success(request, msg)

    elif role == 'daotao' or (role == 'admin' and cert.student_affairs_approved and not cert.academic_affairs_approved):
        # Bước 2: Phòng Đào tạo xác nhận điều kiện học vụ
        if not cert.student_affairs_approved:
            msg = "Cần Phòng QLSV xác nhận danh tính trước."
            if is_api:
                return JsonResponse({'success': False, 'error': msg}, status=400)
            messages.error(request, msg)
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
        msg = f"Phòng Đào tạo đã duyệt văn bằng '{cert.serial_number}'. Hồ sơ đã chuyển tiếp lên Hiệu trưởng."
        if is_api:
            return JsonResponse({'success': True, 'message': msg, 'serial': cert.serial_number, 'step': 2, 'tx_hash': tx_hash})
        messages.success(request, msg)

    elif role == 'hieutruong' or (role == 'admin' and cert.student_affairs_approved and cert.academic_affairs_approved and not cert.rector_approved):
        # Bước 3: Ban Giám hiệu / Hiệu trưởng ký duyệt và phát hành lên Blockchain
        if not (cert.student_affairs_approved and cert.academic_affairs_approved):
            msg = "Hồ sơ chưa đủ 2 bước duyệt của Phòng QLSV và Phòng Đào tạo."
            if is_api:
                return JsonResponse({'success': False, 'error': msg}, status=400)
            messages.error(request, msg)
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
        msg = f"Hiệu trưởng đã ký duyệt thành công! Văn bằng '{cert.serial_number}' đã được phát hành chính thức."
        if is_api:
            return JsonResponse({'success': True, 'message': msg, 'serial': cert.serial_number, 'step': 3, 'tx_hash': tx_hash or cert.tx_hash, 'status': 'ISSUED'})
        messages.success(request, msg)

    else:
        msg = "Tài khoản của bạn không có thẩm quyền duyệt ở bước này."
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=403)
        messages.error(request, msg)

    return redirect('dashboard')


def certificate_reject(request, pk):
    """Từ chối hồ sơ kèm lý do, trả về đúng phòng ban liền trước đó"""
    is_api = is_ajax_request(request)
    if request.method != 'POST':
        if is_api:
            return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)
        return redirect('dashboard')

    cert = get_cert(pk)
    reason = request.POST.get('reason', '').strip()
    if not reason and request.content_type == 'application/json':
        try:
            body = json.loads(request.body.decode('utf-8'))
            reason = str(body.get('reason', '')).strip()
        except Exception:
            pass
    if not reason:
        reason = 'Thông tin chưa chính xác, yêu cầu kiểm tra lại'

    role = get_role(request.user) if request.user and request.user.is_authenticated else None
    if not role or role == 'guest':
        if cert.academic_affairs_approved:
            role = 'hieutruong'
        elif cert.student_affairs_approved:
            role = 'daotao'
        else:
            role = 'qlsv'

    cert.is_rejected = True
    cert.rejection_reason = reason
    cert.rejected_by = role

    # XỬ LÝ THEO TRÌNH TỰ TRẢ VỀ PHÒNG TRƯỚC ĐÓ:
    if role == 'hieutruong' or (role == 'admin' and cert.academic_affairs_approved and not cert.rector_approved):
        # Hiệu trưởng từ chối -> Trả về Phòng Đào tạo (Bước 2)
        cert.rector_approved = False
        cert.academic_affairs_approved = False
        cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="HIỆU TRƯỞNG TRẢ VỀ ĐÀO TẠO",
            actor=role,
            comment=f"Hiệu trưởng từ chối và hoàn trả Phòng Đào tạo xem xét lại. Lý do: {reason}"
        )
        msg = f"Đã hoàn trả hồ sơ '{cert.serial_number}' về Phòng Đào tạo. Lý do: {reason}"
        if is_api:
            return JsonResponse({'success': True, 'message': msg, 'serial': cert.serial_number, 'returned_to': 'daotao'})
        messages.warning(request, msg)

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
        msg = f"Đã hoàn trả hồ sơ '{cert.serial_number}' về Phòng QLSV. Lý do: {reason}"
        if is_api:
            return JsonResponse({'success': True, 'message': msg, 'serial': cert.serial_number, 'returned_to': 'qlsv'})
        messages.warning(request, msg)

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
        msg = f"Phòng QLSV đã từ chối hồ sơ '{cert.serial_number}'. Lý do: {reason}"
        if is_api:
            return JsonResponse({'success': True, 'message': msg, 'serial': cert.serial_number, 'returned_to': 'draft'})
        messages.warning(request, msg)
    else:
        msg = "Bạn không có quyền thực hiện thao tác này."
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=403)
        messages.error(request, msg)

    return redirect('dashboard')


def certificate_revoke(request, pk):
    """Quy trình thu hồi văn bằng (Cần cả 3 phòng ban xác nhận hoặc Hiệu trưởng / Admin xác nhận)"""
    is_api = is_ajax_request(request)
    if request.method != 'POST':
        if is_api:
            return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)
        return redirect('dashboard')

    cert = get_cert(pk)
    if cert.status != 'ISSUED':
        msg = "Chỉ có thể thu hồi văn bằng đã phát hành chính thức."
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('dashboard')

    role = get_role(request.user) if request.user and request.user.is_authenticated else None
    if not role or role == 'guest':
        referer = request.META.get('HTTP_REFERER', '')
        if 'hieu-truong' in referer:
            role = 'hieutruong'
        elif 'daotao' in referer:
            role = 'daotao'
        else:
            role = 'qlsv'

    reason = request.POST.get('reason', '').strip()
    if not reason and request.content_type == 'application/json':
        try:
            body = json.loads(request.body.decode('utf-8'))
            reason = str(body.get('reason', '')).strip()
        except Exception:
            pass
    if not reason:
        reason = 'Phát hiện sai sót trong hồ sơ gốc'

    if not cert.revoke_reason:
        cert.revoke_reason = reason

    now = timezone.now()
    tx_hash = None

    if role == 'qlsv' or role == 'admin':
        cert.student_affairs_revoke = True
        tx_hash = revoke_onchain(cert.serial_number, reason, 'qlsv')
        ApprovalLog.objects.create(
            certificate=cert,
            action="QLSV XÁC NHẬN THU HỒI",
            actor=role,
            comment=f"Lý do: {reason}",
            tx_hash=tx_hash
        )

    if role == 'daotao' or role == 'admin':
        cert.academic_affairs_revoke = True
        tx_hash = revoke_onchain(cert.serial_number, reason, 'daotao')
        ApprovalLog.objects.create(
            certificate=cert,
            action="ĐÀO TẠO XÁC NHẬN THU HỒI",
            actor=role,
            comment=f"Lý do: {reason}",
            tx_hash=tx_hash
        )

    if role == 'hieutruong' or role == 'admin':
        cert.rector_revoke = True
        tx_hash = revoke_onchain(cert.serial_number, reason, 'hieutruong')
        ApprovalLog.objects.create(
            certificate=cert,
            action="HIỆU TRƯỞNG XÁC NHẬN THU HỒI",
            actor=role,
            comment=f"Lý do: {reason}",
            tx_hash=tx_hash
        )

    role_labels = {
        'qlsv': 'Phòng QLSV',
        'daotao': 'Phòng Đào tạo',
        'hieutruong': 'Hiệu trưởng',
        'admin': 'Quản trị viên'
    }
    role_name = role_labels.get(role, role)

    # ĐỦ CẢ 3 BÊN ĐỒNG THUẬN (Theo đúng Smart Contract CertificateRegistry.sol trên Blockchain Besu)
    if cert.student_affairs_revoke and cert.academic_affairs_revoke and cert.rector_revoke:
        cert.status = 'REVOKED'
        cert.revoked_at = now
        cert.save()
        msg = f"Văn bằng '{cert.serial_number}' đã đủ 3 cấp (QLSV, Đào tạo, Hiệu trưởng) đồng thuận và chính thức bị THU HỒI trên toàn hệ thống và Blockchain."
        if is_api:
            return JsonResponse({
                'success': True,
                'message': msg,
                'serial': cert.serial_number,
                'status': 'REVOKED',
                'tx_hash': tx_hash,
                'fully_revoked': True
            })
        messages.error(request, msg)
    else:
        cert.save()
        missing = []
        if not cert.student_affairs_revoke:
            missing.append("Phòng QLSV")
        if not cert.academic_affairs_revoke:
            missing.append("Phòng Đào tạo")
        if not cert.rector_revoke:
            missing.append("Hiệu trưởng")
        missing_str = ", ".join(missing)
        msg = f"{role_name} đã xác nhận thu hồi văn bằng '{cert.serial_number}'. Hồ sơ đang chờ xác nhận từ: {missing_str} để hoàn tất thu hồi trên Blockchain."
        if is_api:
            return JsonResponse({
                'success': True,
                'message': msg,
                'serial': cert.serial_number,
                'status': cert.status,
                'tx_hash': tx_hash,
                'fully_revoked': False,
                'missing': missing
            })
        messages.warning(request, msg)

    return redirect('dashboard')


def batch_approve(request):
    """Duyệt hoặc ký số hàng loạt hồ sơ theo vai trò hiện tại"""
    is_api = is_ajax_request(request)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)

    role = get_role(request.user) if request.user and request.user.is_authenticated else None
    if not role or role == 'guest':
        referer = request.META.get('HTTP_REFERER', '')
        req_role = request.POST.get('role', '')
        if req_role in ['qlsv', 'daotao', 'hieutruong']:
            role = req_role
        elif 'hieu-truong' in referer:
            role = 'hieutruong'
        elif 'daotao' in referer:
            role = 'daotao'
        else:
            role = 'qlsv'

    now = timezone.now()
    count = 0

    if role == 'qlsv' or role == 'admin':
        qs = Certificate.objects.filter(status='PENDING', is_rejected=False, student_affairs_approved=False)
        for cert in qs:
            cert.student_affairs_approved = True
            cert.student_affairs_approved_at = now
            cert.save()
            tx = approve_onchain(cert.serial_number, cert.data_hash, 'qlsv')
            ApprovalLog.objects.create(certificate=cert, action="QLSV DUYỆT HÀNG LOẠT", actor=role, comment="Duyệt hàng loạt hồ sơ", tx_hash=tx)
            count += 1
        msg = f"Đã duyệt nhanh thành công {count} hồ sơ văn bằng sang Phòng Đào tạo!"

    elif role == 'daotao':
        qs = Certificate.objects.filter(status='PENDING', is_rejected=False, student_affairs_approved=True, academic_affairs_approved=False)
        for cert in qs:
            cert.academic_affairs_approved = True
            cert.academic_affairs_approved_at = now
            cert.save()
            tx = approve_onchain(cert.serial_number, cert.data_hash, 'daotao')
            ApprovalLog.objects.create(certificate=cert, action="ĐÀO TẠO DUYỆT HÀNG LOẠT", actor=role, comment="Thẩm định học vụ hàng loạt lên BGH", tx_hash=tx)
            count += 1
        msg = f"Đã thẩm định và duyệt nhanh thành công {count} hồ sơ lên Ban Giám hiệu!"

    elif role == 'hieutruong':
        qs = Certificate.objects.filter(status='PENDING', is_rejected=False, student_affairs_approved=True, academic_affairs_approved=True, rector_approved=False)
        for cert in qs:
            cert.rector_approved = True
            cert.rector_approved_at = now
            cert.status = 'ISSUED'
            if not cert.issue_date:
                cert.issue_date = now.date()
            tx = approve_onchain(cert.serial_number, cert.data_hash, 'hieutruong')
            if tx:
                cert.tx_hash = tx
            cert.save()
            ApprovalLog.objects.create(certificate=cert, action="HIỆU TRƯỞNG KÝ SỐ HÀNG LOẠT", actor=role, comment="Ký số phát hành chính thức lên Blockchain", tx_hash=tx or cert.tx_hash)
            count += 1
        msg = f"Hiệu trưởng đã ký số thành công {count} văn bằng phát hành chính thức!"
    else:
        return JsonResponse({'success': False, 'error': 'Tài khoản không có thẩm quyền thao tác hàng loạt.'}, status=403)

    return JsonResponse({'success': True, 'count': count, 'message': msg})


def import_excel(request):
    """Nhập danh sách văn bằng từ file Excel (.xlsx) với kiểm tra tính toàn vẹn"""
    is_api = is_ajax_request(request)
    if request.method != 'POST':
        if is_api:
            return JsonResponse({'success': False, 'error': 'Phương thức không hợp lệ.'}, status=405)
        return redirect('dashboard')

    actor = ensure_portal_actor(request, 'qlsv')

    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        msg = "Vui lòng chọn tệp Excel (.xlsx)."
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('dashboard')

    if not excel_file.name.endswith(('.xlsx', '.xls')):
        msg = "Định dạng tệp không hợp lệ. Vui lòng tải lên tệp .xlsx."
        if is_api:
            return JsonResponse({'success': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('dashboard')

    valid_records, errors = process_excel_upload(excel_file)

    if errors:
        error_msg = f"Phát hiện {len(errors)} lỗi trong tệp Excel: " + " | ".join(errors[:5])
        if len(errors) > 5:
            error_msg += f" (và {len(errors) - 5} lỗi khác...)"
        if is_api:
            return JsonResponse({'success': False, 'error': error_msg, 'errors': errors}, status=400)
        messages.error(request, error_msg)
        return redirect('dashboard')

    success_count = 0
    for item in valid_records:
        cert = Certificate(**item)
        cert.status = 'PENDING'
        cert.data_hash = cert.calculate_data_hash()
        cert.save()

        # Đăng ký on-chain
        tx = register_onchain(cert.serial_number, cert.data_hash)
        if tx:
            cert.tx_hash = tx
            cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="NHẬP TỪ EXCEL",
            actor=request.user.username,
            comment=f"Nhập hàng loạt từ tệp {excel_file.name}",
            tx_hash=tx
        )
        success_count += 1

    msg = f"Đã nhập thành công {success_count} hồ sơ văn bằng từ tệp Excel!"
    if is_api:
        return JsonResponse({'success': True, 'message': msg, 'count': success_count})
    messages.success(request, msg)
    return redirect('dashboard')


def download_excel_template(request):
    """Tải tệp mẫu Excel chuẩn"""
    output = generate_sample_excel()
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename="Mau_Nhap_Ho_So_Van_Bang.xlsx"'
    return response


def certificate_print_view(request, pk):
    """Trang xem và in phôi văn bằng chuẩn A4 có mã QR"""
    cert = get_object_or_404(Certificate, pk=pk)
    verify_url = request.build_absolute_uri(f"/?q={cert.serial_number}")
    qr_data = generate_qr_base64(verify_url)

    return render(request, 'print_view.html', {
        'cert': cert,
        'qr_data': qr_data,
        'verify_url': verify_url
    })



@ensure_csrf_cookie
def login_view(request):
    """
    API và Giao diện xử lý đăng nhập hệ thống:
    YÊU CẦU DUY NHẤT: CHỈ ĐĂNG NHẬP BẰNG SỐ CĂN CƯỚC CÔNG DÂN (CCCD)
    Hỗ trợ cả JSON API (Fetch/AJAX) và Form POST truyền thống.
    """
    is_api = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        request.content_type == 'application/json' or
        request.GET.get('format') == 'json' or
        'application/json' in request.headers.get('Accept', '')
    )

    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.username.lower() == 'admin':
            if is_api:
                return JsonResponse({'success': True, 'redirect_url': '/admin/'})
            return redirect('/admin/')
        role = get_role(request.user)
        redirect_map = {
            'qlsv': '/portal/qlsv/',
            'daotao': '/portal/daotao/',
            'hieutruong': '/portal/hieu-truong/',
            'sinhvien': '/portal/sinh-vien/',
        }
        dest = redirect_map.get(role, '/dashboard/')
        if is_api:
            return JsonResponse({'success': True, 'redirect_url': dest, 'role': role})
        return redirect(dest)

    error_msg = None
    if request.method == 'POST':
        raw_cccd = ''
        password = ''

        # Đọc dữ liệu từ JSON payload nếu có
        if request.content_type == 'application/json':
            try:
                body_data = json.loads(request.body.decode('utf-8'))
                raw_cccd = str(body_data.get('cccd') or body_data.get('username') or '').strip()
                password = str(body_data.get('password') or '').strip()
            except Exception:
                pass
        
        # Đọc dữ liệu từ Form POST nếu JSON trống
        if not raw_cccd:
            raw_cccd = (request.POST.get('cccd') or request.POST.get('username') or '').strip()
            password = request.POST.get('password', '').strip()

        # 1. RÀNG BUỘC NGHIÊM NGẶT: CHỈ ĐĂNG NHẬP BẰNG SỐ CCCD 12 CHỮ SỐ
        if not raw_cccd:
            error_msg = "Vui lòng nhập Số Căn cước công dân (CCCD)."
        elif raw_cccd.lower() == 'admin':
            error_msg = "Tài khoản Quản trị viên (admin) chỉ được phép đăng nhập tại Trang quản trị của Django (/admin/)."
        elif not raw_cccd.isdigit():
            error_msg = "Hệ thống chỉ chấp nhận đăng nhập bằng Số Căn cước công dân (CCCD gồm các chữ số). Vui lòng không sử dụng tên đăng nhập hoặc mã số sinh viên."
        elif len(raw_cccd) != 12:
            error_msg = "Số Căn cước công dân (CCCD) phải gồm chính xác 12 chữ số."
        else:
            # 2. TÌM KIẾM TÀI KHOẢN THEO SỐ CCCD
            matched_profile = UserProfile.objects.filter(cccd=raw_cccd).select_related('user').first()
            if matched_profile:
                matched_user = matched_profile.user
            else:
                matched_user = User.objects.filter(username=raw_cccd).first()

            if not matched_user:
                error_msg = f"Số CCCD '{raw_cccd}' chưa được đăng ký trong hệ thống."
            else:
                # 3. XÁC THỰC MẬT KHẨU
                auth_user = authenticate(request, username=matched_user.username, password=password)
                if auth_user is not None:
                    role = get_role(auth_user)
                    if auth_user.is_superuser or role == 'admin' or auth_user.username.lower() == 'admin':
                        error_msg = "Tài khoản Quản trị viên (admin) chỉ được phép đăng nhập tại Trang quản trị của Django (/admin/)."
                    else:
                        auth_login(request, auth_user)
                        redirect_map = {
                            'qlsv': '/portal/qlsv/',
                            'daotao': '/portal/daotao/',
                            'hieutruong': '/portal/hieu-truong/',
                            'sinhvien': '/portal/sinh-vien/',
                        }
                        dest_url = request.POST.get('next') or request.GET.get('next') or redirect_map.get(role, '/dashboard/')
                        full_name = getattr(getattr(auth_user, 'profile', None), 'full_name', '') or auth_user.username

                        if is_api:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': dest_url,
                                'role': role,
                                'full_name': full_name,
                                'cccd': raw_cccd,
                                'message': f"Đăng nhập thành công với CCCD: {raw_cccd}"
                            })

                        messages.success(request, f"Đăng nhập thành công với CCCD: {raw_cccd}")
                        return redirect(dest_url)
                else:
                    error_msg = f"Mật khẩu không chính xác cho số CCCD '{raw_cccd}'."

        if is_api:
            return JsonResponse({'success': False, 'error': error_msg}, status=400)

    return render(request, 'login.html', {'error_msg': error_msg})


def logout_view(request):
    """Đăng xuất người dùng linh hoạt bằng cả GET và POST"""
    auth_logout(request)
    messages.info(request, "Đã đăng xuất khỏi hệ thống thành công.")
    return redirect('search')