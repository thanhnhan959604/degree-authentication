from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from django.conf import settings  # Update: đọc các công tắc mới trong settings (PUBLIC_BASE_URL, ALLOW_LOOKUP_BY_SERIAL...)
from django.core.cache import cache  # Update: bộ đếm giới hạn tần suất tra cứu (cache bộ nhớ mặc định của Django)

from .models import Certificate, ApprovalLog, UserProfile
from .models import normalize_verify_code, VERIFY_CODE_LENGTH  # Update: chuẩn hoá mã xác minh người dùng nhập
from .models import ShareToken, VerificationLog  # Update: liên kết chia sẻ + nhật ký xác minh
from .security_helper import (  # Update: băm CCCD, mã chia sẻ, IP (file mới security_helper.py)
    hash_national_id, national_id_last4, is_valid_national_id, normalize_national_id,
    new_share_token, hash_token, hash_ip,
)
from .security_helper import encrypt_national_id, decrypt_national_id  # Update: mã hoá / giải mã CCCD cho nút con mắt
from django.views.decorators.cache import never_cache  # Update: trang có CCCD đầy đủ không được lưu cache trình duyệt
from django.http import HttpResponseForbidden, Http404  # Update: từ chối ở tầng backend (không chỉ ẩn nút trên giao diện)
from .models import DiplomaAccessLog  # Update: nhật ký xem / tải ảnh văn bằng gốc
from . import diploma_helper  # Update: dựng / che / phân phối ảnh văn bằng (file mới diploma_helper.py)
import json as _json  # Update: đọc địa chỉ hợp đồng cho trang chi tiết
from pathlib import Path  # Update
from datetime import timedelta  # Update: tính hạn liên kết chia sẻ
from django.db.models import F  # Update: tăng lượt xem an toàn khi nhiều người mở cùng lúc
from django.urls import reverse  # Update: tạo đường dẫn kích hoạt tài khoản
from django.core.mail import send_mail  # Update: gửi email link kích hoạt
from django.contrib.auth.forms import SetPasswordForm  # Update: form đặt mật khẩu có sẵn của Django (kèm kiểm tra độ mạnh)
from django.contrib.auth.tokens import default_token_generator  # Update: token kích hoạt 1 lần, có hạn (PASSWORD_RESET_TIMEOUT)
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode  # Update: mã hoá id trong link kích hoạt
from django.utils.http import url_has_allowed_host_and_scheme  # Update: quay về trang trước an toàn
from django.utils.encoding import force_bytes, force_str  # Update
from .blockchain import (
    register_onchain,
    approve_onchain,
    revoke_onchain
)
from .blockchain import (  # Update: đọc trạng thái trên chuỗi + ký / kiểm chữ ký điện tử của nhà trường
    get_onchain_status, sign_certificate, recover_signer, build_signing_payload, ROLE_CONFIG,
)
import hashlib  # Update: băm lý do thu hồi trước khi đưa lên chuỗi
from datetime import datetime, timezone as dt_timezone  # Update: đổi mốc thời gian on-chain (giây) sang ngày giờ
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

# Update: Các vai trò cán bộ nhà trường (dùng để chặn người dùng có vai trò lạ / chưa phân quyền)
STAFF_ROLES = ('qlsv', 'daotao', 'hieutruong', 'admin')


def build_public_url(request, path):
    """Update: Tạo URL tuyệt đối cho mã QR"""
    if settings.PUBLIC_BASE_URL:
        return f"{settings.PUBLIC_BASE_URL}{path}"
    return request.build_absolute_uri(path)


def _client_ip(request):
    """Update: Lấy IP người tra cứu để giới hạn tần suất"""
    return request.META.get('REMOTE_ADDR', 'unknown')


def _rate_hit(key, window):
    """Update: Tăng bộ đếm `key` (tự hết hạn sau `window` giây) và trả về số lượt hiện tại"""
    if cache.add(key, 1, timeout=window):  # lần đầu trong cửa sổ thời gian
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # khoá vừa hết hạn giữa 2 lệnh
        cache.set(key, 1, timeout=window)
        return 1


def _public_lookup(request, raw_query):
    """Update: Tra cứu công khai Cấp độ 1 dùng chung cho ô tìm kiếm (/?q=) và link QR (/verify/<mã>/)"""
    ip = _client_ip(request)
    ctx = {'query': raw_query, 'result': None, 'lookup_mode': None, 'blocked': False}
    if not raw_query:
        return ctx

    miss_key = f"lookup-miss:{ip}"
    # Đã tra sai quá nhiều lần -> khoá tạm, không tra tiếp (không cho biết mã nào đúng/sai)
    if (cache.get(miss_key) or 0) >= settings.LOOKUP_MISS_RATE:
        ctx['blocked'] = True
        return ctx
    if _rate_hit(f"lookup:{ip}", settings.LOOKUP_WINDOW) > settings.LOOKUP_RATE:
        ctx['blocked'] = True
        return ctx

    cert = None
    code = normalize_verify_code(raw_query)
    if len(code) == VERIFY_CODE_LENGTH:
        cert = Certificate.objects.filter(verify_code=code, status__in=Certificate.PUBLIC_STATUSES).first()
        if cert:
            ctx['lookup_mode'] = 'code'
    if cert is None and settings.ALLOW_LOOKUP_BY_SERIAL:
        cert = Certificate.objects.filter(serial_number__iexact=raw_query.strip(),
                                          status__in=Certificate.PUBLIC_STATUSES).first()
        if cert:
            ctx['lookup_mode'] = 'serial'

    if cert is None:
        _rate_hit(miss_key, settings.LOOKUP_MISS_WINDOW)  # đếm lượt tra sai
        return ctx

    # Họ tên hiển thị công khai: che bớt theo cấu hình; tra bằng số hiệu thì không hiện họ tên
    if ctx['lookup_mode'] == 'serial':
        public_name = None
    else:
        public_name = cert.masked_name if settings.MASK_PUBLIC_NAME else cert.student_name
    # Update: Phần điền kết quả tách ra _fill_result() để dùng chung với trang liên kết chia sẻ
    _fill_result(ctx, cert, public_name)
    # Update: Ảnh văn bằng công khai (đã che)
    if ctx['lookup_mode'] == 'code':
        ctx['show_diploma'] = True
        # ảnh scan chưa được cán bộ duyệt vùng che -> hiện trạng thái "chưa có ảnh", không gọi ảnh
        if not (cert.diploma_original and not cert.diploma_public_approved):
            ctx['diploma_img_url'] = reverse('public_diploma_image', args=[cert.verify_code_display])
    # Update: Ghi nhật ký lượt xác minh để sinh viên xem được ai đã kiểm tra văn bằng của mình
    _log_verification(request, cert, 'public_serial' if ctx['lookup_mode'] == 'serial' else 'public_code')
    return ctx


