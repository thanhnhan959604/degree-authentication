"""Update: XỬ LÝ ẢNH VĂN BẰNG (file mới, giai đoạn P6)"""
import io
import math
import uuid
from datetime import date
from pathlib import Path

import qrcode
from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

FONT_DIR = Path(settings.BASE_DIR) / 'assets' / 'fonts'
if not FONT_DIR.exists():
    FONT_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'
if not FONT_DIR.exists():
    FONT_DIR = Path(__file__).resolve().parent / 'assets' / 'fonts'
W, H = 2200, 1556                                                  # tỉ lệ ~ A4 nằm ngang (√2)
PAPER, GOLD, GOLD_SOFT = (251, 247, 236), (176, 128, 52), (222, 190, 128)
RED, INK, MUTED, REDACT = (158, 27, 32), (28, 35, 48), (120, 113, 100), (17, 24, 39)
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}
REGION_FIELDS = ('name', 'dob', 'classification', 'student_id', 'other')
END_STAMP = {'REVOKED': 'ĐÃ THU HỒI', 'CANCELLED': 'ĐÃ HỦY', 'REPLACED': 'ĐÃ THAY THẾ', 'PENDING': 'CHƯA PHÁT HÀNH'}


# ----------------------------------------------------------------------------- tiện ích chung
def _font(style, size):
    name = {'regular': 'NoticiaText-Regular.ttf', 'bold': 'NoticiaText-Bold.ttf',
            'italic': 'NoticiaText-Italic.ttf', 'bolditalic': 'NoticiaText-BoldItalic.ttf'}[style]
    return ImageFont.truetype(str(FONT_DIR / name), size)


def _private_root():
    root = Path(settings.PRIVATE_MEDIA_ROOT)
    (root / 'diplomas').mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(rel):
    """Đường dẫn tuyệt đối của file trong PRIVATE_MEDIA_ROOT; chặn đường dẫn thoát ra ngoài (../)."""
    if not rel:
        return None
    root = _private_root().resolve()
    p = (root / rel).resolve()
    return p if root in p.parents and p.is_file() else None


def load_private_image(rel):
    p = _safe_path(rel)
    if p is None:
        return None
    try:
        with Image.open(p) as im:
            return im.convert('RGB')
    except (OSError, UnidentifiedImageError):
        return None


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def _center_text(draw, y, text, font, fill, cx=W / 2):
    draw.text((cx - draw.textlength(text, font=font) / 2, y), text, font=font, fill=fill)


# ----------------------------------------------------------------------------- 1. ảnh scan thật
def validate_upload(upload):
    """Kiểm tra file tải lên: dung lượng, đúng là ảnh JPEG/PNG/WEBP, không hỏng. Trả về (ảnh RGB, None) hoặc (None, lỗi)."""
    max_bytes = settings.DIPLOMA_MAX_UPLOAD_MB * 1024 * 1024
    if upload is None:
        return None, "Chưa chọn tệp ảnh văn bằng."
    if upload.size > max_bytes:
        return None, f"Tệp quá lớn (tối đa {settings.DIPLOMA_MAX_UPLOAD_MB} MB)."
    try:
        upload.seek(0)
        with Image.open(upload) as probe:
            fmt = probe.format
            probe.verify()                     # phát hiện file hỏng / giả đuôi
        if fmt not in ALLOWED_FORMATS:
            return None, "Chỉ nhận ảnh JPEG, PNG hoặc WEBP."
        upload.seek(0)
        with Image.open(upload) as im:
            im = ImageOps.exif_transpose(im)   # xoay đúng chiều theo EXIF của máy scan / điện thoại
            img = im.convert('RGB')            # bỏ kênh trong suốt, bỏ siêu dữ liệu khi lưu lại
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        return None, "Tệp không phải ảnh hợp lệ hoặc đã bị hỏng."
    if min(img.size) < 600:
        return None, "Ảnh có độ phân giải quá thấp (cạnh ngắn cần từ 600 điểm ảnh) để đối chiếu văn bằng."
    return img, None


