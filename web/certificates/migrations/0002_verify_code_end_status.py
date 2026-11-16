# Update: Migration P1: thêm mã xác minh ngẫu nhiên

import secrets

import django.db.models.deletion
from django.db import migrations, models

# Update: Sao chép bảng ký tự từ models.py
_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def backfill_verify_codes(apps, schema_editor):
    """Update: Cấp mã xác minh cho các văn bằng đã có trước khi có cột verify_code"""
    Certificate = apps.get_model('certificates', 'Certificate')
    used = set(Certificate.objects.exclude(verify_code__isnull=True).values_list('verify_code', flat=True))
    for cert in Certificate.objects.filter(verify_code__isnull=True):
        code = ''.join(secrets.choice(_ALPHABET) for _ in range(10))
        while code in used:  # chống trùng
            code = ''.join(secrets.choice(_ALPHABET) for _ in range(10))
        used.add(code)
        cert.verify_code = code
        cert.save(update_fields=['verify_code'])  # chỉ ghi cột mới, không đụng data_hash/tx_hash


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0001_initial'),
    ]

    operations = [
        # Update: Bổ sung 2 lựa chọn trạng thái (CANCELLED, REPLACED)
        migrations.AlterField(
            model_name='certificate',
            name='status',
            field=models.CharField(
                choices=[('PENDING', 'Chờ duyệt'), ('ISSUED', 'Đã cấp'), ('REVOKED', 'Đã thu hồi'),
                         ('CANCELLED', 'Đã hủy'), ('REPLACED', 'Đã thay thế')],
                default='PENDING', max_length=20, verbose_name='Trạng thái'),
        ),
        # Update: Loại kết thúc hiệu lực đề xuất khi thu hồi
        migrations.AddField(
            model_name='certificate',
            name='end_type',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Loại kết thúc hiệu lực'),
        ),
        # Update: Liên kết tới văn bằng thay thế
        migrations.AddField(
            model_name='certificate',
            name='replaced_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='replaces', to='certificates.certificate',
                                    verbose_name='Được thay thế bởi'),
        ),
        # Update: Mã xác minh ngẫu nhiên, duy nhất
        migrations.AddField(
            model_name='certificate',
            name='verify_code',
            field=models.CharField(blank=True, editable=False, max_length=16, null=True, unique=True,
                                   verbose_name='Mã xác minh'),
        ),
        # Update: Điền mã cho văn bằng cũ
        migrations.RunPython(backfill_verify_codes, migrations.RunPython.noop),
    ]
