"""Update: Các hàm bảo mật dùng chung (file mới, giai đoạn P2/P3)"""
import hashlib
import hmac
import secrets

from django.conf import settings


def normalize_national_id(raw):
    """Giữ lại chữ số của số CCCD người dùng nhập (bỏ khoảng trắng, dấu chấm, gạch)."""
    return ''.join(ch for ch in str(raw or '') if ch.isdigit())


def is_valid_national_id(raw):
    """Số CCCD hợp lệ = đúng 12 chữ số."""
    return len(normalize_national_id(raw)) == 12


def _pepper():
    """Khoá bí mật dùng cho HMAC. Ưu tiên CCCD_PEPPER trong .env; nếu trống thì suy ra từ SECRET_KEY."""
    pepper = getattr(settings, 'CCCD_PEPPER', '') or ''
    if not pepper:
        pepper = hashlib.sha256(f"cccd-pepper:{settings.SECRET_KEY}".encode('utf-8')).hexdigest()
    return pepper.encode('utf-8')


def hash_national_id(raw):
    """Trả về HMAC-SHA256 (64 ký tự hex) của số CCCD đã chuẩn hoá; chuỗi rỗng nếu không hợp lệ."""
    nid = normalize_national_id(raw)
    if len(nid) != 12:
        return ''
    return hmac.new(_pepper(), nid.encode('utf-8'), hashlib.sha256).hexdigest()


def national_id_last4(raw):
    """4 số cuối CCCD để cán bộ đối chiếu (ví dụ '5678')."""
    nid = normalize_national_id(raw)
    return nid[-4:] if len(nid) == 12 else ''


def new_share_token():
    """Update: Sinh mã chia sẻ ngẫu nhiên 192 bit, dạng an toàn cho URL (32 ký tự)"""
    return secrets.token_urlsafe(24)


def hash_token(token):
    """Update: Băm SHA-256 mã chia sẻ để lưu DB (lộ DB cũng không dùng được mã)"""
    return hashlib.sha256(str(token or '').encode('utf-8')).hexdigest()


def hash_ip(ip):
    """Update: Dấu băm rút gọn của IP cho nhật ký truy cập (đếm được lượt khác nhau, không lưu IP thật)"""
    return hmac.new(_pepper(), str(ip or '').encode('utf-8'), hashlib.sha256).hexdigest()[:16]


# =============================================================================
# Update: MÃ HOÁ HAI CHIỀU SỐ CCCD (để chính sinh viên xem lại số đầy đủ bằng nút con mắt)
# =============================================================================
# - Thuật toán AES-256-GCM (thư viện pycryptodome, đã có sẵn vì web3 cần nó). GCM vừa mã hoá vừa chống sửa bản mã.
# - Khoá lấy từ CCCD_ENCRYPTION_KEY trong .env (KHÁC với CCCD_PEPPER). Lộ riêng DB thì không đọc được CCCD.
# - Định dạng lưu: "v1:" + base64(nonce 12 byte | tag 16 byte | bản mã).
# - Chỉ giải mã khi hiển thị cho đúng sinh viên chủ sở hữu; trang công khai và dashboard cán bộ vẫn chỉ thấy 4 số cuối.

def _encryption_key():
    """32 byte khoá AES từ CCCD_ENCRYPTION_KEY; nếu trống thì suy ra từ SECRET_KEY (khi đó đổi SECRET_KEY = mất khả năng giải mã)."""
    key = getattr(settings, 'CCCD_ENCRYPTION_KEY', '') or f"cccd-enc:{settings.SECRET_KEY}"
    return hashlib.sha256(key.encode('utf-8')).digest()


def encrypt_national_id(raw):
    """Mã hoá số CCCD (12 chữ số). Trả về chuỗi rỗng nếu số không hợp lệ."""
    nid = normalize_national_id(raw)
    if len(nid) != 12:
        return ''
    import base64
    from Crypto.Cipher import AES
    nonce = secrets.token_bytes(12)
    cipher = AES.new(_encryption_key(), AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(nid.encode('utf-8'))
    return 'v1:' + base64.b64encode(nonce + tag + ciphertext).decode('ascii')


def decrypt_national_id(token):
    """Giải mã chuỗi do encrypt_national_id tạo. Sai khoá / bản mã bị sửa / rỗng -> trả về chuỗi rỗng."""
    if not token or not str(token).startswith('v1:'):
        return ''
    try:
        import base64
        from Crypto.Cipher import AES
        blob = base64.b64decode(str(token)[3:])
        nonce, tag, ciphertext = blob[:12], blob[12:28], blob[28:]
        cipher = AES.new(_encryption_key(), AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag).decode('utf-8')
    except Exception:
        return ''
