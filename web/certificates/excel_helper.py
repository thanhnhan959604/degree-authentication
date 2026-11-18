import io
import hashlib
import hmac
from datetime import datetime, date
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from .models import Certificate

HMAC_SECRET = b"CTUT_BLOCKCHAIN_SECRET_KEY_2026"

def hash_national_id(val):
    if not val:
        return None
    val_str = str(val).strip()
    return hmac.new(HMAC_SECRET, val_str.encode('utf-8'), hashlib.sha256).hexdigest()

def _read_national_id(val):
    if val is None or val == '':
        return ''
    return str(val).strip()

def generate_sample_excel():
    """Tạo tệp Excel mẫu .xlsx với định dạng chuẩn và dữ liệu ví dụ"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mau_Nhap_Van_Bang"

    headers = [
        "Số hiệu văn bằng (*)",
        "Mã sinh viên (*)",
        "Họ và tên sinh viên (*)",
        "Ngày sinh (YYYY-MM-DD) (*)",
        "Ngành đào tạo (*)",
        "Năm tốt nghiệp (*)",
        "Xếp loại (*)",
        "Loại văn bằng",
        "Ngày cấp (YYYY-MM-DD)",
        "Số CCCD (12 số)",
    ]

    ws.append(headers)

    header_fill = PatternFill(start_color="26457F", end_color="26457F", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    sample_data = [
        ["CTUT-2026-0150", "B2200150", "Phạm Minh Đức", "2004-05-15", "Kỹ thuật điều khiển & TĐH", 2026, "Giỏi", "Bằng Kỹ sư", "2026-06-30", "092204000150"],
        ["CTUT-2026-0151", "B2200151", "Hoàng Thu Thảo", "2004-08-20", "Quản trị kinh doanh", 2026, "Giỏi", "Bằng Cử nhân", "2026-06-30", "092204000151"],
        ["CTUT-2026-0152", "B2200152", "Trương Công Vinh", "2004-11-10", "Kỹ thuật phần mềm", 2026, "Khá", "Bằng Kỹ sư", "2026-06-30", "092204000152"],
    ]

    for row in sample_data:
        ws.append(row)

    for row in ws.iter_rows(min_row=2, max_row=len(sample_data) + 1, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = thin_border
            cell.font = Font(name="Segoe UI", size=10)
            if cell.column in [1, 2, 4, 6, 7, 9, 10]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            if cell.column == 10:
                cell.number_format = '@'

    col_widths = [22, 18, 26, 24, 26, 18, 16, 20, 24, 20]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

def parse_date(val):
    if not val:
        return None
    if isinstance(val, (datetime, date)):
        return val if isinstance(val, date) else val.date()
    val_str = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    return None

def process_excel_upload(file):
    """Đọc và kiểm tra tệp Excel từng dòng, trả về (valid_records, errors)"""
    errors = []
    valid_records = []
    seen_serials = set()

    existing_serials = set(Certificate.objects.values_list('serial_number', flat=True))

    try:
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active
    except Exception as e:
        return [], [f"Không thể đọc tệp Excel: {str(e)}"]

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return [], ["Tệp Excel không có dòng dữ liệu nào ngoài tiêu đề."]

    for row_idx, row in enumerate(rows[1:], start=2):
        if not any(row):
            continue

        serial = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
        student_id = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        student_name = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        dob_raw = row[3] if len(row) > 3 else None
        major = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
        grad_year_raw = row[5] if len(row) > 5 else None
        classification = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ""
        degree_type = str(row[7]).strip() if len(row) > 7 and row[7] is not None else "Bằng Cử nhân"
        issue_date_raw = row[8] if len(row) > 8 else None
        national_id = _read_national_id(row[9]) if len(row) > 9 else ''

        row_errors = []

        if not serial:
            row_errors.append("Thiếu số hiệu văn bằng")
        elif serial in seen_serials or serial in existing_serials:
            row_errors.append(f"Số hiệu văn bằng '{serial}' bị trùng lặp")
        else:
            seen_serials.add(serial)

        if not student_id:
            row_errors.append("Thiếu mã sinh viên")
        else:
            # Bắt buộc: Sinh viên phải có tài khoản trong hệ thống trước khi tạo văn bằng
            from django.contrib.auth.models import User
            from django.db.models import Q
            student_user = User.objects.filter(
                Q(username__iexact=student_id) |
                (Q(profile__cccd=national_id) if national_id else Q(pk=None))
            ).first()
            if not student_user:
                row_errors.append(f"Sinh viên '{student_name}' (Mã SV: {student_id}) chưa có tài khoản trong hệ thống")

        if not student_name:
            row_errors.append("Thiếu họ tên sinh viên")

        dob = parse_date(dob_raw)
        if not dob:
            row_errors.append("Ngày sinh không hợp lệ (định dạng đúng: YYYY-MM-DD hoặc DD/MM/YYYY)")

        if not major:
            row_errors.append("Thiếu ngành đào tạo")

        try:
            grad_year = int(grad_year_raw)
            if grad_year < 1950 or grad_year > 2100:
                row_errors.append("Năm tốt nghiệp không hợp lý")
        except (ValueError, TypeError):
            row_errors.append("Năm tốt nghiệp phải là số nguyên")

        if not classification:
            row_errors.append("Thiếu xếp loại tốt nghiệp")

        issue_date = parse_date(issue_date_raw) if issue_date_raw else None

        last4 = national_id[-4:] if len(national_id) >= 4 else ''
        h_nid = hash_national_id(national_id) if national_id else None

        if row_errors:
            errors.append(f"Dòng {row_idx}: {', '.join(row_errors)}")
        else:
            valid_records.append({
                'serial_number': serial,
                'student_id': student_id,
                'student_name': student_name,
                'date_of_birth': dob,
                'major': major,
                'graduation_year': grad_year,
                'classification': classification,
                'degree_type': degree_type or 'Bằng Cử nhân',
                'issue_date': issue_date,
                'national_id_last4': last4 or None,
                'national_id_hash': h_nid,
            })

    return valid_records, errors