def _fill_result(ctx, cert, public_name):
    """Update: Điền dữ liệu hiển thị kết quả xác minh"""
    ctx['result'] = cert
    ctx['public_name'] = public_name
    # Bằng chứng xác thực (Khu vực 4).
    ctx['hash_ok'] = (cert.data_hash == cert.calculate_data_hash())  # dữ liệu hiện tại khớp dấu băm đã lưu
    ctx['verified_at'] = timezone.now()  # thời điểm thực hiện xác minh
    # Update: Đối chiếu trực tiếp với chuỗi và kiểm chữ ký điện tử
    ctx.update(_verify_against_chain_and_signature(cert, ctx['hash_ok']))
    return ctx


def _iso_date(value):
    """Update: Ngày dạng 'YYYY-MM-DD' (chấp nhận cả date lẫn chuỗi)"""
    if not value:
        return ''
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)


def _verify_against_chain_and_signature(cert, hash_ok):
    """Update: Kết luận xác minh từ 3 nguồn: dữ liệu ↔ dấu băm, dấu băm ↔ chuỗi, chữ ký ↔ ví Hiệu trưởng"""
    out = {'chain_state': 'unavailable', 'chain_issued_at': None, 'signature_state': 'none',
           'signer_address': None, 'fail_reasons': []}

    chain = get_onchain_status(cert.serial_number)
    if chain.get('ok'):
        if not chain.get('found'):
            out['chain_state'] = 'missing'  # không có bản ghi: cảnh báo, chưa đủ để kết luận giả
        elif (chain.get('data_hash') or '').lower() != (cert.data_hash or '').lower():
            out['chain_state'] = 'mismatch'
            out['fail_reasons'].append("Thông tin văn bằng không khớp với bản ghi gốc trong hệ thống lưu trữ chống chỉnh sửa.")
        else:
            on_status = chain.get('status')
            if cert.status == 'ISSUED' and on_status == 'Issued':
                out['chain_state'] = 'match'
            elif cert.status in Certificate.END_STATUSES and on_status == 'Revoked':
                out['chain_state'] = 'match'
            elif cert.status == 'ISSUED' and on_status == 'Revoked':
                out['chain_state'] = 'revoked_onchain'
                out['fail_reasons'].append("Hệ thống lưu trữ chống chỉnh sửa ghi nhận văn bằng này đã bị thu hồi.")
            elif cert.status == 'ISSUED':
                out['chain_state'] = 'not_issued_onchain'
                out['fail_reasons'].append("Việc cấp văn bằng chưa được ghi nhận đầy đủ trong hệ thống lưu trữ chống chỉnh sửa.")
            else:
                out['chain_state'] = 'end_pending_onchain'  # trường đã thu hồi nhưng chuỗi chưa cập nhật: vẫn hiện "đã thu hồi"
        if chain.get('issued_at'):
            out['chain_issued_at'] = datetime.fromtimestamp(chain['issued_at'], tz=dt_timezone.utc)

    if cert.issuer_signature:
        # Địa chỉ người ký hợp lệ: ưu tiên địa chỉ Hiệu trưởng do HỢP ĐỒNG công nhận; mất kết nối chuỗi thì dùng cấu hình
        expected = chain.get('rector_address') if chain.get('ok') else None
        expected = expected or ROLE_CONFIG['hieutruong']['address']
        payload = build_signing_payload(cert.serial_number, cert.data_hash, _iso_date(cert.issue_date))
        signer = recover_signer(payload, cert.issuer_signature)
        out['signer_address'] = signer
        if signer and expected and signer.lower() == expected.lower():
            out['signature_state'] = 'ok'
        else:
            out['signature_state'] = 'fail'
            out['fail_reasons'].append("Chữ ký điện tử không hợp lệ, không xác minh được nguồn phát hành.")

    if not hash_ok:
        out['fail_reasons'].insert(0, "Thông tin văn bằng không trùng khớp với bản gốc nhà trường đã cấp.")
    out['failed'] = bool(out['fail_reasons'])
    return out


def _log_verification(request, cert, channel, outcome='shown', share=None):
    """Update: Ghi 1 dòng VerificationLog"""
    try:
        VerificationLog.objects.create(certificate=cert, share=share, channel=channel, outcome=outcome,
                                       ip_hash=hash_ip(_client_ip(request)))
    except Exception:
        pass


def search_view(request):
    """Trang tra cứu công khai văn bằng - ai cũng có thể truy cập"""
    # Update: chỉ tra theo mã xác minh (và số hiệu nếu bật công tắc), không theo họ tên / mã SV
    query = request.GET.get('q', '').strip()
    ctx = _public_lookup(request, query)
    ctx['allow_serial'] = settings.ALLOW_LOOKUP_BY_SERIAL  # để giao diện hướng dẫn đúng loại mã được nhập
    return render(request, 'certificates/search.html', ctx, status=429 if ctx['blocked'] else 200)


def verify_view(request, code):
    """Update: Trang đích của mã QR in trên văn bằng: /verify/<mã xác minh>/ (Cấp độ 1 - công khai)"""
    ctx = _public_lookup(request, code)
    ctx['allow_serial'] = settings.ALLOW_LOOKUP_BY_SERIAL
    return render(request, 'certificates/search.html', ctx, status=429 if ctx['blocked'] else 200)




@login_required(login_url='login')
def dashboard(request):
    """Bảng điều khiển nội bộ và Hàng đợi duyệt hồ sơ theo đúng phân quyền tuần tự"""
    role = get_role(request.user)  # qlsv, daotao, hieutruong, admin
    if role == 'student':  # Update: sinh viên không dùng dashboard cán bộ → chuyển về trang cá nhân
        return redirect('student_portal')
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
    # Update: chỉ qlsv/admin thấy toàn bộ hồ sơ
    elif role in ('qlsv', 'admin'):
        base_qs = Certificate.objects.all()
    else:  # Update: vai trò không thuộc cán bộ → không thấy hồ sơ nào
        base_qs = Certificate.objects.none()
        messages.warning(request, "Tài khoản chưa được phân quyền cán bộ. Vui lòng liên hệ quản trị viên.")

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
    # Update: Đếm cả Đã hủy / Đã thay thế vào nhóm hết hiệu lực
    revoked_count = base_qs.filter(status__in=Certificate.END_STATUSES).count()

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
        # Update: Tab "Đã thu hồi" hiện cả Đã hủy / Đã thay thế
        qs = qs.filter(status__in=Certificate.END_STATUSES)

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
        'create_form': request.session.pop('create_form', None),  # Update: dữ liệu giữ lại khi tạo hồ sơ bị lỗi
    })


# Update: Sau khi duyệt / trả / sửa / thu hồi thì quay về trang người dùng vừa thao tác (chỉ nhận đường dẫn nội bộ)
def _back(request):
    nxt = request.POST.get('next', '')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(nxt)
    return redirect('dashboard')


# Update: Lỗi khi tạo hồ sơ thì mở lại hộp thoại với dữ liệu đã nhập (không giữ số CCCD)
CREATE_FORM_FIELDS = ('serial_number', 'student_id', 'student_name', 'date_of_birth', 'major', 'graduation_year',
                      'classification', 'degree_type', 'issue_date', 'student_email')


