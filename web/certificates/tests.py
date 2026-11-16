from django.test import TestCase

# Create your tests here.

# ============================================================================
# Update: Kiểm thử tự động cho giai đoạn P0 (vá lỗ hổng) và P1
# Chạy:  docker compose exec web python manage.py test certificates
# Các hàm ghi Blockchain được giả lập (mock) để test KHÔNG gửi giao dịch thật lên mạng Besu.
# ============================================================================
from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings

from .models import Certificate, normalize_verify_code


def _make_cert(serial, status='ISSUED', **kw):
    """Update: Tạo văn bằng mẫu trực tiếp trong DB (không gọi Blockchain)"""
    data = dict(serial_number=serial, student_id='B21DCCN999', student_name='Nguyễn Văn An',
                date_of_birth=date(2003, 5, 15), major='Công nghệ thông tin', graduation_year=2026,
                classification='Xuất sắc', degree_type='Bằng Cử nhân', status=status,
                issue_date=date(2026, 11, 1), tx_hash='ab' * 32)
    data.update(kw)
    cert = Certificate(**data)
    cert.save()
    return cert


def _make_user(username, role):
    """Update: Tạo tài khoản và gán vai trò qua UserProfile (như gán trong Django Admin)"""
    user = User.objects.create_user(username=username, password='Test@12345')
    user.profile.role = role
    user.profile.save()
    return user


class PublicLookupTests(TestCase):
    """Update: Trang tra cứu / xác minh công khai (Cấp độ 1)"""

    def setUp(self):
        cache.clear()  # xoá bộ đếm giới hạn tần suất giữa các test
        self.cert = _make_cert('TEST-001')

    def test_verify_code_generated_and_random(self):
        self.assertEqual(len(self.cert.verify_code), 10)
        other = _make_cert('TEST-002')
        self.assertNotEqual(self.cert.verify_code, other.verify_code)
        self.assertNotIn('TEST', self.cert.verify_code)  # không suy ra từ số hiệu

    def test_normalize_code_accepts_dashes_and_lowercase(self):
        self.assertEqual(normalize_verify_code(' k7m2-9qxd 4t '), 'K7M29QXD4T')

    def test_lookup_by_verify_code_shows_minimal_data(self):
        r = self.client.get('/', {'q': self.cert.verify_code_display.lower()})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Văn bằng hợp lệ', html)
        self.assertIn('Nguyễn V*** An', html)        # họ tên đã che
        self.assertNotIn('Nguyễn Văn An', html)       # không có họ tên đầy đủ
        self.assertNotIn('B21DCCN999', html)          # không có mã sinh viên
        self.assertNotIn('15/05/2003', html)          # không có ngày sinh
        self.assertNotIn('2003-05-15', html)
        self.assertNotIn('Xuất sắc', html)            # không có xếp loại
        self.assertNotIn(self.cert.data_hash, html)   # không có dấu băm (chưa có muối, tránh dò ngược)

    def test_public_page_uses_plain_language(self):
        """Update: Trang công khai không dùng thuật ngữ kỹ thuật khó hiểu với doanh nghiệp"""
        r = self.client.get(f'/verify/{self.cert.verify_code_display}/')
        for term in ('SHA-256', 'Hash', 'Hyperledger', 'Besu', 'On-Chain'):
            self.assertNotContains(r, term)
        self.assertContains(r, 'Nội dung văn bằng còn nguyên vẹn')
        self.assertContains(r, 'giờ Việt Nam')

    def test_qr_route_verify(self):
        r = self.client.get(f'/verify/{self.cert.verify_code_display}/')
        self.assertContains(r, 'Văn bằng hợp lệ')

    def test_no_lookup_by_name_or_student_id(self):
        for q in ('Nguyễn', 'Nguyễn Văn An', 'B21DCCN999'):
            r = self.client.get('/', {'q': q})
            self.assertContains(r, 'Không tìm thấy văn bằng')

    def test_serial_lookup_disabled_by_default(self):
        r = self.client.get('/', {'q': 'TEST-001'})
        self.assertContains(r, 'Không tìm thấy văn bằng')

    @override_settings(ALLOW_LOOKUP_BY_SERIAL=True)
    def test_serial_lookup_when_enabled_hides_name(self):
        r = self.client.get('/', {'q': 'TEST-001'})
        self.assertContains(r, 'Văn bằng hợp lệ')
        self.assertContains(r, 'kết quả rút gọn')
        self.assertNotContains(r, 'Nguyễn V*** An')
        self.assertNotContains(r, 'Công nghệ thông tin')  # không hiện ngành ở chế độ rút gọn

    @override_settings(MASK_PUBLIC_NAME=False)
    def test_full_name_when_mask_disabled(self):
        r = self.client.get('/', {'q': self.cert.verify_code})
        self.assertContains(r, 'Nguyễn Văn An')

    def test_pending_certificate_not_public(self):
        pending = _make_cert('TEST-003', status='PENDING')
        r = self.client.get('/', {'q': pending.verify_code})
        self.assertContains(r, 'Không tìm thấy văn bằng')

    def test_revoked_hides_reason(self):
        revoked = _make_cert('TEST-004', status='REVOKED', revoke_reason='Lý do bí mật nội bộ')
        r = self.client.get('/', {'q': revoked.verify_code})
        self.assertContains(r, 'Văn bằng đã bị thu hồi')
        self.assertNotContains(r, 'Lý do bí mật nội bộ')

    def test_cancelled_and_replaced_status(self):
        new = _make_cert('TEST-006')
        cancelled = _make_cert('TEST-005', status='CANCELLED')
        replaced = _make_cert('TEST-007', status='REPLACED', replaced_by=new)
        self.assertContains(self.client.get('/', {'q': cancelled.verify_code}), 'Văn bằng đã bị hủy')
        r = self.client.get('/', {'q': replaced.verify_code})
        self.assertContains(r, 'Văn bằng đã được thay thế')
        self.assertContains(r, 'TEST-006')
        self.assertNotContains(r, new.verify_code_display)  # không lộ mã xác minh của văn bằng mới

    def test_tampered_data_fails_integrity(self):
        # Sửa trực tiếp DB (bỏ qua save()) để giả lập dữ liệu bị chỉnh sửa trái phép
        Certificate.objects.filter(pk=self.cert.pk).update(classification='Trung bình')
        r = self.client.get('/', {'q': self.cert.verify_code})
        self.assertContains(r, 'Chưa thể xác nhận văn bằng này')  # Update: câu thông báo mới, không dùng thuật ngữ
        self.assertNotContains(r, 'Văn bằng hợp lệ')

    @override_settings(LOOKUP_MISS_RATE=3)
    def test_rate_limit_on_wrong_codes(self):
        for _ in range(3):
            self.assertEqual(self.client.get('/', {'q': 'AAAA-AAAA-AA'}).status_code, 200)
        r = self.client.get('/', {'q': self.cert.verify_code})  # kể cả mã đúng cũng bị chặn tạm
        self.assertEqual(r.status_code, 429)


