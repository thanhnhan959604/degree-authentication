import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)

# Tải cấu hình từ .env
ENV_PATH = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(ENV_PATH)

RPC_URL = os.getenv("BESU_RPC_NODE1", "http://127.0.0.1:8545")
CHAIN_ID = int(os.getenv("BESU_CHAIN_ID", 1337))

CONTRACT_INFO_PATH = Path(__file__).resolve().parent.parent.parent / "contracts" / "compiled" / "contract_info.json"

ROLE_CONFIG = {
    'qlsv': {
        'address': os.getenv("STUDENT_AFFAIRS_ADDRESS"),
        'private_key': os.getenv("STUDENT_AFFAIRS_PRIVATE_KEY"),
        'name': 'Phòng Quản lý sinh viên'
    },
    'daotao': {
        'address': os.getenv("ACADEMIC_AFFAIRS_ADDRESS"),
        'private_key': os.getenv("ACADEMIC_AFFAIRS_PRIVATE_KEY"),
        'name': 'Phòng Đào tạo'
    },
    'hieutruong': {
        'address': os.getenv("RECTOR_ADDRESS"),
        'private_key': os.getenv("RECTOR_PRIVATE_KEY"),
        'name': 'Hiệu trưởng'
    }
}

def get_web3_client():
    """Khởi tạo kết nối Web3 tới Besu Node 1"""
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 5}))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        return w3
    except Exception as e:
        logger.error(f"Lỗi khởi tạo Web3: {e}")
        return None

def get_contract(w3=None):
    """Lấy đối tượng Smart Contract đã triển khai"""
    if not w3:
        w3 = get_web3_client()
    if not w3 or not w3.is_connected():
        return None, None

    if not CONTRACT_INFO_PATH.exists():
        logger.warning(f"Không tìm thấy file {CONTRACT_INFO_PATH}")
        return None, None

    try:
        with open(CONTRACT_INFO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            address = Web3.to_checksum_address(data.get("address"))
            abi = data.get("abi")
            contract = w3.eth.contract(address=address, abi=abi)
            return contract, address
    except Exception as e:
        logger.error(f"Lỗi nạp contract: {e}")
        return None, None

def get_node_status():
    """Kiểm tra trạng thái mạng Besu"""
    w3 = get_web3_client()
    if not w3 or not w3.is_connected():
        return {
            'connected': False,
            'block_number': 0,
            'node_info': 'Không kết nối được Node Besu',
            'chain_id': CHAIN_ID
        }
    try:
        block_num = w3.eth.block_number
        return {
            'connected': True,
            'block_number': block_num,
            'node_info': 'Besu QBFT (3 Nodes)',
            'chain_id': CHAIN_ID
        }
    except Exception as e:
        return {
            'connected': False,
            'block_number': 0,
            'node_info': str(e),
            'chain_id': CHAIN_ID
        }

def register_onchain(serial_number, data_hash_hex):
    """Đăng ký văn bằng mới lên hợp đồng bằng ví Phòng QLSV"""
    w3 = get_web3_client()
    if not w3 or not w3.is_connected():
        logger.warning("Besu node offline. Bỏ qua ghi on-chain.")
        return None

    contract, _ = get_contract(w3)
    if not contract:
        return None

    try:
        qlsv = ROLE_CONFIG['qlsv']
        sender_addr = Web3.to_checksum_address(qlsv['address'])
        private_key = qlsv['private_key']

        # Chuyển data_hash sang bytes32
        data_hash_bytes = bytes.fromhex(data_hash_hex.replace('0x', ''))

        nonce = w3.eth.get_transaction_count(sender_addr)
        tx = contract.functions.register(serial_number, data_hash_bytes).build_transaction({
            'chainId': CHAIN_ID,
            'gasPrice': 0,
            'gas': 1000000,
            'nonce': nonce
        })

        signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        return receipt.transactionHash.hex()
    except Exception as e:
        logger.error(f"Lỗi register_onchain: {e}")
        return None

def approve_onchain(serial_number, data_hash_hex, role_username):
    """Phê duyệt văn bằng trên hợp đồng theo vai trò"""
    w3 = get_web3_client()
    if not w3 or not w3.is_connected():
        logger.warning("Besu node offline. Bỏ qua ghi on-chain.")
        return None

    contract, _ = get_contract(w3)
    if not contract:
        return None

    if role_username not in ROLE_CONFIG:
        return None

    try:
        conf = ROLE_CONFIG[role_username]
        sender_addr = Web3.to_checksum_address(conf['address'])
        private_key = conf['private_key']

        data_hash_bytes = bytes.fromhex(data_hash_hex.replace('0x', ''))

        nonce = w3.eth.get_transaction_count(sender_addr)
        tx = contract.functions.approve(serial_number, data_hash_bytes).build_transaction({
            'chainId': CHAIN_ID,
            'gasPrice': 0,
            'gas': 1000000,
            'nonce': nonce
        })

        signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        return receipt.transactionHash.hex()
    except Exception as e:
        logger.error(f"Lỗi approve_onchain: {e}")
        return None

def revoke_onchain(serial_number, reason, role_username):
    """Xác nhận thu hồi văn bằng trên hợp đồng"""
    w3 = get_web3_client()
    if not w3 or not w3.is_connected():
        return None

    contract, _ = get_contract(w3)
    if not contract:
        return None

    if role_username not in ROLE_CONFIG:
        return None

    try:
        conf = ROLE_CONFIG[role_username]
        sender_addr = Web3.to_checksum_address(conf['address'])
        private_key = conf['private_key']

        nonce = w3.eth.get_transaction_count(sender_addr)
        tx = contract.functions.revoke(serial_number, reason).build_transaction({
            'chainId': CHAIN_ID,
            'gasPrice': 0,
            'gas': 1000000,
            'nonce': nonce
        })

        signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        return receipt.transactionHash.hex()
    except Exception as e:
        logger.error(f"Lỗi revoke_onchain: {e}")
        return None