def _back_to_create_form(request):
    request.session['create_form'] = {k: request.POST.get(k, '').strip() for k in CREATE_FORM_FIELDS}
    return redirect(reverse('dashboard') + '?action=create')


# Update: Điều kiện trạng thái dùng chung cho trả hồ sơ / sửa hồ sơ (khớp với điều kiện hiện nút trên dashboard)
def _can_reject(role, cert):
    if cert.status != 'PENDING':
        return False
    s, a, r = cert.student_affairs_approved, cert.academic_affairs_approved, cert.rector_approved
    if role == 'hieutruong':
        return s and a and not r and not cert.is_rejected
    if role == 'daotao':
        return s and not a
    if role == 'qlsv':
        return not s and not cert.is_rejected
    return not cert.is_rejected  # admin: như nút trên dashboard


def _can_edit(role, cert):
    if cert.status != 'PENDING' or not cert.is_rejected:
        return False
    if role == 'daotao':
        return cert.rejected_by == 'hieutruong' and cert.student_affairs_approved and not cert.academic_affairs_approved
    if role == 'qlsv':
        return not cert.student_affairs_approved
    return True  # admin


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
        return _back_to_create_form(request)

    if classification not in Certificate.CLASSIFICATIONS:  # Update: chỉ nhận xếp loại chuẩn
        messages.error(request, "Xếp loại tốt nghiệp không hợp lệ.")
        return _back_to_create_form(request)

    if Certificate.objects.filter(serial_number=serial_number).exists():
        messages.error(request, f"Số hiệu văn bằng '{serial_number}' đã tồn tại trong hệ thống.")
        return _back_to_create_form(request)

    # Update: Số CCCD (chỉ lưu dạng băm + 4 số cuối) và email sinh viên, không bắt buộc
    national_id = request.POST.get('national_id', '').strip()
    student_email = request.POST.get('student_email', '').strip() or None
    if national_id and not is_valid_national_id(national_id):
        messages.error(request, "Số CCCD phải gồm đúng 12 chữ số.")
        return _back_to_create_form(request)

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
            status='PENDING',
            national_id_hash=hash_national_id(national_id) or None,      # Update
            national_id_last4=national_id_last4(national_id) or None,    # Update
            national_id_encrypted=encrypt_national_id(national_id) or None,  # Update
            student_email=student_email,                                  # Update
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
        return _back(request)

    # Update: chỉ sửa hồ sơ đang chờ duyệt và đã bị trả về đúng phòng mình; văn bằng đã cấp / đã thu hồi không sửa được
    if request.method == 'POST' and not _can_edit(get_role(request.user), cert):
        messages.error(request, f"Hồ sơ '{cert.serial_number}' không ở trạng thái bị trả về cho phòng của bạn nên không thể chỉnh sửa.")
        return _back(request)

    if request.method == 'POST' and request.POST.get('classification', cert.classification).strip() not in Certificate.CLASSIFICATIONS:
        messages.error(request, "Xếp loại tốt nghiệp không hợp lệ.")  # Update
        return _back(request)

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
        return _back(request)

    return redirect('dashboard')


@login_required(login_url='login')
def certificate_approve(request, pk):
    """Xử lý phê duyệt hồ sơ theo đúng 3 bước vai trò tuần tự"""
    if request.method != 'POST':
        return _back(request)

    cert = get_object_or_404(Certificate, pk=pk)
    role = get_role(request.user)

    # Update: chỉ duyệt hồ sơ đang chờ duyệt (văn bằng đã cấp / đã thu hồi / hủy / thay thế không duyệt lại)
    if cert.status != 'PENDING':
        messages.error(request, f"Văn bằng '{cert.serial_number}' không còn ở trạng thái chờ duyệt.")
        return _back(request)

    now = timezone.now()
    tx_hash = None

    if role == 'qlsv' or (role == 'admin' and not cert.student_affairs_approved):
        if cert.student_affairs_approved:  # Update: QLSV đã duyệt rồi thì không duyệt lần nữa
            messages.error(request, f"Hồ sơ '{cert.serial_number}' đã được Phòng QLSV duyệt trước đó.")
            return _back(request)
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
            return _back(request)
        if cert.academic_affairs_approved:  # Update: Đào tạo đã duyệt rồi thì không duyệt lần nữa
            messages.error(request, f"Hồ sơ '{cert.serial_number}' đã được Phòng Đào tạo duyệt trước đó.")
            return _back(request)

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
            return _back(request)
        if cert.rector_approved:  # Update: đã ký rồi thì không ký lại
            messages.error(request, f"Văn bằng '{cert.serial_number}' đã được Hiệu trưởng ký trước đó.")
            return _back(request)

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
        # Update: Hiệu trưởng ký điện tử lên
        signature, _payload = sign_certificate(cert.serial_number, cert.data_hash, _iso_date(cert.issue_date))
        if signature:
            cert.issuer_signature = signature
            cert.signed_at = now
        if not cert.issuer_name:  # Update: ghi tên trường TẠI THỜI ĐIỂM CẤP (đổi tên trường sau này không ảnh hưởng)
            cert.issuer_name = settings.INSTITUTION['name']
        cert.save()

        ApprovalLog.objects.create(
            certificate=cert,
            action="HIỆU TRƯỞNG KÝ DUYỆT PHÁT HÀNH",
            actor=role,
            comment="Hiệu trưởng ký số phát hành chính thức văn bằng lên Blockchain Besu",
            tx_hash=tx_hash or cert.tx_hash
        )
        messages.success(request, f"Hiệu trưởng đã ký duyệt thành công! Văn bằng '{cert.serial_number}' đã được phát hành On-Chain.")
        # Update: văn bằng vừa phát hành: tạo tài khoản sinh viên + gửi link kích hoạt
        note = _provision_student_account(request, cert)
        if note:
            messages.info(request, note)

    else:
        messages.error(request, "Tài khoản của bạn không có thẩm quyền duyệt ở bước này.")

    return _back(request)

    
@login_required(login_url='login')
def certificate_reject(request, pk):
    """Từ chối hồ sơ kèm lý do, trả về đúng phòng ban liền trước đó"""
    if request.method != 'POST':
        return _back(request)

    cert = get_object_or_404(Certificate, pk=pk)
    reason = request.POST.get('reason', 'Thông tin chưa chính xác, yêu cầu kiểm tra lại').strip()
    role = get_role(request.user)

    # Update: chỉ trả hồ sơ đang chờ duyệt và đang ở đúng bước của phòng mình
    if role in ('qlsv', 'daotao', 'hieutruong', 'admin') and not _can_reject(role, cert):
        messages.error(request, f"Hồ sơ '{cert.serial_number}' không ở bước chờ phòng của bạn xử lý nên không thể trả về.")
        return _back(request)

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

    return _back(request)