class AccessControlTests(TestCase):
    """Update: Phân quyền phôi in, dashboard và luồng thu hồi có loại kết thúc"""

    def setUp(self):
        cache.clear()
        self.cert = _make_cert('TEST-101')

    def test_print_view_requires_staff_login(self):
        r = self.client.get(f'/certificates/{self.cert.pk}/print/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_print_view_for_staff_shows_verify_code(self):
        _make_user('qlsv_t', 'qlsv')
        self.client.login(username='qlsv_t', password='Test@12345')
        r = self.client.get(f'/certificates/{self.cert.pk}/print/')
        self.assertContains(r, self.cert.verify_code_display)
        self.assertContains(r, f'/verify/{self.cert.verify_code_display}/')
        self.assertNotContains(r, 'Số vào sổ')

    def test_print_view_denied_for_unknown_role(self):
        User.objects.create_user(username='nguoila', password='Test@12345')
        self.client.login(username='nguoila', password='Test@12345')
        r = self.client.get(f'/certificates/{self.cert.pk}/print/')
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('/print/', r['Location'])

    def test_dashboard_unknown_role_sees_nothing(self):
        User.objects.create_user(username='nguoila2', password='Test@12345')
        self.client.login(username='nguoila2', password='Test@12345')
        r = self.client.get('/dashboard/')
        self.assertEqual(r.context['certificates'].count(), 0)

    @mock.patch('certificates.views.revoke_onchain', return_value=None)
    def test_admin_cancel_sets_cancelled(self, _mock):
        _make_user('admin_t', 'admin')
        self.client.login(username='admin_t', password='Test@12345')
        self.client.post(f'/certificates/{self.cert.pk}/revoke/', {'reason': 'Cấp sai', 'end_type': 'CANCELLED'})
        self.cert.refresh_from_db()
        self.assertEqual(self.cert.status, 'CANCELLED')

    @mock.patch('certificates.views.revoke_onchain', return_value=None)
    def test_replace_requires_existing_replacement(self, _mock):
        _make_user('admin_t2', 'admin')
        self.client.login(username='admin_t2', password='Test@12345')
        self.client.post(f'/certificates/{self.cert.pk}/revoke/',
                         {'reason': 'Cấp lại', 'end_type': 'REPLACED', 'replaced_serial': 'KHONG-CO'})
        self.cert.refresh_from_db()
        self.assertEqual(self.cert.status, 'ISSUED')  # không đổi vì số hiệu thay thế không tồn tại
        new = _make_cert('TEST-102')
        self.client.post(f'/certificates/{self.cert.pk}/revoke/',
                         {'reason': 'Cấp lại', 'end_type': 'REPLACED', 'replaced_serial': 'TEST-102'})
        self.cert.refresh_from_db()
        self.assertEqual(self.cert.status, 'REPLACED')
        self.assertEqual(self.cert.replaced_by, new)

    @mock.patch('certificates.views.revoke_onchain', return_value=None)
    def test_three_party_revoke_still_works(self, _mock):
        for name, role in (('q', 'qlsv'), ('d', 'daotao'), ('h', 'hieutruong')):
            _make_user(name, role)
            self.client.login(username=name, password='Test@12345')
            self.client.post(f'/certificates/{self.cert.pk}/revoke/', {'reason': 'Sai sót'})
            self.client.logout()
        self.cert.refresh_from_db()
        self.assertEqual(self.cert.status, 'REVOKED')  # mặc định như trước: thu hồi


# ============================================================================
# Update: Kiểm thử P2 (tài khoản sinh viên đăng nhập bằng CCCD) và P3 (liên kết chia sẻ có thời hạn)
# Trong test, Django tự dùng hộp thư giả (mail.outbox) nên không gửi email thật.
# ============================================================================
import io
import re
from datetime import timedelta

import openpyxl
from django.core import mail
from django.utils import timezone

from .models import ShareToken, VerificationLog, UserProfile
from .security_helper import hash_national_id
from .security_helper import encrypt_national_id, decrypt_national_id  # Update

CCCD = '001203000001'
CCCD_SPACED = '0012 0300 0001'


def _issued_cert_with_cccd(serial='SV-001', cccd=CCCD, email='an@example.com', **kw):
    """Update: Văn bằng đã phát hành, gắn CCCD (dạng băm) + email"""
    return _make_cert(serial, national_id_hash=hash_national_id(cccd), national_id_last4=cccd[-4:],
                      national_id_encrypted=encrypt_national_id(cccd),  # Update: CCCD mã hoá cho nút con mắt
                      student_email=email, rector_approved_at=timezone.now(), **kw)


def _activate_student(client, cert, password='MatKhau@2026'):
    """Update: Cán bộ gửi link kích hoạt → sinh viên mở link trong email và đặt mật khẩu"""
    staff = _make_user(f'qlsv_{cert.pk}', 'qlsv')
    client.force_login(staff)
    client.post(f'/certificates/{cert.pk}/student-account/', {'student_email': cert.student_email})
    client.logout()
    link = re.search(r'https?://[^\s]+/student/activate/[^\s]+/', mail.outbox[-1].body).group(0)
    path = link.split('://', 1)[1].split('/', 1)[1]
    client.post('/' + path, {'new_password1': password, 'new_password2': password})
    client.logout()
    return '/' + path


class StudentAccountTests(TestCase):
    """Update: Tài khoản sinh viên"""

    def setUp(self):
        cache.clear()

    @mock.patch('certificates.views.register_onchain', return_value=None)
    def test_create_stores_only_hash_of_cccd(self, _m):
        self.client.force_login(_make_user('qlsv_a', 'qlsv'))
        self.client.post('/certificates/create/', dict(
            serial_number='SV-100', student_id='B21', student_name='Lê Văn Tư', date_of_birth='2003-01-01',
            major='CNTT', graduation_year='2026', classification='Khá', national_id=CCCD, student_email='tu@example.com'))
        cert = Certificate.objects.get(serial_number='SV-100')
        self.assertEqual(cert.national_id_hash, hash_national_id(CCCD))
        self.assertEqual(cert.national_id_last4, '0001')
        for value in Certificate.objects.filter(pk=cert.pk).values().first().values():
            self.assertNotEqual(str(value), CCCD)  # không cột nào chứa số CCCD đầy đủ

    @mock.patch('certificates.views.register_onchain', return_value=None)
    def test_create_rejects_bad_cccd(self, _m):
        self.client.force_login(_make_user('qlsv_b', 'qlsv'))
        self.client.post('/certificates/create/', dict(
            serial_number='SV-101', student_id='B21', student_name='X', date_of_birth='2003-01-01',
            major='CNTT', graduation_year='2026', classification='Khá', national_id='12345'))
        self.assertFalse(Certificate.objects.filter(serial_number='SV-101').exists())

    @mock.patch('certificates.views.approve_onchain', return_value='0x' + 'cd' * 32)
    def test_rector_issue_creates_account_and_sends_link(self, _m):
        cert = _issued_cert_with_cccd(status='PENDING', student_affairs_approved=True, academic_affairs_approved=True)
        self.client.force_login(_make_user('ht', 'hieutruong'))
        self.client.post(f'/certificates/{cert.pk}/approve/')
        cert.refresh_from_db()
        self.assertEqual(cert.status, 'ISSUED')
        profile = UserProfile.objects.get(national_id_hash=cert.national_id_hash)
        self.assertEqual(profile.role, 'student')
        self.assertNotIn(CCCD, profile.user.username)          # tên tài khoản nội bộ không chứa CCCD
        self.assertFalse(profile.user.has_usable_password())     # chưa đặt mật khẩu thì chưa đăng nhập được
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/student/activate/', mail.outbox[0].body)

    def test_activate_then_login_with_cccd(self):
        cert = _issued_cert_with_cccd()
        path = _activate_student(self.client, cert)
        r = self.client.post('/login/', {'username': CCCD_SPACED, 'password': 'MatKhau@2026'})
        self.assertRedirects(r, '/me/', fetch_redirect_response=False)
        # Link kích hoạt chỉ dùng được 1 lần
        self.client.logout()
        self.assertContains(self.client.get(path), 'Liên kết không còn hiệu lực')

    def test_generic_login_error_and_lockout(self):
        cert = _issued_cert_with_cccd()
        _activate_student(self.client, cert)
        r1 = self.client.post('/login/', {'username': CCCD, 'password': 'sai'})
        r2 = self.client.post('/login/', {'username': '999999999999', 'password': 'sai'})
        self.assertContains(r1, 'Tên đăng nhập hoặc mật khẩu không đúng.')
        self.assertContains(r2, 'Tên đăng nhập hoặc mật khẩu không đúng.')  # không phân biệt CCCD có/không tồn tại
        with self.settings(LOGIN_FAIL_LIMIT=2):
            self.client.post('/login/', {'username': CCCD, 'password': 'sai'})
            r = self.client.post('/login/', {'username': CCCD, 'password': 'MatKhau@2026'})
            self.assertContains(r, 'sai quá nhiều lần')

    def test_open_redirect_blocked(self):
        cert = _issued_cert_with_cccd()
        _activate_student(self.client, cert)
        r = self.client.post('/login/?next=https://evil.example.com/', {'username': CCCD, 'password': 'MatKhau@2026'})
        self.assertEqual(r['Location'], '/me/')

    def test_portal_shows_only_own_certificates(self):
        mine = _issued_cert_with_cccd('SV-200')
        other = _issued_cert_with_cccd('SV-201', cccd='079203009999', email='b@example.com', student_name='Người Khác')
        pending = _issued_cert_with_cccd('SV-202', status='PENDING')
        _activate_student(self.client, mine)
        self.client.login(username=UserProfile.objects.get(national_id_hash=mine.national_id_hash).user.username,
                          password='MatKhau@2026')
        r = self.client.get('/me/')
        self.assertContains(r, 'SV-200')
        self.assertContains(r, '15/05/2003')            # sinh viên xem được ngày sinh của chính mình
        self.assertNotContains(r, 'SV-201')             # không thấy văn bằng người khác
        self.assertNotContains(r, 'SV-202')             # hồ sơ chưa phát hành không hiện chi tiết
        self.assertContains(r, '1 hồ sơ văn bằng đang được nhà trường xét duyệt')
        # In phôi: được văn bằng của mình, không được của người khác; vào dashboard -> chuyển về /me/
        self.assertEqual(self.client.get(f'/certificates/{mine.pk}/print/').status_code, 200)
        self.assertEqual(self.client.get(f'/certificates/{other.pk}/print/').status_code, 302)
        self.assertRedirects(self.client.get('/dashboard/'), '/me/', fetch_redirect_response=False)

    def test_forgot_sends_mail_only_for_known_cccd_with_same_message(self):
        cert = _issued_cert_with_cccd()
        _activate_student(self.client, cert)
        mail.outbox.clear()
        r1 = self.client.post('/student/forgot/', {'national_id': CCCD}, follow=True)
        r2 = self.client.post('/student/forgot/', {'national_id': '999999999999'}, follow=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(r1, 'Nếu số CCCD đã được nhà trường đăng ký')
        self.assertContains(r2, 'Nếu số CCCD đã được nhà trường đăng ký')

    @mock.patch('certificates.views.register_onchain', return_value=None)
    def test_excel_import_keeps_leading_zero_of_cccd(self, _m):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['h'] * 11)
        ws.append(['SV-300', 'B21', 'Đỗ Văn Ba', '2003-01-01', 'CNTT', 2026, 'Khá', 'Bằng Cử nhân', '',
                   1203000001, 'ba@example.com'])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'ds.xlsx'
        self.client.force_login(_make_user('can_bo_qlsv_x', 'qlsv'))  # Update: nay kiểm tra theo vai trò, không theo username
        self.client.post('/excel/import/', {'excel_file': buf})
        cert = Certificate.objects.get(serial_number='SV-300')
        self.assertEqual(cert.national_id_hash, hash_national_id('001203000001'))


class ShareLinkTests(TestCase):
    """Update: Liên kết chia sẻ có thời hạn"""

    def setUp(self):
        cache.clear()
        self.cert = _issued_cert_with_cccd('SV-400')
        _activate_student(self.client, self.cert)
        self.student = UserProfile.objects.get(national_id_hash=self.cert.national_id_hash).user
        self.client.login(username=self.student.username, password='MatKhau@2026')

    def _create(self, **extra):
        data = {'recipient': 'Công ty ABC', 'days': '7', 'show_full_name': '1', 'show_dob': '1'}
        data.update(extra)
        self.client.post(f'/me/share/{self.cert.pk}/create/', data)
        url = self.client.session['new_share']['url']
        return '/' + url.split('://', 1)[1].split('/', 1)[1]

    def test_share_shows_only_allowed_fields_and_logs(self):
        path = self._create()
        self.client.logout()
        r = self.client.get(path)
        self.assertContains(r, 'Văn bằng hợp lệ')
        self.assertContains(r, 'Nguyễn Văn An')        # cho phép họ tên đầy đủ
        self.assertContains(r, '15/05/2003')           # cho phép ngày sinh
        self.assertNotContains(r, 'B21DCCN999')        # KHÔNG cho phép mã sinh viên
        self.assertNotContains(r, 'Xuất sắc')          # KHÔNG cho phép xếp loại
        self.assertContains(r, 'Công ty ABC')
        share = ShareToken.objects.get()
        self.assertEqual(share.view_count, 1)
        self.assertTrue(VerificationLog.objects.filter(share=share, outcome='shown').exists())
        self.assertNotIn(path.split('/')[-2], share.token_hash)  # DB không lưu mã gốc

    def test_share_link_shown_only_once(self):
        self._create()
        self.assertContains(self.client.get('/me/'), 'chỉ hiện một lần')     # lần đầu hiện liên kết
        self.assertNotContains(self.client.get('/me/'), 'chỉ hiện một lần')  # lần sau không hiện nữa

    def test_max_views_expired_revoked(self):
        path = self._create(max_views='1')
        self.client.logout()
        self.assertContains(self.client.get(path), 'Văn bằng hợp lệ')
        r = self.client.get(path)
        self.assertContains(r, 'Liên kết chia sẻ không còn hiệu lực')
        self.assertNotContains(r, '15/05/2003')
        # hết hạn
        self.client.login(username=self.student.username, password='MatKhau@2026')
        path2 = self._create()
        ShareToken.objects.filter(max_views__isnull=True).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertContains(self.client.get(path2), 'không còn hiệu lực')
        # thu hồi
        path3 = self._create()
        s3 = ShareToken.objects.order_by('-created_at').first()
        self.client.post(f'/me/share/{s3.pk}/revoke/')
        self.assertContains(self.client.get(path3), 'không còn hiệu lực')

    def test_cannot_share_or_revoke_others(self):
        other = _issued_cert_with_cccd('SV-401', cccd='079203009999', email='b@example.com')
        self.client.post(f'/me/share/{other.pk}/create/', {'days': '7'})
        self.assertFalse(ShareToken.objects.filter(certificate=other).exists())
        foreign = ShareToken.objects.create(certificate=other, token_hash='x' * 64,
                                            expires_at=timezone.now() + timedelta(days=1))
        self.client.post(f'/me/share/{foreign.pk}/revoke/')
        foreign.refresh_from_db()
        self.assertIsNone(foreign.revoked_at)

    def test_wrong_share_token(self):
        self.client.logout()
        self.assertContains(self.client.get('/verify/s/khong-dung/'), 'Liên kết chia sẻ không đúng')


# ============================================================================
# Update: Kiểm thử P4: dấu băm có muối, đối chiếu trực tiếp với chuỗi, chữ ký điện tử của nhà trường
# Toàn bộ test trong file dùng "chuỗi giả" (_fake_chain) để không phụ thuộc mạng Besu đang chạy;
# chuỗi giả trả về đúng dấu băm và trạng thái đang có trong DB (tức là trường hợp "khớp").
# ============================================================================
import hashlib
import unicodedata

from eth_account import Account

from .blockchain import ROLE_CONFIG

_chain_patcher = None


def _fake_chain(serial):
    """Update: Mô phỏng getStatus(): chuỗi lưu đúng dấu băm và trạng thái như DB"""
    c = Certificate.objects.filter(serial_number=serial).first()
    if c is None:
        return {'ok': True, 'found': False}
    status = 'Issued' if c.status == 'ISSUED' else ('Revoked' if c.status in Certificate.END_STATUSES else 'Pending')
    return {'ok': True, 'found': True, 'data_hash': c.data_hash, 'status': status,
            'issued_at': 1763000000, 'revoked_at': 0, 'rector_address': ROLE_CONFIG['hieutruong']['address']}


def setUpModule():
    """Update: Bật chuỗi giả cho mọi test trong file (unittest gọi tự động trước khi chạy module)"""
    global _chain_patcher
    _chain_patcher = mock.patch('certificates.views.get_onchain_status', side_effect=_fake_chain)
    _chain_patcher.start()


def tearDownModule():
    _chain_patcher.stop()


class SaltedHashTests(TestCase):
    """Update: Dấu băm phiên bản 2 có muối"""

    def test_new_certificate_uses_salted_v2(self):
        a = _make_cert('H-001')
        b = _make_cert('H-002')
        self.assertEqual(a.hash_version, 2)
        self.assertEqual(len(a.hash_salt), 32)
        b.serial_number = 'H-001'  # cùng toàn bộ dữ liệu như a ...
        self.assertNotEqual(a.calculate_data_hash(), b._calculate_data_hash_v2())  # ... nhưng khác muối -> khác dấu băm

    def test_legacy_v1_still_matches(self):
        c = _make_cert('H-003')
        Certificate.objects.filter(pk=c.pk).update(hash_version=1, data_hash=None)
        c.refresh_from_db()
        c.data_hash = c.calculate_data_hash()  # công thức cũ không muối
        raw = f"{c.serial_number}|{c.student_id}|{c.student_name}|{c.date_of_birth}|{c.major}|{c.graduation_year}|{c.classification}"
        self.assertEqual(c.data_hash, '0x' + hashlib.sha256(raw.encode('utf-8')).hexdigest())

    def test_unicode_normalization(self):
        c = _make_cert('H-004')
        h1 = c.calculate_data_hash()
        c.student_name = unicodedata.normalize('NFD', '  Nguyễn   Văn An ')  # gõ kiểu tổ hợp + thừa khoảng trắng
        self.assertEqual(c.calculate_data_hash(), h1)


class ChainAndSignatureTests(TestCase):
    """Update: Đối chiếu chuỗi (các tình huống 5, 6, 7 trong yêu cầu) và chữ ký điện tử"""

    def setUp(self):
        cache.clear()
        self.acct = Account.create()  # khoá Hiệu trưởng giả dùng riêng cho test
        self.key_patch = mock.patch.dict(ROLE_CONFIG['hieutruong'],
                                         {'private_key': self.acct.key.hex(), 'address': self.acct.address})
        self.key_patch.start()

    def tearDown(self):
        self.key_patch.stop()

    @mock.patch('certificates.views.approve_onchain', return_value='0x' + 'ef' * 32)
    def _issue(self, serial, _m):
        cert = _make_cert(serial, status='PENDING', student_affairs_approved=True, academic_affairs_approved=True,
                          issue_date=None, tx_hash=None)
        self.client.force_login(_make_user(f'ht_{serial}', 'hieutruong'))
        self.client.post(f'/certificates/{cert.pk}/approve/')
        self.client.logout()
        cert.refresh_from_db()
        return cert

    def test_rector_signs_and_signature_verifies(self):
        cert = self._issue('S-001')
        self.assertTrue(cert.issuer_signature)
        r = self.client.get('/', {'q': cert.verify_code})
        self.assertContains(r, 'Văn bằng hợp lệ')
        self.assertContains(r, 'Có chữ ký điện tử hợp lệ của Hiệu trưởng')
        self.assertContains(r, 'Khớp với hệ thống lưu trữ chống chỉnh sửa')

    def test_signature_by_other_key_is_rejected(self):
        cert = self._issue('S-002')
        other = Account.create()
        with mock.patch.dict(ROLE_CONFIG['hieutruong'], {'private_key': other.key.hex()}):
            from .blockchain import sign_certificate
            forged, _ = sign_certificate(cert.serial_number, cert.data_hash, cert.issue_date.isoformat())
        Certificate.objects.filter(pk=cert.pk).update(issuer_signature=forged)
        r = self.client.get('/', {'q': cert.verify_code})
        self.assertContains(r, 'Chưa thể xác nhận văn bằng này')
        self.assertContains(r, 'Chữ ký điện tử không hợp lệ')

    def test_changed_issue_date_breaks_signature(self):
        cert = self._issue('S-003')
        Certificate.objects.filter(pk=cert.pk).update(issue_date=date(2020, 1, 1))
        self.assertContains(self.client.get('/', {'q': cert.verify_code}), 'Chữ ký điện tử không hợp lệ')

    def test_chain_unavailable_does_not_mark_invalid(self):
        cert = _make_cert('C-001')
        with mock.patch('certificates.views.get_onchain_status', return_value={'ok': False}):
            r = self.client.get('/', {'q': cert.verify_code})
        self.assertContains(r, 'Văn bằng hợp lệ')
        self.assertContains(r, 'Tạm thời chưa đối chiếu được')
        self.assertNotContains(r, 'Chưa thể xác nhận văn bằng này')

    def test_chain_hash_mismatch_fails(self):
        cert = _make_cert('C-002')
        fake = {'ok': True, 'found': True, 'data_hash': '0x' + '00' * 32, 'status': 'Issued',
                'issued_at': 0, 'revoked_at': 0, 'rector_address': None}
        with mock.patch('certificates.views.get_onchain_status', return_value=fake):
            r = self.client.get('/', {'q': cert.verify_code})
        self.assertContains(r, 'Chưa thể xác nhận văn bằng này')
        self.assertContains(r, 'không khớp với bản ghi gốc')

    def test_chain_says_revoked_but_db_issued_fails(self):
        cert = _make_cert('C-003')
        fake = {'ok': True, 'found': True, 'data_hash': cert.data_hash, 'status': 'Revoked',
                'issued_at': 0, 'revoked_at': 0, 'rector_address': None}
        with mock.patch('certificates.views.get_onchain_status', return_value=fake):
            r = self.client.get('/', {'q': cert.verify_code})
        self.assertContains(r, 'Chưa thể xác nhận văn bằng này')
        self.assertNotContains(r, 'Văn bằng hợp lệ')

    def test_chain_missing_is_warning_only(self):
        cert = _make_cert('C-004')
        with mock.patch('certificates.views.get_onchain_status', return_value={'ok': True, 'found': False}):
            r = self.client.get('/', {'q': cert.verify_code})
        self.assertContains(r, 'Văn bằng hợp lệ')
        self.assertContains(r, 'Chưa tìm thấy bản ghi')

    @mock.patch('certificates.views.revoke_onchain', return_value=None)
    def test_revoke_reason_not_written_in_clear_onchain(self, m_revoke):
        cert = _make_cert('R-001')
        self.client.force_login(_make_user('admin_r', 'admin'))
        self.client.post(f'/certificates/{cert.pk}/revoke/', {'reason': 'Sinh viên Nguyễn Văn An gian lận'})
        sent_reasons = [call.args[1] for call in m_revoke.call_args_list]
        self.assertEqual(len(sent_reasons), 3)
        for sent in sent_reasons:
            self.assertTrue(sent.startswith('REVOKED#'))
            self.assertNotIn('Nguyễn', sent)


class NationalIdRevealTests(TestCase):
    """Update: CCCD mã hoá hai chiều + nút con mắt trên trang sinh viên"""

    def setUp(self):
        cache.clear()

    def test_encrypt_roundtrip_and_tamper(self):
        token = encrypt_national_id('0012 0300 0001')
        self.assertTrue(token.startswith('v1:'))
        self.assertNotIn(CCCD, token)
        self.assertEqual(decrypt_national_id(token), CCCD)
        self.assertNotEqual(encrypt_national_id(CCCD), token)  # mỗi lần mã hoá ra bản mã khác (nonce ngẫu nhiên)
        tampered = token[:-4] + ('AAAA' if not token.endswith('AAAA') else 'BBBB')
        self.assertEqual(decrypt_national_id(tampered), '')    # bản mã bị sửa -> không giải mã
        with self.settings(CCCD_ENCRYPTION_KEY='khoa-khac'):
            self.assertEqual(decrypt_national_id(token), '')   # sai khoá -> không giải mã

    def test_student_sees_masked_with_eye_toggle_and_no_cache(self):
        cert = _issued_cert_with_cccd('E-001')
        _activate_student(self.client, cert)
        self.client.post('/login/', {'username': CCCD, 'password': 'MatKhau@2026'})
        r = self.client.get('/me/')
        html = r.content.decode()
        self.assertIn('•••• •••• 0001', html)                 # mặc định hiện bản che
        self.assertIn(f'data-full="{CCCD}"', html)            # số đầy đủ chỉ nằm sẵn cho nút con mắt
        self.assertIn('aria-label="Hiện số CCCD"', html)      # có nút con mắt
        self.assertIn('no-store', r['Cache-Control'])         # không cho trình duyệt lưu trang có CCCD

    def test_full_cccd_never_on_staff_or_public_pages(self):
        cert = _issued_cert_with_cccd('E-002')
        self.client.force_login(_make_user('qlsv_e', 'qlsv'))
        self.assertNotContains(self.client.get('/dashboard/'), CCCD)
        self.client.logout()
        self.assertNotContains(self.client.get(f'/verify/{cert.verify_code_display}/'), CCCD)

    def test_old_record_without_encrypted_cccd_shows_info_icon(self):
        cert = _issued_cert_with_cccd('E-003')
        Certificate.objects.filter(pk=cert.pk).update(national_id_encrypted=None)
        _activate_student(self.client, cert)
        self.client.post('/login/', {'username': CCCD, 'password': 'MatKhau@2026'})
        r = self.client.get('/me/')
        self.assertContains(r, '•••• •••• 0001')
        self.assertNotContains(r, 'aria-label="Hiện số CCCD"')  # không có nút con mắt khi không có số đầy đủ
        self.assertContains(r, 'chưa lưu số đầy đủ')


# ============================================================================
# Update: Kiểm thử P6: ảnh văn bằng theo quyền (đánh số theo mục VII của yêu cầu)
# Ảnh lưu vào thư mục tạm riêng cho test (không đụng private_media thật).
# ============================================================================
import shutil
import tempfile

from django.contrib.auth.models import Permission
from PIL import Image as PILImage

from . import diploma_helper
from .models import DiplomaAccessLog

_TMP_MEDIA = tempfile.mkdtemp(prefix='diploma-test-')


def _png_upload(size=(1400, 990), name='scan.png', dob_color=(220, 0, 0)):
    """Update: Ảnh 'scan' giả: nền trắng, ô màu đỏ đúng chỗ vùng che ngày sinh mặc định"""
    from django.core.files.uploadedfile import SimpleUploadedFile
    img = PILImage.new('RGB', size, 'white')
    w, h = size
    img.paste(dob_color, (int(w * 0.40), int(h * 0.61), int(w * 0.50), int(h * 0.625)))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def _png(resp):
    return PILImage.open(io.BytesIO(b''.join(resp.streaming_content) if resp.streaming else resp.content))


@override_settings(PRIVATE_MEDIA_ROOT=_TMP_MEDIA)
class DiplomaImageTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.cert = _issued_cert_with_cccd('D-001')

    def _staff(self, username, role, perms=()):
        user = _make_user(username, role)
        for codename in perms:
            user.user_permissions.add(Permission.objects.get(codename=codename))
        self.client.force_login(user)
        return user

    def _student_login(self, cert):
        _activate_student(self.client, cert)
        self.client.post('/login/', {'username': CCCD, 'password': 'MatKhau@2026'})

    # 1. Sinh viên xem văn bằng của chính mình: ảnh đầy đủ
    def test_01_student_sees_own_full_image(self):
        self._student_login(self.cert)
        r = self.client.get(f'/me/diploma/{self.cert.pk}.png')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'image/png')
        self.assertIn('no-store', r['Cache-Control'])
        self.assertContains(self.client.get('/me/'), f'/me/diploma/{self.cert.pk}.png')
        r = self.client.get(f'/me/diploma/{self.cert.pk}.png?download=1')
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertTrue(DiplomaAccessLog.objects.filter(certificate=self.cert, action='download_owner').exists())

    # 2. Sinh viên truy cập văn bằng của người khác: từ chối
    def test_02_student_cannot_see_others(self):
        other = _issued_cert_with_cccd('D-002', cccd='079203009999', email='b@example.com')
        self._student_login(self.cert)
        self.assertEqual(self.client.get(f'/me/diploma/{other.pk}.png').status_code, 403)
        self.assertEqual(self.client.get(f'/certificates/{other.pk}/diploma/original.png').status_code, 403)

    # 3 + 4. Người ngoài: trang và ảnh công khai đều là bản đã che (ảnh DEMO dựng KHÔNG vẽ ngày sinh / xếp loại)
    def test_03_04_public_gets_redacted_demo(self):
        r = self.client.get(f'/verify/{self.cert.verify_code_display}/')
        self.assertContains(r, f'/verify/{self.cert.verify_code_display}/diploma.png')
        self.assertNotContains(r, '/me/diploma/')
        self.assertNotContains(r, '/diploma/original.png')
        r = self.client.get(f'/verify/{self.cert.verify_code_display}/diploma.png')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'image/png')
        _img, drawn = diploma_helper.render_demo(self.cert, reveal=set(), masked_name=self.cert.masked_name)
        self.assertNotIn('dob', drawn)
        self.assertNotIn('classification', drawn)
        self.assertEqual(drawn['name'], 'Nguyễn V*** An')

    # 4. Ảnh scan thật: bản công khai bị TÔ KÍN trên điểm ảnh, ảnh gốc giữ nguyên
    def test_04_public_scan_pixels_are_redacted(self):
        self._staff('qlsv_d', 'qlsv', perms=('manage_diploma_image', 'view_original_diploma'))
        self.client.post(f'/certificates/{self.cert.pk}/diploma/manage/', {'action': 'upload', 'diploma_file': _png_upload()})
        self.client.post(f'/certificates/{self.cert.pk}/diploma/manage/', {'action': 'approve'})
        self.client.logout()
        img = _png(self.client.get(f'/verify/{self.cert.verify_code_display}/diploma.png'))
        probe = (int(img.width * 0.45), int(img.height * 0.615))
        self.assertEqual(img.convert('RGB').getpixel(probe), diploma_helper.REDACT)   # ô đỏ (ngày sinh) đã bị tô kín
        self.cert.refresh_from_db()
        original = diploma_helper.load_private_image(self.cert.diploma_original)
        self.assertEqual(original.getpixel(probe), (220, 0, 0))                          # ảnh gốc không bị sửa
        self.assertNotEqual(self.cert.diploma_original, self.cert.diploma_public)        # 2 file riêng biệt

    # 5. Người ngoài thử URL ảnh gốc: bị từ chối; không có URL tĩnh tới file
    def test_05_anonymous_original_denied(self):
        r = self.client.get(f'/certificates/{self.cert.pk}/diploma/original.png')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])
        self.assertEqual(self.client.get(f'/me/diploma/{self.cert.pk}.png').status_code, 302)
        self.assertEqual(self.client.get('/private_media/diplomas/x_original.png').status_code, 404)

    # 6. Cán bộ có quyền: xem ảnh gốc, có ghi nhật ký
    def test_06_staff_with_permission_sees_original(self):
        self._staff('qlsv_e', 'qlsv', perms=('view_original_diploma',))
        r = self.client.get(f'/certificates/{self.cert.pk}/diploma/original.png')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(DiplomaAccessLog.objects.filter(certificate=self.cert, action='view_original').exists())
        self.assertContains(self.client.get(f'/certificates/{self.cert.pk}/detail/'), 'Ảnh văn bằng gốc')

    # 7. Cán bộ KHÔNG có quyền: không xem được ảnh gốc, không quản lý được ảnh; lượt bị từ chối được ghi lại
    def test_07_staff_without_permission_denied(self):
        self._staff('daotao_x', 'daotao')
        self.assertEqual(self.client.get(f'/certificates/{self.cert.pk}/diploma/original.png').status_code, 403)
        self.assertTrue(DiplomaAccessLog.objects.filter(certificate=self.cert, action='denied').exists())
        r = self.client.post(f'/certificates/{self.cert.pk}/diploma/manage/', {'action': 'upload', 'diploma_file': _png_upload()})
        self.assertEqual(r.status_code, 403)
        page = self.client.get(f'/certificates/{self.cert.pk}/detail/')
        self.assertContains(page, 'Không có quyền xem ảnh gốc')
        self.assertNotContains(page, '/diploma/original.png')

    # 8. Ảnh scan chưa duyệt: công khai chưa có ảnh (trạng thái phù hợp), endpoint 404
    def test_08_unapproved_scan_not_public(self):
        self._staff('qlsv_f', 'qlsv', perms=('manage_diploma_image',))
        self.client.post(f'/certificates/{self.cert.pk}/diploma/manage/', {'action': 'upload', 'diploma_file': _png_upload()})
        self.client.logout()
        self.assertEqual(self.client.get(f'/verify/{self.cert.verify_code_display}/diploma.png').status_code, 404)
        self.assertContains(self.client.get(f'/verify/{self.cert.verify_code_display}/'),
                            'Nhà trường chưa phát hành ảnh văn bằng điện tử')

    # 9. Ảnh sai định dạng / lỗi / quá nhỏ: báo rõ, không lưu gì
    def test_09_invalid_upload_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self._staff('qlsv_g', 'qlsv', perms=('manage_diploma_image',))
        for upload in (SimpleUploadedFile('fake.png', b'day khong phai anh', content_type='image/png'),
                       _png_upload(size=(300, 200), name='nho.png')):
            r = self.client.post(f'/certificates/{self.cert.pk}/diploma/manage/',
                                 {'action': 'upload', 'diploma_file': upload}, follow=True)
            self.assertContains(r, 'Không lưu được ảnh văn bằng')
        self.cert.refresh_from_db()
        self.assertEqual(self.cert.diploma_original, '')

    # 11. Nội dung trên ảnh khớp dữ liệu văn bằng trong CSDL
    def test_11_image_content_matches_database(self):
        _img, drawn = diploma_helper.render_demo(self.cert, reveal={'name', 'dob', 'classification'})
        self.assertEqual(drawn['name'], self.cert.student_name)
        self.assertEqual(drawn['dob'], self.cert.date_of_birth.strftime('%d/%m/%Y'))
        self.assertEqual(drawn['classification'], self.cert.classification)
        self.assertEqual(drawn['serial'], self.cert.serial_number)
        self.assertEqual(drawn['major'], self.cert.major)
        self.assertEqual(drawn['issue_date'], self.cert.issue_date.isoformat())

    # 12. Liên kết chia sẻ: ảnh mở đúng trường được phép; liên kết hết hiệu lực -> không có ảnh
    def test_12_share_image_follows_permissions(self):
        self._student_login(self.cert)
        self.client.post(f'/me/share/{self.cert.pk}/create/', {'days': '7', 'show_dob': '1'})
        token = self.client.session['new_share']['url'].rstrip('/').split('/')[-1]
        self.client.logout()
        self.assertEqual(self.client.get(f'/verify/s/{token}/diploma.png').status_code, 200)
        ShareToken.objects.update(revoked_at=timezone.now())
        self.assertEqual(self.client.get(f'/verify/s/{token}/diploma.png').status_code, 404)

    def test_revoked_certificate_image_is_stamped(self):
        Certificate.objects.filter(pk=self.cert.pk).update(status='REVOKED')
        self.cert.refresh_from_db()
        clean, _ = diploma_helper.render_demo(self.cert, reveal=set())
        stamped = diploma_helper.stamp_status(clean, self.cert)
        self.assertNotEqual(list(clean.getdata())[::5000], list(stamped.getdata())[::5000])

    def test_demo_seal_toggle(self):
        """Update: Bật / tắt DIPLOMA_DEMO_SEAL: dấu minh hoạ hoặc khung chờ"""
        with self.settings(DIPLOMA_DEMO_SEAL=True):
            _img, drawn = diploma_helper.render_demo(self.cert, reveal=set())
            self.assertEqual(drawn['seal'], 'demo')
        with self.settings(DIPLOMA_DEMO_SEAL=False):
            _img, drawn = diploma_helper.render_demo(self.cert, reveal=set())
            self.assertEqual(drawn['seal'], 'placeholder')

    def test_institution_branding_everywhere(self):
        for url in ('/', '/login/', f'/verify/{self.cert.verify_code_display}/'):
            r = self.client.get(url)
            self.assertContains(r, 'Trường Đại học Kỹ thuật – Công nghệ Cần Thơ')
            self.assertContains(r, 'ctut-logo.png')
            self.assertNotContains(r, 'CÔNG NGHỆ & ĐÀO TẠO')


