# Context processors cho ứng dụng certificates
from .blockchain import get_node_status

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