@login_required(login_url='login')
def certificate_revoke(request, pk):
    """Quy trình thu hồi văn bằng (Cần cả 3 phòng ban xác nhận)"""
    if request.method != 'POST':
        return _back(request)

    cert = get_object_or_404(Certificate, pk=pk)
    if cert.status != 'ISSUED':
        messages.error(request, "Chỉ có thể thu hồi văn bằng đã phát hành chính thức.")
        return _back(request)

    role = get_role(request.user)
    reason = request.POST.get('reason', 'Phát hiện sai sót trong hồ sơ gốc').strip()

    # Update: phòng đã xác nhận thu hồi thì không xác nhận lại (tránh nhật ký và giao dịch trùng)
    if role not in ('qlsv', 'daotao', 'hieutruong', 'admin'):
        messages.error(request, "Bạn không có quyền thu hồi văn bằng.")
        return _back(request)
    already = {'qlsv': cert.student_affairs_revoke, 'daotao': cert.academic_affairs_revoke, 'hieutruong': cert.rector_revoke}
    if already.get(role):
        messages.info(request, f"Phòng của bạn đã xác nhận thu hồi văn bằng '{cert.serial_number}'. "
                               f"Đang chờ các phòng còn lại ({cert.revoke_confirmations}/3).")
        return _back(request)

    # Update: Loại kết thúc hiệu lực: Thu hồi (mặc định, như cũ) / Hủy / Thay thế bằng văn bằng khác
    end_type = request.POST.get('end_type', 'REVOKED').strip().upper()
    if end_type not in Certificate.END_STATUSES:
        end_type = 'REVOKED'
    replacement = None
    if end_type == 'REPLACED':
        replaced_serial = request.POST.get('replaced_serial', '').strip()
        replacement = Certificate.objects.filter(serial_number=replaced_serial).exclude(pk=cert.pk).first()
        if replacement is None:
            messages.error(request, "Chọn 'Thay thế' cần nhập đúng số hiệu của văn bằng thay thế đã có trong hệ thống.")
            return _back(request)

    if not cert.revoke_reason:
        cert.revoke_reason = reason
    if not cert.end_type:  # Update: giữ loại do phòng ban đầu tiên đề xuất (giống cách giữ lý do ở trên)
        cert.end_type = end_type
        if replacement is not None:
            cert.replaced_by = replacement

    now = timezone.now()
    tx_hash = None

    # Update: lên chuỗi chỉ ghi "LOẠI#dấu băm lý do", lý do đầy đủ lưu trong DB
    onchain_reason = f"{cert.end_type or end_type}#{hashlib.sha256(reason.encode('utf-8')).hexdigest()[:16]}"

    if role == 'qlsv' or role == 'admin':
        cert.student_affairs_revoke = True
        tx_hash = revoke_onchain(cert.serial_number, onchain_reason, 'qlsv')
        ApprovalLog.objects.create(
            certificate=cert,
            action="QLSV XÁC NHẬN THU HỒI",
            actor=role,
            comment=f"Lý do: {reason}",
            tx_hash=tx_hash
        )

    if role == 'daotao' or role == 'admin':
        cert.academic_affairs_revoke = True
        tx_hash = revoke_onchain(cert.serial_number, onchain_reason, 'daotao')  # Update
        ApprovalLog.objects.create(
            certificate=cert,
            action="ĐÀO TẠO XÁC NHẬN THU HỒI",
            actor=role,
            comment=f"Lý do: {reason}",
            tx_hash=tx_hash
        )

    if role == 'hieutruong' or role == 'admin':
        cert.rector_revoke = True
        tx_hash = revoke_onchain(cert.serial_number, onchain_reason, 'hieutruong')  # Update
        ApprovalLog.objects.create(
            certificate=cert,
            action="HIỆU TRƯỞNG XÁC NHẬN THU HỒI",
            actor=role,
            comment=f"Lý do: {reason}",
            tx_hash=tx_hash
        )

    # Nếu cả 3 bên đã xác nhận (hoặc admin ép thu hồi)
    if (cert.student_affairs_revoke and cert.academic_affairs_revoke and cert.rector_revoke) or role == 'admin':
        # Update: Đặt trạng thái theo loại kết thúc đã đề xuất
        cert.status = cert.end_type or 'REVOKED'
        cert.revoked_at = now
        cert.student_affairs_revoke = True
        cert.academic_affairs_revoke = True
        cert.rector_revoke = True
        # Update: Thông báo nêu đúng loại kết thúc (Đã thu hồi / Đã hủy / Đã thay thế)
        messages.error(request, f"Văn bằng '{cert.serial_number}' đã chính thức chuyển trạng thái "
                                f"'{cert.get_status_display().upper()}' trên toàn hệ thống.")
    else:
        messages.info(request, f"Đã ghi nhận ý kiến thu hồi từ {role}. Cần đủ 3 phòng ban xác nhận để hoàn tất thu hồi.")

    cert.save()
    return _back(request)


@login_required(login_url='login')
def import_excel(request):
    """Nhập danh sách văn bằng từ file Excel (.xlsx) với kiểm tra tính toàn vẹn"""
    if request.method != 'POST':
        return redirect('dashboard')

    # Update: Kiểm tra quyền theo VAI TRÒ như các view khác
    if get_role(request.user) not in ['qlsv', 'admin']:
        messages.error(request, "Bạn không có quyền nhập file Excel.")
        return redirect('dashboard')

    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        messages.error(request, "Vui lòng chọn tệp Excel (.xlsx).")
        return redirect('dashboard')

    if not excel_file.name.endswith(('.xlsx', '.xls')):
        messages.error(request, "Định dạng tệp không hợp lệ. Vui lòng tải lên tệp .xlsx.")
        return redirect('dashboard')

    valid_records, errors = process_excel_upload(excel_file)

    if errors:
        error_msg = f"Phát hiện {len(errors)} lỗi trong tệp Excel: " + " | ".join(errors[:5])
        if len(errors) > 5:
            error_msg += f" (và {len(errors) - 5} lỗi khác...)"
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

    messages.success(request, f"Đã nhập thành công {success_count} hồ sơ văn bằng từ tệp Excel!")
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


@login_required(login_url='login')  # Update: chỉ cán bộ hoặc sinh viên chủ văn bằng mới mở được phôi in
def certificate_print_view(request, pk):
    """Trang xem và in phôi văn bằng chuẩn A4 có mã QR"""
    # Update: Phôi in chứa đầy đủ ngày sinh, mã SV, xếp loại → chỉ cán bộ nhà trường được mở
    # Update: Bổ sung: sinh viên chủ sở hữu được mở phôi văn bằng ĐÃ PHÁT HÀNH của chính mình
    cert = get_object_or_404(Certificate, pk=pk)
    if get_role(request.user) not in STAFF_ROLES and not _student_owns(request.user, cert):
        messages.error(request, "Bạn không có quyền xem phôi văn bằng này.")
        return redirect('search')
    # Update: QR trỏ tới trang xác minh bằng mã ngẫu nhiên
    if not cert.verify_code:  # hồ sơ cũ chưa có mã -> lưu lại để save() tự cấp
        cert.save()
    verify_url = build_public_url(request, f"/verify/{cert.verify_code_display}/")
    qr_data = generate_qr_base64(verify_url)

    return render(request, 'certificates/print_view.html', {
        'cert': cert,
        'qr_data': qr_data,
        'verify_url': verify_url,
        'public_lookup_url': build_public_url(request, '/'),  # Update: địa chỉ trang tra cứu in trên phôi
        'back_url': reverse('student_portal') if get_role(request.user) == 'student' else reverse('dashboard'),  # Update
    })