# ============================================================================
# Update: Kiểm tra trạng thái hồ sơ ở backend (duyệt / trả / sửa chỉ đúng bước, không áp dụng cho văn bằng đã cấp hay đã thu hồi)
# ============================================================================
from .models import ApprovalLog


@mock.patch('certificates.views.register_onchain', return_value=None)
@mock.patch('certificates.views.approve_onchain', return_value=None)
class StateGuardTests(TestCase):
    def setUp(self):
        self.users = {r: _make_user(f'sg_{r}', r) for r in ('qlsv', 'daotao', 'hieutruong', 'admin')}

    def _post(self, role, url, data=None):
        self.client.force_login(self.users[role])
        resp = self.client.post(url, data or {})
        self.client.logout()
        return resp

    def _edit_data(self, cert, name):
        return {'student_id': cert.student_id, 'student_name': name, 'date_of_birth': cert.date_of_birth.isoformat(),
                'major': cert.major, 'graduation_year': cert.graduation_year, 'classification': cert.classification,
                'degree_type': cert.degree_type}

    def test_1_cannot_edit_issued_certificate(self, *_m):
        cert = _make_cert('SG-1', status='ISSUED', student_affairs_approved=True, academic_affairs_approved=True, rector_approved=True)
        h0 = cert.data_hash
        self._post('qlsv', f'/certificates/{cert.pk}/edit/', self._edit_data(cert, 'Tên Đã Sửa'))
        cert.refresh_from_db()
        self.assertEqual(cert.status, 'ISSUED')
        self.assertEqual(cert.student_name, 'Nguyễn Văn An')
        self.assertEqual(cert.data_hash, h0)

    def test_2_cannot_reject_issued_certificate(self, *_m):
        cert = _make_cert('SG-2', status='ISSUED', student_affairs_approved=True, academic_affairs_approved=True, rector_approved=True)
        for role in ('qlsv', 'daotao', 'hieutruong', 'admin'):
            self._post(role, f'/certificates/{cert.pk}/reject/', {'reason': 'x'})
        cert.refresh_from_db()
        self.assertEqual(cert.status, 'ISSUED')
        self.assertFalse(cert.is_rejected)
        self.assertTrue(cert.student_affairs_approved and cert.academic_affairs_approved and cert.rector_approved)

    def test_3_rector_cannot_resign_issued_certificate(self, *_m):
        cert = _make_cert('SG-3', status='ISSUED', student_affairs_approved=True, academic_affairs_approved=True, rector_approved=True)
        logs = ApprovalLog.objects.filter(certificate=cert).count()
        self._post('hieutruong', f'/certificates/{cert.pk}/approve/')
        cert.refresh_from_db()
        self.assertEqual(ApprovalLog.objects.filter(certificate=cert).count(), logs)
        self.assertIsNone(cert.signed_at)

    def test_4_cannot_approve_revoked_certificate(self, *_m):
        cert = _make_cert('SG-4', status='REVOKED', student_affairs_approved=True, academic_affairs_approved=True, rector_approved=True)
        for role in ('qlsv', 'daotao', 'hieutruong', 'admin'):
            self._post(role, f'/certificates/{cert.pk}/approve/')
        cert.refresh_from_db()
        self.assertEqual(cert.status, 'REVOKED')
        self.assertEqual(ApprovalLog.objects.filter(certificate=cert).count(), 0)

    def test_5_qlsv_cannot_reject_record_at_rector_step(self, *_m):
        cert = _make_cert('SG-5', status='PENDING', student_affairs_approved=True, academic_affairs_approved=True)
        self._post('qlsv', f'/certificates/{cert.pk}/reject/', {'reason': 'x'})
        self._post('daotao', f'/certificates/{cert.pk}/reject/', {'reason': 'x'})
        cert.refresh_from_db()
        self.assertTrue(cert.student_affairs_approved and cert.academic_affairs_approved)
        self.assertFalse(cert.is_rejected)

    def test_no_double_approval_at_same_step(self, *_m):
        cert = _make_cert('SG-6', status='PENDING', student_affairs_approved=True)
        self._post('qlsv', f'/certificates/{cert.pk}/approve/')
        cert.refresh_from_db()
        self.assertEqual(ApprovalLog.objects.filter(certificate=cert).count(), 0)
        self.assertFalse(cert.academic_affairs_approved)

    def test_normal_flow_still_works(self, *_m):
        cert = _make_cert('SG-7', status='PENDING', tx_hash=None, issue_date=None)
        self._post('qlsv', f'/certificates/{cert.pk}/approve/')
        self._post('daotao', f'/certificates/{cert.pk}/reject/', {'reason': 'Sai ngành'})
        cert.refresh_from_db()
        self.assertTrue(cert.is_rejected and not cert.student_affairs_approved)
        self._post('qlsv', f'/certificates/{cert.pk}/edit/', self._edit_data(cert, 'Nguyễn Văn An'))
        self._post('qlsv', f'/certificates/{cert.pk}/approve/')
        self._post('daotao', f'/certificates/{cert.pk}/approve/')
        self._post('hieutruong', f'/certificates/{cert.pk}/reject/', {'reason': 'Xem lại xếp loại'})
        cert.refresh_from_db()
        self.assertTrue(cert.is_rejected and cert.rejected_by == 'hieutruong' and cert.student_affairs_approved)
        self._post('daotao', f'/certificates/{cert.pk}/edit/', self._edit_data(cert, 'Nguyễn Văn An'))
        self._post('daotao', f'/certificates/{cert.pk}/approve/')
        self._post('hieutruong', f'/certificates/{cert.pk}/approve/')
        cert.refresh_from_db()
        self.assertEqual(cert.status, 'ISSUED')
        self.assertFalse(cert.is_rejected)


