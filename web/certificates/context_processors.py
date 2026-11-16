# Context processors cho ứng dụng certificates
from .blockchain import get_node_status
from django.conf import settings  # Update


def institution_processor(request):
    """Update: Cung cấp biến INSTITUTION"""
    from .models import Certificate  # Update: danh sách xếp loại cho các form
    return {'INSTITUTION': settings.INSTITUTION,
            'DIPLOMA_DEMO_SEAL': settings.DIPLOMA_DEMO_SEAL,
            'CLASSIFICATIONS': Certificate.CLASSIFICATIONS}  # Update: công tắc dấu / chữ ký minh hoạ cho phôi in HTML

def blockchain_status_processor(request):
    """Cung cấp thông tin trạng thái mạng Blockchain Besu cho các template."""
    try:
        return {
            'blockchain_status': get_node_status()
        }
    except Exception:
        return {
            'blockchain_status': {
                'connected': False,
                'block_number': 0,
                'node_info': 'Không kết nối được',
                'chain_id': 1337
            }
        }