@ensure_csrf_cookie
def login_view(request):
    """Xử lý đăng nhập phân biệt chính xác chữ hoa / chữ thường theo chuẩn Django"""
    if request.user.is_authenticated:
        # Update: sinh viên về trang cá nhân, cán bộ về dashboard
        return redirect('student_portal' if get_role(request.user) == 'student' else 'dashboard')

    error_msg = None
    if request.method == 'POST':
        raw_u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '').strip()

        # Update: Khoá tạm theo (IP + tên đăng nhập) khi sai quá LOGIN_FAIL_LIMIT lần trong
        fail_key = f"login-fail:{_client_ip(request)}:{hash_token(raw_u.lower())[:16]}"
        if (cache.get(fail_key) or 0) >= settings.LOGIN_FAIL_LIMIT:
            error_msg = (f"Bạn đã đăng nhập sai quá nhiều lần. Vui lòng thử lại sau "
                         f"{settings.LOGIN_FAIL_WINDOW // 60} phút.")
            return render(request, 'certificates/login.html', {'error_msg': error_msg})

        # Update: Sinh viên đăng nhập bằng SỐ CCCD
        if raw_u.replace(' ', '').isdigit() and is_valid_national_id(raw_u):
            profile = UserProfile.objects.filter(role='student', national_id_hash=hash_national_id(raw_u)).first()
            actual_username = profile.user.username if profile else raw_u
        else:
            # Kiểm tra nếu đăng nhập bằng email chính xác (giữ như cũ)
            matched_user = User.objects.filter(email=raw_u).first()
            actual_username = matched_user.username if matched_user else raw_u

        # Xác thực với Django (PostgreSQL so khớp phân biệt chính xác hoa/thường)
        user = authenticate(request, username=actual_username, password=p)

        if user is not None:
            cache.delete(fail_key)  # Update: đăng nhập đúng → xoá bộ đếm sai
            auth_login(request, user)
            is_student = get_role(user) == 'student'  # Update
            default_url = reverse('student_portal') if is_student else '/dashboard/'
            next_url = request.POST.get('next') or request.GET.get('next') or default_url
            # Update: Chỉ chuyển hướng tới địa chỉ nội bộ
            from django.utils.http import url_has_allowed_host_and_scheme
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                next_url = default_url
            if is_student:
                messages.success(request, "Đăng nhập thành công. Chào mừng bạn đến với trang văn bằng cá nhân.")
            else:
                messages.success(request, f"Đăng nhập thành công với tài khoản: {user.username}")
            return redirect(next_url)
        else:
            _rate_hit(fail_key, settings.LOGIN_FAIL_WINDOW)  # Update: đếm lượt sai
            # Update: Một thông báo chung cho mọi trường hợp sai
            error_msg = "Tên đăng nhập hoặc mật khẩu không đúng."

    return render(request, 'certificates/login.html', {'error_msg': error_msg})


def logout_view(request):
    """Đăng xuất người dùng linh hoạt bằng cả GET và POST"""
    auth_logout(request)
    messages.info(request, "Đã đăng xuất khỏi hệ thống thành công.")
    return redirect('search')


# =============================================================================
# Update: GIAI ĐOẠN P2 — TÀI KHOẢN SINH VIÊN (đăng nhập bằng số CCCD)
# =============================================================================

def _student_profile(user):
    """Update: Trả về UserProfile nếu user là sinh viên đã liên kết CCCD, ngược lại None"""
    if not user.is_authenticated:
        return None
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if profile.role == 'student' and profile.national_id_hash:
        return profile
    return None


def _student_owns(user, cert):
    """Update: Sinh viên đang đăng nhập có phải chủ sở hữu văn bằng ĐÃ PHÁT HÀNH này không"""
    profile = _student_profile(user)
    return bool(profile and cert.national_id_hash and cert.national_id_hash == profile.national_id_hash
                and cert.status in Certificate.PUBLIC_STATUSES)


def _send_student_link(request, user, purpose='activate'):
    """Update: Gửi email chứa link đặt mật khẩu (kích hoạt lần đầu hoặc quên mật khẩu)"""
    if not user.email:
        return False
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = build_public_url(request, reverse('student_activate', args=[uid, token]))
    hours = settings.PASSWORD_RESET_TIMEOUT // 3600
    inst = settings.INSTITUTION  # Update: tên trường trong email theo nhận diện thống nhất
    if purpose == 'activate':
        subject = f"[{inst['short']}] Kích hoạt tài khoản tra cứu văn bằng"
        intro = "Văn bằng của bạn đã được nhà trường phát hành. Bấm vào liên kết dưới đây để đặt mật khẩu và kích hoạt tài khoản:"
    else:
        subject = f"[{inst['short']}] Đặt lại mật khẩu tài khoản văn bằng"  # Update
        intro = "Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu. Bấm vào liên kết dưới đây để đặt mật khẩu mới:"
    body = (f"Chào {user.first_name or 'bạn'},\n\n{intro}\n\n{link}\n\n"
            f"Liên kết có hiệu lực trong {hours} giờ và chỉ dùng được một lần.\n"
            f"Sau khi kích hoạt, bạn đăng nhập bằng SỐ CCCD và mật khẩu vừa đặt.\n\n"
            f"Nếu bạn không yêu cầu, vui lòng bỏ qua email này.\n\n"
            f"{inst['name']} ({inst['short']}) – {inst['name_en']}")  # Update: chữ ký email
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
        return True
    except Exception:
        return False


def _provision_student_account(request, cert):
    """Update: Tạo hoặc liên kết tài khoản sinh viên cho văn bằng đã phát hành, rồi gửi link kích hoạt"""
    if not cert.national_id_hash:
        return f"Văn bằng '{cert.serial_number}' chưa có số CCCD nên chưa tạo được tài khoản sinh viên."
    if cert.status != 'ISSUED':
        return None
    profile = UserProfile.objects.filter(national_id_hash=cert.national_id_hash).first()
    if profile is None:
        user = User.objects.create_user(username=f"sv_{cert.national_id_hash[:24]}",
                                        email=cert.student_email or '',
                                        first_name=cert.student_name[:150])
        user.set_unusable_password()
        user.save()
        profile = user.profile
        profile.role = 'student'
        profile.national_id_hash = cert.national_id_hash
        profile.save()
        created = True
    else:
        user = profile.user
        created = False
        if cert.student_email and user.email != cert.student_email:  # cập nhật email mới nhất do QLSV nhập
            user.email = cert.student_email
            user.save(update_fields=['email'])

    if user.has_usable_password():
        return "Sinh viên đã có tài khoản và đã kích hoạt; văn bằng mới tự hiện trong trang cá nhân của sinh viên."
    if not user.email:
        return (("Đã tạo" if created else "Đã có") +
                " tài khoản sinh viên nhưng chưa có email nên chưa gửi được link kích hoạt. Vui lòng bổ sung email.")
    sent = _send_student_link(request, user, 'activate')
    ApprovalLog.objects.create(certificate=cert, action="GỬI LINK KÍCH HOẠT SV",
                               actor=request.user.username if request.user.is_authenticated else 'system',
                               comment=("Đã gửi" if sent else "Gửi thất bại") + " link kích hoạt tới email sinh viên")
    if sent:
        return f"Đã gửi link kích hoạt tài khoản tới email sinh viên ({user.email})."
    return "Không gửi được email kích hoạt. Kiểm tra cấu hình email (EMAIL_BACKEND) rồi bấm gửi lại."