@mock.patch('certificates.views.revoke_onchain', return_value=None)
class RevokeConfirmationTests(TestCase):
    """Update: thu hồi cần đủ 3 phòng; mỗi phòng xác nhận một lần; giao diện hiện tiến độ"""
    def setUp(self):
        self.users = {r: _make_user(f'rv_{r}', r) for r in ('qlsv', 'daotao', 'hieutruong')}
        self.cert = _make_cert('RV-1', status='ISSUED', student_affairs_approved=True, academic_affairs_approved=True, rector_approved=True)

    def _revoke(self, role):
        self.client.force_login(self.users[role])
        self.client.post(f'/certificates/{self.cert.pk}/revoke/', {'reason': 'Sai thông tin', 'end_type': 'REVOKED'})
        self.cert.refresh_from_db()

    def test_same_department_cannot_confirm_twice(self, _m):
        self._revoke('qlsv'); self._revoke('qlsv')
        self.assertEqual(ApprovalLog.objects.filter(certificate=self.cert, action='QLSV XÁC NHẬN THU HỒI').count(), 1)
        self.assertEqual(self.cert.status, 'ISSUED')
        self.assertEqual(self.cert.revoke_confirmations, 1)

    def test_dashboard_shows_progress_and_hides_button_for_confirmed_department(self, _m):
        self._revoke('qlsv')
        page = self.client.get('/dashboard/').content.decode()   # vẫn đăng nhập QLSV
        self.assertIn('Đang chờ thu hồi (1/3)', page)
        self.assertIn('Phòng bạn đã xác nhận thu hồi', page)
        self.client.force_login(self.users['daotao'])
        page = self.client.get('/dashboard/').content.decode()
        self.assertIn('Xác nhận thu hồi (1/3)', page)

    def test_revoked_only_after_three_departments(self, _m):
        self._revoke('qlsv'); self._revoke('daotao')
        self.assertEqual(self.cert.status, 'ISSUED')
        self._revoke('hieutruong')
        self.assertEqual(self.cert.status, 'REVOKED')


