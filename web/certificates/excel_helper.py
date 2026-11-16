import io
from datetime import datetime, date
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from .models import Certificate
from .security_helper import hash_national_id, national_id_last4, is_valid_national_id  # Update: băm CCCD khi nhập Excel
from .security_helper import encrypt_national_id  # Update: lưu thêm CCCD mã hoá để sinh viên xem lại


def _read_national_id(val):
    """Update: Đọc số CCCD từ ô Excel"""
    if val is None or val == '':
        return ''
    if isinstance(val, (int, float)):
        return f"{int(val):012d}"
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
        "Số CCCD (12 số)",          # Update: tuỳ chọn — cần để sinh viên có tài khoản khi văn bằng phát hành
        "Email sinh viên",          # Update: tuỳ chọn — nhận link kích hoạt tài khoản
    ]

    ws.append(headers)

    header_fill = PatternFill(start_color="0B3B60", end_color="0B3B60", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    for col_idx, cell in enumerate(ws[1], 1):
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Thêm dữ liệu mẫu
    sample_data = [
        # Update: thêm 2 cột ví dụ CCCD + email (số CCCD mẫu là số giả)
        ["VB-2026-001", "B21DCCN001", "Nguyễn Văn An", "2003-05-15", "Công nghệ thông tin", 2026, "Giỏi", "Bằng Cử nhân", "2026-06-30", "001203000001", "an.nv@example.com"],
        ["VB-2026-002", "B21DCCN002", "Trần Thị Bình", "2003-08-20", "Khoa học máy tính", 2026, "Xuất sắc", "Bằng Kỹ sư", "2026-06-30", "001303000002", "binh.tt@example.com"],
        ["VB-2026-003", "B21DCKT003", "Lê Hoàng Cường", "2003-12-01", "Kỹ thuật phần mềm", 2026, "Khá", "Bằng Cử nhân", "2026-06-30", "", ""],
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
            if cell.column == 10:  # Update: định dạng ô CCCD là văn bản để Excel không xoá số 0 đầu
                cell.number_format = '@'

    col_widths = [22, 18, 26, 24, 26, 18, 16, 20, 24, 18, 28]  # Update: thêm độ rộng 2 cột mới
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
    seen_students = set()

    # Danh sách số hiệu đã có trong DB
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
            continue  # Bỏ qua dòng trống

        serial = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
        student_id = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        student_name = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        dob_raw = row[3] if len(row) > 3 else None
        major = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
        grad_year_raw = row[5] if len(row) > 5 else None
        classification = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ""
        degree_type = str(row[7]).strip() if len(row) > 7 and row[7] is not None else "Bằng Cử nhân"
        issue_date_raw = row[8] if len(row) > 8 else None
        national_id = _read_national_id(row[9]) if len(row) > 9 else ''          # Update: cột tuỳ chọn
        student_email = str(row[10]).strip() if len(row) > 10 and row[10] else ''  # Update: cột tuỳ chọn

        row_errors = []
        if national_id and not is_valid_national_id(national_id):  # Update
            row_errors.append("Số CCCD phải gồm đúng 12 chữ số")
        if student_email and '@' not in student_email:  # Update
            row_errors.append("Email sinh viên không hợp lệ")

        if not serial:
            row_errors.append("Thiếu số hiệu văn bằng")
        elif serial in seen_serials or serial in existing_serials:
            row_errors.append(f"Số hiệu văn bằng '{serial}' bị trùng lặp")
        else:
            seen_serials.add(serial)

        if not student_id:
            row_errors.append("Thiếu mã sinh viên")
        else:
            seen_students.add(student_id)

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
        elif classification not in Certificate.CLASSIFICATIONS:  # Update: chỉ nhận 5 loại chuẩn
            row_errors.append(f"Xếp loại '{classification}' không hợp lệ (chỉ nhận: {', '.join(Certificate.CLASSIFICATIONS)})")

        issue_date = parse_date(issue_date_raw) if issue_date_raw else None

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
                'national_id_hash': hash_national_id(national_id) or None,     # Update: chỉ lưu dấu băm
                'national_id_last4': national_id_last4(national_id) or None,   # Update
                'national_id_encrypted': encrypt_national_id(national_id) or None,  # Update
                'student_email': student_email or None,                        # Update
            })

    return valid_records, errors