def redact(img, regions, allowed=frozenset()):
    """Tô KÍN (màu đặc) các vùng trên MỘT BẢN SAO của ảnh. Vùng thuộc trường nằm trong `allowed` thì giữ nguyên."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    for r in regions or []:
        if r.get('field') in allowed:
            continue
        x0, y0 = w * float(r['x']) / 100, h * float(r['y']) / 100
        draw.rectangle([x0, y0, x0 + w * float(r['w']) / 100, y0 + h * float(r['h']) / 100], fill=REDACT)
    return out


def parse_regions(text):
    """Đọc vùng che từ ô nhập: mỗi dòng 'trường x y rộng cao' (đơn vị % ảnh), ví dụ 'dob 55 55.5 25 4.5'."""
    regions = []
    for n, line in enumerate((text or '').splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.replace(',', ' ').split()
        if len(parts) != 5 or parts[0] not in REGION_FIELDS:
            raise ValueError(f"Dòng {n}: cần dạng 'trường x y rộng cao', trường thuộc {', '.join(REGION_FIELDS)}.")
        try:
            x, y, w, h = (float(v) for v in parts[1:])
        except ValueError:
            raise ValueError(f"Dòng {n}: x, y, rộng, cao phải là số (đơn vị %).")
        if not (0 <= x < 100 and 0 <= y < 100 and 0 < w <= 100 and 0 < h <= 100):
            raise ValueError(f"Dòng {n}: giá trị phải nằm trong khoảng 0–100%.")
        regions.append({'field': parts[0], 'x': x, 'y': y, 'w': w, 'h': h})
    return regions


def regions_to_text(regions):
    return '\n'.join(f"{r['field']} {r['x']:g} {r['y']:g} {r['w']:g} {r['h']:g}" for r in regions or [])


def rebuild_public_scan(cert):
    """Tạo lại bản công khai từ ảnh gốc theo vùng che hiện tại; bản công khai luôn là FILE RIÊNG."""
    original = load_private_image(cert.diploma_original)
    if original is None:
        return False
    public = redact(original, cert.diploma_regions, allowed=frozenset())
    rel = cert.diploma_public or f"diplomas/{uuid.uuid4().hex}_public.png"
    public.save(_private_root() / rel, format='PNG', optimize=True)
    cert.diploma_public = rel
    return True


def save_scan(cert, upload, user):
    """Lưu ảnh scan mới làm ảnh GỐC (tên file ngẫu nhiên), tạo bản công khai đã che, đặt về trạng thái CHỜ DUYỆT.
    Trả về chuỗi lỗi hoặc None nếu thành công."""
    img, error = validate_upload(upload)
    if error:
        return error
    root = _private_root()
    for old in (cert.diploma_original, cert.diploma_public):  # xoá ảnh cũ để không còn bản gốc mồ côi
        p = _safe_path(old)
        if p:
            p.unlink(missing_ok=True)
    rel = f"diplomas/{uuid.uuid4().hex}_original.png"
    img.save(root / rel, format='PNG', optimize=True)
    cert.diploma_original = rel
    cert.diploma_public = ''
    if not cert.diploma_regions:
        cert.diploma_regions = list(settings.DIPLOMA_DEFAULT_REGIONS)
    rebuild_public_scan(cert)
    cert.diploma_public_approved = False
    cert.diploma_uploaded_at = timezone.now()
    cert.diploma_uploaded_by = user
    return None


# ----------------------------------------------------------------------------- 2. ảnh MẪU MINH HOẠ (DEMO)
def _guilloche(layer):
    """Hoa văn bảo an dạng guilloche (đường cong hypotrochoid + sóng viền), màu vàng đồng nhạt."""
    d = ImageDraw.Draw(layer)
    cx, cy = W / 2, H * 0.53
    for k, (R, r, dd, alpha) in enumerate([(330, 118, 210, 46), (290, 82, 170, 40), (380, 140, 120, 34)]):
        pts = [((R - r) * math.cos(t) + dd * math.cos((R - r) / r * t) + cx,
                (R - r) * math.sin(t) - dd * math.sin((R - r) / r * t) + cy)
               for t in (i * 2 * math.pi * r / math.gcd(int(R), int(r)) / 2400 for i in range(2401))]
        d.line(pts, fill=GOLD_SOFT + (alpha,), width=2)
    for edge in range(4):                     # dải sóng đan nhau dọc 4 cạnh
        for phase in (0, math.pi / 2, math.pi):
            pts = []
            length = W - 240 if edge in (0, 1) else H - 240
            for i in range(0, int(length), 4):
                off = 14 * math.sin(i / 22 + phase)
                if edge == 0:
                    pts.append((120 + i, 100 + off))
                elif edge == 1:
                    pts.append((120 + i, H - 100 + off))
                elif edge == 2:
                    pts.append((100 + off, 120 + i))
                else:
                    pts.append((W - 100 + off, 120 + i))
            d.line(pts, fill=GOLD + (90,), width=2)


def _dashed_rect(draw, box, color, dash=16):
    x0, y0, x1, y1 = box
    for x in range(int(x0), int(x1), dash * 2):
        draw.line([(x, y0), (min(x + dash, x1), y0)], fill=color, width=3)
        draw.line([(x, y1), (min(x + dash, x1), y1)], fill=color, width=3)
    for y in range(int(y0), int(y1), dash * 2):
        draw.line([(x0, y), (x0, min(y + dash, y1))], fill=color, width=3)
        draw.line([(x1, y), (x1, min(y + dash, y1))], fill=color, width=3)


def _dashed_circle(draw, center, radius, color, segments=36):
    cx, cy = center
    for i in range(0, segments * 2, 2):
        a0, a1 = 360 * i / (segments * 2), 360 * (i + 1) / (segments * 2)
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], a0, a1, fill=color, width=4)


def _demo_seal(img, center, radius):
    """Update: Con dấu MINH HOẠ mực đỏ: 2 vòng tròn"""
    s = 3
    size = int(radius * 2 * s + 40 * s)
    layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c, R = size / 2, radius * s
    ink = (196, 32, 40, 225)
    d.ellipse([c - R, c - R, c + R, c + R], outline=ink, width=7 * s)
    d.ellipse([c - R * 0.70, c - R * 0.70, c + R * 0.70, c + R * 0.70], outline=ink, width=3 * s)
    # Vành tròn con dấu chính thức của Trường
    ring = ' TRƯỜNG ĐẠI HỌC KỸ THUẬT - CÔNG NGHỆ CẦN THƠ ·'
    font = _font('bold', 18 * s)
    widths = [d.textlength(ch, font=font) for ch in ring]
    r_text = R * 0.85
    # Giãn đều khoảng cách ký tự để chữ phủ vừa đúng ~350°
    spread = 350 / math.degrees(sum(widths) / r_text)
    angle = -90 - 175                                                # bắt đầu từ đáy trái, chạy theo chiều kim đồng hồ
    for ch, w in zip(ring, widths):
        step = math.degrees(w / r_text) * spread
        a = math.radians(angle + step / 2)
        glyph = Image.new('RGBA', (int(w) + 6 * s, 48 * s), (0, 0, 0, 0))
        ImageDraw.Draw(glyph).text((3 * s, 16 * s), ch, font=font, fill=ink)
        glyph = glyph.rotate(-(angle + step / 2 + 90), expand=True, resample=Image.BICUBIC)
        x, y = c + r_text * math.cos(a), c + r_text * math.sin(a)
        layer.paste(glyph, (int(x - glyph.width / 2), int(y - glyph.height / 2)), glyph)
        angle += step
    for text, size_pt, dy in (('HIỆU', 30, -0.25), ('TRƯỞNG', 30, 0.08), ('★', 26, 0.40)):
        f = _font('bold', size_pt * s)
        w = d.textlength(text, font=f)
        d.text((c - w / 2, c + R * dy - size_pt * s * 0.55), text, font=f, fill=ink)
    rng = __import__('random').Random(7)                             # vệt mực không đều cho giống dấu đóng tay
    px = layer.load()
    for _ in range(size * 9):
        x, y = rng.randrange(size), rng.randrange(size)
        if px[x, y][3]:
            px[x, y] = (196, 32, 40, rng.randint(60, 160))
    layer = layer.rotate(-9, resample=Image.BICUBIC).resize((size // s, size // s), Image.LANCZOS)
    img.paste(layer, (int(center[0] - layer.width / 2), int(center[1] - layer.height / 2)), layer)


def _demo_signature(img, box):
    """Update: Chữ ký MINH HOẠ mực xanh: nét cong tự sinh theo công thức"""
    x0, y0, x1, y1 = box
    s = 3
    w, h = int((x1 - x0) * s), int((y1 - y0) * s)
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ink = (28, 58, 150, 235)
    pts = []
    for i in range(0, 900):                                            # một nét liền: vòng xoắn + gợn sóng dần sang phải
        t = i / 900
        x = w * (0.08 + 0.80 * t) + w * 0.06 * math.sin(t * 19)
        y = h * (0.50 - 0.18 * math.sin(t * 7.5) * (1 - t)) + h * 0.16 * math.cos(t * 19) * (1 - 0.6 * t)
        pts.append((x, y))
    d.line(pts, fill=ink, width=4 * s, joint='curve')
    d.line([(w * 0.10, h * 0.78), (w * 0.62, h * 0.70), (w * 0.95, h * 0.58)], fill=ink, width=3 * s, joint='curve')
    layer = layer.resize((w // s, h // s), Image.LANCZOS)
    img.paste(layer, (int(x0), int(y0)), layer)


def _qr(url, size):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=1)
    q.add_data(url or '-')
    q.make(fit=True)
    return q.make_image(fill_color='black', back_color='white').convert('RGB').resize((size, size), Image.NEAREST)


def get_masked_name(cert):
    """Họ tên đã che cho trang công khai: giữ họ và tên gọi, che tên đệm"""
    if hasattr(cert, 'masked_name') and cert.masked_name:
        return cert.masked_name
    parts = (getattr(cert, 'student_name', '') or '').split()
    if not parts:
        return ''
    if len(parts) == 1:
        return parts[0][0] + '***'
    if len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}***"
    middle = ' '.join(p[0] + '***' for p in parts[1:-1])
    return f"{parts[0]} {middle} {parts[-1]}"


def render_demo(cert, *, reveal, masked_name=None, verify_url=''):
    """Dựng ảnh MẪU MINH HOẠ của văn bằng từ dữ liệu hồ sơ.
    reveal: tập trường được VẼ dữ liệu thật ('name', 'dob', 'classification'); trường không có trong reveal
            được thay bằng thanh tô kín (hoặc họ tên đã che nếu có masked_name) — dữ liệu thật không hề được vẽ.
    Trả về (ảnh, drawn): drawn là các giá trị đã thực sự vẽ lên ảnh (dùng để kiểm thử / đối chiếu với CSDL)."""
    inst = getattr(settings, 'INSTITUTION', {
        'name': 'Trường Đại học Kỹ thuật – Công nghệ Cần Thơ',
        'city': 'Cần Thơ',
        'rector_title': 'HIỆU TRƯỞNG',
        'rector_name': 'Hoàng Nam Tiến',
        'logo': 'media/ctut_logo.png',
    })
    img = Image.new('RGB', (W, H), PAPER)
    deco = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    _guilloche(deco)
    img.paste(deco, (0, 0), deco)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, W - 40, H - 40], outline=GOLD, width=12)     # viền ngoài vàng đồng
    d.rectangle([70, 70, W - 70, H - 70], outline=GOLD, width=3)      # viền trong
    d.rectangle([140, 140, W - 140, H - 140], outline=GOLD_SOFT, width=2)
    drawn = {}

    try:                                                               # logo CTUT do người dùng cung cấp, giữ nguyên tỉ lệ
        logo_path = Path(settings.BASE_DIR) / inst.get('logo', '')
        if not logo_path.exists():
            logo_path = Path(settings.BASE_DIR) / 'media' / 'ctut_logo.png'
        if not logo_path.exists():
            logo_path = Path(settings.BASE_DIR) / 'static' / inst.get('logo', '')
        if logo_path.exists():
            with Image.open(logo_path) as logo:
                logo = logo.convert('RGBA')
                logo.thumbnail((170, 170), Image.LANCZOS)
                img.paste(logo, (int(W / 2 - logo.width / 2), 165), logo)
    except Exception:
        pass

    _center_text(d, 350, 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', _font('bold', 40), INK)
    f = _font('bold', 34)
    _center_text(d, 400, 'Độc lập - Tự do - Hạnh phúc', f, INK)
    tw = d.textlength('Độc lập - Tự do - Hạnh phúc', font=f)
    d.line([(W / 2 - tw / 2, 448), (W / 2 + tw / 2, 448)], fill=INK, width=2)
    _center_text(d, 490, inst.get('rector_title', 'HIỆU TRƯỞNG'), _font('bold', 42), INK)
    issuer = (getattr(cert, 'issuer_name', None) or inst.get('name', 'Trường Đại học Kỹ thuật – Công nghệ Cần Thơ')).upper()
    _center_text(d, 545, issuer, _font('bold', 42), INK)
    _center_text(d, 600, 'cấp', _font('italic', 36), INK)
    _center_text(d, 650, (getattr(cert, 'degree_type', 'BẰNG CỬ NHÂN') or '').upper(), _font('bold', 86), RED)
    _center_text(d, 762, (getattr(cert, 'major', 'CÔNG NGHỆ THÔNG TIN') or '').upper(), _font('bold', 44), INK)
    drawn.update(degree_type=getattr(cert, 'degree_type', ''), major=getattr(cert, 'major', ''))

    label, value_x = _font('regular', 38), 860
    for y, text in ((840, 'Cho:'), (905, 'Mã sinh viên:'), (965, 'Ngày sinh:'), (1025, 'Xếp loại tốt nghiệp:')):
        d.text((470, y + (10 if text == 'Cho:' else 0)), text, font=label, fill=INK)
    if 'name' in reveal:
        d.text((value_x, 828), cert.student_name, font=_font('bolditalic', 62), fill=INK)
        drawn['name'] = cert.student_name
    elif masked_name:
        d.text((value_x, 828), masked_name, font=_font('bolditalic', 62), fill=INK)
        drawn['name'] = masked_name
    else:
        d.rectangle([value_x, 838, value_x + 640, 892], fill=REDACT)

    if 'student_id' in reveal:
        sid = getattr(cert, 'student_id', '') or ''
        d.text((value_x, 900), sid, font=_font('bold', 40), fill=INK)
        drawn['student_id'] = sid
    else:
        d.rectangle([value_x, 905, value_x + 300, 950], fill=REDACT)

    if 'dob' in reveal:
        dob = cert.date_of_birth.strftime('%d/%m/%Y') if hasattr(cert.date_of_birth, 'strftime') else str(cert.date_of_birth)
        d.text((value_x, 960), dob, font=_font('bold', 40), fill=INK)
        drawn['dob'] = dob
    else:
        d.rectangle([value_x, 965, value_x + 330, 1010], fill=REDACT)

    if 'classification' in reveal:
        d.text((value_x, 1020), cert.classification, font=_font('bold', 40), fill=INK)
        drawn['classification'] = cert.classification
    else:
        d.rectangle([value_x, 1025, value_x + 330, 1070], fill=REDACT)

    issued = getattr(cert, 'issue_date', None) if isinstance(getattr(cert, 'issue_date', None), date) else None
    date_line = (f"{inst.get('city', 'Cần Thơ')}, ngày {issued.day:02d} tháng {issued.month:02d} năm {issued.year}" if issued
                 else f"{inst.get('city', 'Cần Thơ')}, ngày ... tháng ... năm ...")
    sx = 1610
    _center_text(d, 1080, date_line, _font('italic', 36), INK, cx=sx)
    _center_text(d, 1132, inst.get('rector_title', 'HIỆU TRƯỞNG'), _font('bold', 38), INK, cx=sx)
    if getattr(settings, 'DIPLOMA_DEMO_SEAL', True):
        # Update: Chữ ký + con dấu MINH HOẠ (tự vẽ, ghi rõ là mẫu)
        _demo_signature(img, (sx - 70, 1195, sx + 250, 1335))
        _demo_seal(img, (sx - 120, 1285), 100)
        drawn['seal'] = 'demo'
    else:
        # KHUNG CHỜ con dấu + chữ ký: không vẽ con dấu / chữ ký mô phỏng
        _dashed_circle(d, (sx - 150, 1275), 82, (190, 150, 150))
        small = _font('italic', 22)
        for i, t in enumerate(('Vị trí con dấu', 'chờ tài nguyên', 'chính thức')):
            _center_text(d, 1240 + i * 26, t, small, MUTED, cx=sx - 150)
        _dashed_rect(d, (sx - 40, 1205, sx + 270, 1330), (150, 160, 190))
        for i, t in enumerate(('Vị trí chữ ký', 'chờ tài nguyên chính thức')):
            _center_text(d, 1245 + i * 28, t, small, MUTED, cx=sx + 115)
        drawn['seal'] = 'placeholder'
    _center_text(d, 1365, inst.get('rector_name', 'Hoàng Nam Tiến'), _font('bold', 38), INK, cx=sx)

    qr_size = 200                                                       # mã QR xác minh + số hiệu
    img.paste(_qr(verify_url, qr_size), (230, 1060))
    d.text((230, 1280), 'Quét mã để xác minh', font=_font('italic', 26), fill=MUTED)
    d.text((230, 1330), 'Số hiệu: ', font=_font('italic', 34), fill=INK)
    d.text((230 + d.textlength('Số hiệu: ', font=_font('italic', 34)), 1326), cert.serial_number,
           font=_font('bold', 40), fill=RED)
    drawn.update(serial=cert.serial_number, issue_date=issued.isoformat() if issued else '')

    return img, drawn


# ----------------------------------------------------------------------------- 3. dấu trạng thái
def stamp_status(img, cert):
    """Đóng chữ trạng thái lên ảnh khi văn bằng không còn hiệu lực / chưa phát hành (không áp cho văn bằng hợp lệ)."""
    text = END_STAMP.get(cert.status)
    if not text:
        return img
    out = img.convert('RGBA')
    w, h = out.size
    size = max(40, int(w * 0.075))
    font = _font('bold', size)
    probe = ImageDraw.Draw(out)
    tw = probe.textlength(text, font=font)
    layer = Image.new('RGBA', (int(tw + size), int(size * 1.9)), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rectangle([4, 4, layer.width - 5, layer.height - 5], outline=(200, 30, 30, 210), width=max(4, size // 12))
    ld.text((size / 2, size * 0.35), text, font=font, fill=(200, 30, 30, 210))
    layer = layer.rotate(-14, expand=True)
    out.paste(layer, (int(w / 2 - layer.width / 2), int(h / 2 - layer.height / 2)), layer)
    return out.convert('RGB')


# ----------------------------------------------------------------------------- 4. chọn đúng phiên bản theo quyền
def build_image(cert, mode='public', *, allowed=frozenset(), masked_name=None, verify_url=''):
    """Trả về (ảnh, nguồn) cho từng chế độ; ảnh None nếu chưa có phiên bản phù hợp.
      mode='full'    : ảnh gốc (scan) hoặc DEMO đầy đủ  -> sinh viên chủ sở hữu, cán bộ có quyền.
      mode='public'  : bản công khai đã DUYỆT (scan)    hoặc DEMO dựng không vẽ dữ liệu che -> mọi người.
      mode='share'   : như public nhưng mở thêm các trường sinh viên cho phép trong liên kết chia sẻ.
      mode='preview' : bản công khai CHƯA duyệt, chỉ để cán bộ kiểm tra vùng che."""
    if getattr(cert, 'diploma_original', None):
        source = 'scan'
        if mode == 'full':
            img = load_private_image(cert.diploma_original)
        elif mode == 'preview':
            img = load_private_image(cert.diploma_public)
        elif not getattr(cert, 'diploma_public_approved', False):
            img = None                               # chưa duyệt vùng che -> không phát ảnh ra ngoài
        elif mode == 'share':
            original = load_private_image(cert.diploma_original)
            img = redact(original, getattr(cert, 'diploma_regions', []), allowed) if original else None
        else:
            img = load_private_image(cert.diploma_public)
    else:
        source = 'demo'
        if mode == 'full':
            reveal, mname = {'name', 'dob', 'classification', 'student_id'}, None
        elif mode == 'share':
            reveal = set(allowed) & {'name', 'dob', 'classification', 'student_id'}
            mname = None if 'name' in reveal else (masked_name or get_masked_name(cert))
        else:
            # Tra cứu công khai / quét mã QR trên bằng: bảo vệ quyền riêng tư, không để lộ thông tin cá nhân
            reveal = set()
            mname = masked_name or get_masked_name(cert)
        img, _ = render_demo(cert, reveal=reveal, masked_name=mname, verify_url=verify_url)
    if img is not None:
        img = stamp_status(img, cert)
    return img, source