@mock.patch('certificates.views.approve_onchain', return_value=None)
class DetailPageTests(TestCase):
    """Update: Đợt 2 – trang chi tiết: thao tác nghiệp vụ, quay về đúng trang, không hiện mã nội bộ"""
    def setUp(self):
        self.ht = _make_user('dp_ht', 'hieutruong')
        self.cert = _make_cert('DP-1', status='PENDING', student_affairs_approved=True, academic_affairs_approved=True,
                               issue_date=None, tx_hash=None)
        self.url = f'/certificates/{self.cert.pk}/detail/'

    def test_rector_sees_sign_button_and_no_raw_state(self, _m):
        self.client.force_login(self.ht)
        page = self.client.get(self.url).content.decode()
        self.assertIn('Ký phát hành', page)
        self.assertIn('Trả hồ sơ về Đào tạo', page)
        self.assertNotIn('end_pending_onchain', page)
        self.assertNotIn(f'#{self.cert.pk} ·', page)

    def test_approve_returns_to_detail_page(self, _m):
        self.client.force_login(self.ht)
        resp = self.client.post(f'/certificates/{self.cert.pk}/approve/', {'next': self.url})
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)
        self.cert.refresh_from_db()
        self.assertEqual(self.cert.status, 'ISSUED')

    def test_external_next_is_ignored(self, _m):
        self.client.force_login(self.ht)
        resp = self.client.post(f'/certificates/{self.cert.pk}/approve/', {'next': 'https://evil.example/'})
        self.assertRedirects(resp, '/dashboard/', fetch_redirect_response=False)

    def test_action_label_is_sentence_case(self, _m):
        self.assertEqual(ApprovalLog(action='ĐÀO TẠO TRẢ VỀ QLSV').action_label, 'Đào tạo trả về QLSV')
        self.assertEqual(ApprovalLog(action='GỬI LINK KÍCH HOẠT SV').action_label, 'Gửi link kích hoạt SV')