@login_required(login_url='login')
def certificate_student_account(request, pk):
    """Update: Cán bộ QLSV/Admin cập nhật số CCCD + email sinh viên cho một hồ sơ"""
    if request.method != 'POST':
        return redirect('dashboard')
    if get_role(request.user) not in ('qlsv', 'admin'):
        messages.error(request, "Bạn không có quyền cập nhật tài khoản sinh viên.")
        return redirect('dashboard')
    cert = get_object_or_404(Certificate, pk=pk)

    national_id = request.POST.get('national_id', '').strip()
    email = request.POST.get('student_email', '').strip()
    if national_id:  # để trống = giữ CCCD đã lưu (vì hệ thống không lưu số đầy đủ để hiện lại)
        if not is_valid_national_id(national_id):
            messages.error(request, "Số CCCD phải gồm đúng 12 chữ số.")
            return redirect('dashboard')
        new_hash = hash_national_id(national_id)
        if cert.national_id_hash and cert.national_id_hash != new_hash and cert.status == 'ISSUED':
            # Đổi CCCD của văn bằng đã phát hành = chuyển văn bằng sang người khác -> phải có lý do rõ ràng, ghi nhật ký
            ApprovalLog.objects.create(certificate=cert, action="ĐỔI CCCD SINH VIÊN", actor=request.user.username,
                                       comment=f"Đổi CCCD từ ••••{cert.national_id_last4} sang ••••{national_id_last4(national_id)}")
        cert.national_id_hash = new_hash
        cert.national_id_last4 = national_id_last4(national_id)
        cert.national_id_encrypted = encrypt_national_id(national_id)  # Update
    if email:
        cert.student_email = email
    cert.save()

    note = _provision_student_account(request, cert) if cert.status == 'ISSUED' else \
        "Đã lưu thông tin. Tài khoản sinh viên sẽ được tạo khi văn bằng được phát hành."
    messages.success(request, f"Đã cập nhật thông tin tài khoản sinh viên cho '{cert.serial_number}'. {note or ''}")
    return redirect('dashboard')