@mock.patch('certificates.views.register_onchain', return_value=None)
class DialogTests(TestCase):
    """Update: Đợt 3 – hộp thoại nghiệp vụ: giữ dữ liệu khi lỗi, xếp loại chuẩn, nội dung theo vai trò"""
    def setUp(self):
        self.qlsv = _make_user('dl_qlsv', 'qlsv')
        self.data = {'serial_number': 'DL-1', 'student_id': 'B21', 'student_name': 'Lê Thị Mai', 'date_of_birth': '2003-02-03',
                     'major': 'CNTT', 'graduation_year': '2026', 'classification': 'Khá', 'national_id': '012345678901'}

    def test_duplicate_serial_reopens_form_with_data_but_not_cccd(self, _m):
        _make_cert('DL-1')
        self.client.force_login(self.qlsv)
        resp = self.client.post('/certificates/create/', self.data)
        self.assertEqual(resp['Location'], '/dashboard/?action=create')
        page = self.client.get('/dashboard/?action=create').content.decode()
        self.assertIn('value="Lê Thị Mai"', page)
        self.assertNotIn('012345678901', page)
        self.assertNotIn('value="Lê Thị Mai"', self.client.get('/dashboard/').content.decode())  # chỉ hiện lại một lần

    def test_invalid_classification_rejected(self, _m):
        self.client.force_login(self.qlsv)
        self.client.post('/certificates/create/', dict(self.data, serial_number='DL-2', classification='Siêu giỏi'))
        self.assertFalse(Certificate.objects.filter(serial_number='DL-2').exists())

    def test_classification_list_has_trung_binh_kha(self, _m):
        self.client.force_login(self.qlsv)
        page = self.client.get('/dashboard/').content.decode()
        self.assertIn('<option value="Trung bình khá">', page)

    def test_excel_rejects_unknown_classification(self, _m):
        import io, openpyxl
        from .excel_helper import process_excel_upload
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(['Số hiệu', 'MSSV', 'Họ tên', 'Ngày sinh', 'Ngành', 'Năm', 'Xếp loại'])
        ws.append(['XL-1', 'B1', 'A', '2003-01-01', 'CNTT', 2026, 'Giỏi lắm'])
        ws.append(['XL-2', 'B2', 'B', '2003-01-01', 'CNTT', 2026, 'Trung bình khá'])
        f = io.BytesIO(); wb.save(f); f.seek(0)
        records, errors = process_excel_upload(f)
        self.assertEqual([r['serial_number'] for r in records], ['XL-2'])
        self.assertTrue(any('Giỏi lắm' in e for e in errors))

    def test_revoke_dialog_text_depends_on_role(self, _m):
        _make_cert('DL-3', status='ISSUED', student_affairs_approved=True, academic_affairs_approved=True, rector_approved=True)
        self.client.force_login(_make_user('dl_admin', 'admin'))
        self.assertIn('có hiệu lực ngay', self.client.get('/dashboard/').content.decode())
        self.client.force_login(self.qlsv)
        self.assertIn('Đây là xác nhận của Phòng QLSV', self.client.get('/dashboard/').content.decode())