def student_activate(request, uidb64, token):
    """Update: Trang đặt mật khẩu từ link trong email (kích hoạt lần đầu / quên mật khẩu)"""
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user is None or get_role(user) != 'student' or not default_token_generator.check_token(user, token):
        return render(request, 'certificates/student_portal.html', {'mode': 'link_invalid'})

    form = SetPasswordForm(user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()  # đặt mật khẩu -> token cũ tự mất hiệu lực
        auth_login(request, user)
        messages.success(request, "Đặt mật khẩu thành công. Từ nay bạn đăng nhập bằng số CCCD và mật khẩu vừa đặt.")
        return redirect('student_portal')
    return render(request, 'certificates/student_portal.html', {'mode': 'activate', 'form': form})


def student_forgot(request):
    """Update: Sinh viên chưa nhận được link kích hoạt / quên mật khẩu: nhập số CCCD để nhận link mới"""
    if request.method == 'POST':
        key = f"forgot:{_client_ip(request)}"
        if _rate_hit(key, 3600) <= 5:  # tối đa 5 yêu cầu / giờ / IP
            nid = request.POST.get('national_id', '')
            if is_valid_national_id(nid):
                profile = UserProfile.objects.filter(role='student', national_id_hash=hash_national_id(nid)).first()
                if profile and profile.user.email:
                    _send_student_link(request, profile.user,
                                       'reset' if profile.user.has_usable_password() else 'activate')
        messages.info(request, "Nếu số CCCD đã được nhà trường đăng ký kèm email, một liên kết đặt mật khẩu "
                               "vừa được gửi tới email đó. Vui lòng kiểm tra hộp thư (kể cả mục thư rác).")
        return redirect('login')
    return render(request, 'certificates/student_portal.html', {'mode': 'forgot'})


@never_cache  # Update: trang chứa CCCD đầy đủ (ẩn sau nút con mắt) → không cho trình duyệt / proxy lưu lại
@login_required(login_url='login')
def student_portal(request):
    """Update: Trang cá nhân sinh viên (/me/): văn bằng của mình, mã xác minh + QR, in phôi"""
    profile = _student_profile(request.user)
    if profile is None:
        return redirect('dashboard')
    my_certs = Certificate.objects.filter(national_id_hash=profile.national_id_hash)
    certs = list(my_certs.filter(status__in=Certificate.PUBLIC_STATUSES).order_by('-issue_date', '-created_at'))
    pending_count = my_certs.filter(status='PENDING').count()

    for c in certs:  # gắn thêm dữ liệu hiển thị cho từng văn bằng
        c.verify_url = build_public_url(request, f"/verify/{c.verify_code_display}/")
        c.qr = generate_qr_base64(c.verify_url)
        c.share_list = list(c.shares.all()[:20])
        c.recent_logs = list(c.verification_logs.select_related('share')[:15])
        # Update: Số CCCD đầy đủ cho nút con mắt: chỉ giải mã khi bản giải mã khớp đúng dấu băm của tài
        full = decrypt_national_id(c.national_id_encrypted)
        c.national_id_full = full if full and hash_national_id(full) == profile.national_id_hash else ''

    new_share = request.session.pop('new_share', None)  # liên kết vừa tạo: chỉ hiện đúng 1 lần
    if new_share:
        new_share['qr'] = generate_qr_base64(new_share['url'])
    return render(request, 'certificates/student_portal.html', {
        'mode': 'portal', 'certs': certs, 'pending_count': pending_count,
        'new_share': new_share, 'share_max_days': settings.SHARE_MAX_DAYS,
    })


# =============================================================================
# Update: GIAI ĐOẠN P3 — LIÊN KẾT CHIA SẺ CÓ THỜI HẠN (Cấp độ 2)
# =============================================================================

@login_required(login_url='login')
def student_share_create(request, pk):
    """Update: Sinh viên tạo liên kết chia sẻ cho một văn bằng còn hiệu lực của mình"""
    if request.method != 'POST':
        return redirect('student_portal')
    cert = get_object_or_404(Certificate, pk=pk)
    if not _student_owns(request.user, cert) or cert.status != 'ISSUED':
        messages.error(request, "Chỉ chia sẻ được văn bằng còn hiệu lực của chính bạn.")
        return redirect('student_portal')

    try:
        days = int(request.POST.get('days', '7'))
    except ValueError:
        days = 7
    days = max(1, min(days, settings.SHARE_MAX_DAYS))
    max_views_raw = request.POST.get('max_views', '').strip()
    max_views = None
    if max_views_raw:
        try:
            max_views = max(1, min(int(max_views_raw), 1000))
        except ValueError:
            max_views = None

    token = new_share_token()
    ShareToken.objects.create(
        certificate=cert, token_hash=hash_token(token),
        recipient=request.POST.get('recipient', '').strip()[:120],
        show_full_name=bool(request.POST.get('show_full_name')),
        show_dob=bool(request.POST.get('show_dob')),
        show_student_id=bool(request.POST.get('show_student_id')),
        show_classification=bool(request.POST.get('show_classification')),
        expires_at=timezone.now() + timedelta(days=days),
        max_views=max_views, created_by=request.user,
    )
    # Mã gốc chỉ giữ trong phiên làm việc để hiện cho sinh viên 1 lần; DB chỉ có dấu băm
    request.session['new_share'] = {'cert_id': cert.pk, 'serial': cert.serial_number,
                                    'url': build_public_url(request, reverse('share_verify', args=[token]))}
    messages.success(request, f"Đã tạo liên kết chia sẻ có hiệu lực {days} ngày. Hãy sao chép ngay, liên kết chỉ hiện một lần.")
    return redirect('student_portal')


@login_required(login_url='login')
def student_share_revoke(request, share_id):
    """Update: Sinh viên thu hồi liên kết chia sẻ (người đang giữ link sẽ không xem được nữa)"""
    if request.method != 'POST':
        return redirect('student_portal')
    share = get_object_or_404(ShareToken, pk=share_id)
    if not _student_owns(request.user, share.certificate):
        messages.error(request, "Bạn không có quyền thu hồi liên kết này.")
        return redirect('student_portal')
    if not share.revoked_at:
        share.revoked_at = timezone.now()
        share.save(update_fields=['revoked_at'])
    messages.info(request, "Đã thu hồi liên kết chia sẻ.")
    return redirect('student_portal')


def share_view(request, token):
    """Update: Trang xác minh Cấp độ 2 mở từ liên kết chia sẻ của sinh viên: /verify/s/<mã>/"""
    ip = _client_ip(request)
    ctx = {'query': '', 'result': None, 'lookup_mode': 'share', 'blocked': False, 'share_mode': True,
           'allow_serial': settings.ALLOW_LOOKUP_BY_SERIAL}
    miss_key = f"lookup-miss:{ip}"  # dùng chung bộ đếm với tra cứu công khai
    if (cache.get(miss_key) or 0) >= settings.LOOKUP_MISS_RATE or \
            _rate_hit(f"lookup:{ip}", settings.LOOKUP_WINDOW) > settings.LOOKUP_RATE:
        ctx['blocked'] = True
        return render(request, 'certificates/search.html', ctx, status=429)

    share = ShareToken.objects.select_related('certificate').filter(token_hash=hash_token(token)).first()
    if share is None:
        _rate_hit(miss_key, settings.LOOKUP_MISS_WINDOW)
        return render(request, 'certificates/search.html', ctx)

    cert = share.certificate
    if not share.is_active or cert.status not in Certificate.PUBLIC_STATUSES:
        _log_verification(request, cert, 'share', 'denied', share)
        ctx['share_denied'] = True
        ctx['share_state'] = share.state_display
        return render(request, 'certificates/search.html', ctx)

    ShareToken.objects.filter(pk=share.pk).update(view_count=F('view_count') + 1)  # đếm lượt xem
    _log_verification(request, cert, 'share', 'shown', share)
    public_name = cert.student_name if share.show_full_name else \
        (cert.masked_name if settings.MASK_PUBLIC_NAME else cert.student_name)
    _fill_result(ctx, cert, public_name)
    ctx['share'] = share
    # Update: Ảnh văn bằng cho liên kết chia sẻ (mở thêm đúng các trường sinh viên cho phép)
    ctx['show_diploma'] = True
    if not (cert.diploma_original and not cert.diploma_public_approved):
        ctx['diploma_img_url'] = reverse('share_diploma_image', args=[token])
    return render(request, 'certificates/search.html', ctx)


# =============================================================================
# Update: GIAI ĐOẠN P6 — ẢNH VĂN BẰNG, PHÂN PHỐI THEO QUYỀN Ở BACKEND
# Không có URL tĩnh nào trỏ tới file ảnh; đường dẫn lưu trữ không bao giờ xuất hiện trong HTML.
# =============================================================================

def _png_response(img, *, filename, download=False, cache='private, no-store'):
    """Update: Trả ảnh PNG; 'attachment' khi tải xuống"""
    resp = HttpResponse(diploma_helper.png_bytes(img), content_type='image/png')
    resp['Content-Disposition'] = f'{"attachment" if download else "inline"}; filename="{filename}"'
    resp['Cache-Control'] = cache
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


def _log_diploma(request, cert, action):
    """Update: Ghi nhật ký truy cập ảnh văn bằng (lỗi ghi log không làm hỏng việc xem ảnh)"""
    try:
        DiplomaAccessLog.objects.create(certificate=cert, action=action, ip_hash=hash_ip(_client_ip(request)),
                                        user=request.user if request.user.is_authenticated else None)
    except Exception:
        pass


def _public_allowed_fields():
    """Update: Trường được hiện trên ảnh công khai ngoài thông tin văn bằng: họ tên đầy đủ nếu tắt"""
    return frozenset() if settings.MASK_PUBLIC_NAME else frozenset({'name'})


def _verify_url_for(request, cert):
    return build_public_url(request, f"/verify/{cert.verify_code_display}/")


def public_diploma_image(request, code):
    """Update: Ảnh văn bằng CÔNG KHAI (đã che)"""
    if _rate_hit(f"img:{_client_ip(request)}", 60) > 120:
        return HttpResponse(status=429)
    cert = Certificate.objects.filter(verify_code=normalize_verify_code(code),
                                      status__in=Certificate.PUBLIC_STATUSES).first()
    if cert is None:
        raise Http404
    img, _src = diploma_helper.build_image(cert, 'public', allowed=_public_allowed_fields(),
                                           masked_name=cert.masked_name, verify_url=_verify_url_for(request, cert))
    if img is None:  # ảnh scan chưa được duyệt vùng che -> chưa phát ảnh ra ngoài
        raise Http404
    return _png_response(img, filename=f"van-bang-{cert.serial_number}-cong-khai.png", cache='public, max-age=300')


def share_diploma_image(request, token):
    """Update: Ảnh văn bằng cho liên kết chia sẻ còn hiệu lực: che như công khai nhưng mở các trường"""
    if _rate_hit(f"img:{_client_ip(request)}", 60) > 120:
        return HttpResponse(status=429)
    share = ShareToken.objects.select_related('certificate').filter(token_hash=hash_token(token)).first()
    if share is None or not share.is_active or share.certificate.status not in Certificate.PUBLIC_STATUSES:
        raise Http404
    cert = share.certificate
    allowed = set(_public_allowed_fields())
    for flag, field in (('show_full_name', 'name'), ('show_dob', 'dob'),
                        ('show_classification', 'classification'), ('show_student_id', 'student_id')):
        if getattr(share, flag):
            allowed.add(field)
    img, _src = diploma_helper.build_image(cert, 'share', allowed=frozenset(allowed), masked_name=cert.masked_name,
                                           verify_url=_verify_url_for(request, cert))
    if img is None:
        raise Http404
    return _png_response(img, filename=f"van-bang-{cert.serial_number}.png")


@login_required(login_url='login')
def owner_diploma_image(request, pk):
    """Update: Sinh viên xem / tải ảnh văn bằng ĐẦY ĐỦ của chính mình"""
    cert = get_object_or_404(Certificate, pk=pk)
    if not _student_owns(request.user, cert):
        return HttpResponseForbidden("Bạn không có quyền xem văn bằng này.")
    download = request.GET.get('download') == '1'
    img, _src = diploma_helper.build_image(cert, 'full', verify_url=_verify_url_for(request, cert))
    if img is None:
        raise Http404
    if download:
        _log_diploma(request, cert, 'download_owner')
    return _png_response(img, filename=f"van-bang-{cert.serial_number}.png", download=download)


@login_required(login_url='login')
def staff_diploma_image(request, pk, variant):
    """Update: Ảnh cho cán bộ. 'original' cần quyền view_original_diploma (KHÔNG mặc định có)"""
    if get_role(request.user) not in STAFF_ROLES:
        return HttpResponseForbidden("Chỉ cán bộ nhà trường được truy cập.")
    cert = get_object_or_404(Certificate, pk=pk)
    if variant == 'original':
        if not request.user.has_perm('certificates.view_original_diploma'):
            _log_diploma(request, cert, 'denied')
            return HttpResponseForbidden("Tài khoản chưa được cấp quyền xem ảnh văn bằng gốc.")
        download = request.GET.get('download') == '1'
        img, _src = diploma_helper.build_image(cert, 'full', verify_url=_verify_url_for(request, cert))
        if img is None:
            raise Http404
        _log_diploma(request, cert, 'download_original' if download else 'view_original')
        return _png_response(img, filename=f"van-bang-{cert.serial_number}-goc.png", download=download)
    if variant == 'public':
        mode = 'preview' if cert.diploma_original else 'public'
        img, _src = diploma_helper.build_image(cert, mode, allowed=_public_allowed_fields(),
                                               masked_name=cert.masked_name, verify_url=_verify_url_for(request, cert))
        if img is None:
            raise Http404
        return _png_response(img, filename=f"van-bang-{cert.serial_number}-cong-khai.png")
    raise Http404


@login_required(login_url='login')
def certificate_detail(request, pk):
    """Update: Trang chi tiết văn bằng cho cán bộ: (1) ảnh văn bằng, (2) thông tin hồ sơ"""
    if get_role(request.user) not in STAFF_ROLES:
        messages.error(request, "Chỉ cán bộ nhà trường được xem trang chi tiết văn bằng.")
        return redirect('search')
    cert = get_object_or_404(Certificate, pk=pk)
    hash_ok = (cert.data_hash == cert.calculate_data_hash())
    try:
        with open(Path(settings.BASE_DIR).parent / 'contracts' / 'compiled' / 'contract_info.json', encoding='utf-8') as f:
            contract_address = _json.load(f).get('address', '')
    except OSError:
        contract_address = ''
    ctx = {
        'cert': cert, 'role': get_role(request.user), 'hash_ok': hash_ok, 'contract_address': contract_address,
        'approval_logs': cert.logs.all()[:50],
        'diploma_logs': cert.diploma_logs.select_related('user')[:30],
        'verification_logs': cert.verification_logs.all()[:20],
        'can_view_original': request.user.has_perm('certificates.view_original_diploma'),
        'can_manage_image': request.user.has_perm('certificates.manage_diploma_image'),
        'has_scan': bool(cert.diploma_original),
        'regions_text': diploma_helper.regions_to_text(cert.diploma_regions or settings.DIPLOMA_DEFAULT_REGIONS),
        'region_fields': diploma_helper.REGION_FIELDS,
        'max_upload_mb': settings.DIPLOMA_MAX_UPLOAD_MB,
    }
    ctx.update(_verify_against_chain_and_signature(cert, hash_ok))
    return render(request, 'certificates/certificate_detail.html', ctx)


@login_required(login_url='login')
def diploma_manage(request, pk):
    """Update: Tải lên ảnh scan / chỉnh vùng che / duyệt hoặc gỡ duyệt ảnh công khai"""
    if request.method != 'POST':
        return redirect('certificate_detail', pk=pk)
    if get_role(request.user) not in STAFF_ROLES or not request.user.has_perm('certificates.manage_diploma_image'):
        return HttpResponseForbidden("Tài khoản chưa được cấp quyền quản lý ảnh văn bằng.")
    cert = get_object_or_404(Certificate, pk=pk)
    action = request.POST.get('action')

    if action == 'upload':
        error = diploma_helper.save_scan(cert, request.FILES.get('diploma_file'), request.user)
        if error:
            messages.error(request, f"Không lưu được ảnh văn bằng: {error}")
            return redirect('certificate_detail', pk=pk)
        cert.save()
        _log_diploma(request, cert, 'upload')
        messages.success(request, "Đã lưu ảnh văn bằng gốc và tạo bản công khai. Hãy kiểm tra vùng che rồi bấm duyệt.")
    elif action == 'regions':
        if not cert.diploma_original:
            messages.error(request, "Chưa có ảnh scan để chỉnh vùng che.")
            return redirect('certificate_detail', pk=pk)
        try:
            cert.diploma_regions = diploma_helper.parse_regions(request.POST.get('regions', ''))
        except ValueError as e:
            messages.error(request, f"Vùng che không hợp lệ. {e}")
            return redirect('certificate_detail', pk=pk)
        diploma_helper.rebuild_public_scan(cert)
        cert.diploma_public_approved = False  # đổi vùng che -> phải kiểm tra & duyệt lại
        cert.save()
        _log_diploma(request, cert, 'regions')
        messages.success(request, "Đã cập nhật vùng che. Ảnh công khai chuyển về trạng thái chờ duyệt.")
    elif action in ('approve', 'unapprove'):
        if not cert.diploma_original or not cert.diploma_public:
            messages.error(request, "Chưa có ảnh scan / bản công khai để duyệt.")
            return redirect('certificate_detail', pk=pk)
        cert.diploma_public_approved = (action == 'approve')
        cert.save(update_fields=['diploma_public_approved'])
        if action == 'approve':
            _log_diploma(request, cert, 'approve_public')
            messages.success(request, "Đã duyệt: người tra cứu sẽ thấy ảnh văn bằng đã che thông tin.")
        else:
            messages.info(request, "Đã gỡ duyệt: trang tra cứu tạm thời không hiện ảnh văn bằng này.")
    return redirect('certificate_detail', pk=pk)