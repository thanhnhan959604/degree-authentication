import os
import json
from dotenv import load_dotenv
from solcx import compile_source, install_solc
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

#load các biến môi trường
load_dotenv()

RPC_URL = os.getenv("BESU_RPC_NODE1")

#dùng ví của phòng qlsv để làm người trả phí và deploy hợp đồng
DEPLOYER_ADDRESS = Web3.to_checksum_address(os.getenv("STUDENT_AFFAIRS_ADDRESS"))
DEPLOYER_PRIVATE_KEY = os.getenv("STUDENT_AFFAIRS_PRIVATE_KEY")

#lấy 3 địa chỉ phòng ban để truyền vào hợp đồng lúc deploy
STUDENT_AFFAIRS = Web3.to_checksum_address(os.getenv("STUDENT_AFFAIRS_ADDRESS"))
ACADEMIC_AFFAIRS = Web3.to_checksum_address(os.getenv("ACADEMIC_AFFAIRS_ADDRESS"))
RECTOR = Web3.to_checksum_address(os.getenv("RECTOR_ADDRESS"))

#kết nối tới node 1
w3 = Web3(Web3.HTTPProvider(RPC_URL))
#cầu nối middleware cho mạng QBFT (Proof of authority)
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

if not w3.is_connected():
    print(f"không thể kết nối tới node tại {RPC_URL}")
    exit()
print("Đã kết nối thành công đến node")

#cài đặt solidity compiler và biên dịch Contract
print("cài đặt trình biên dịc solidity 0.8.20")
install_solc("0.8.20")

print("đang biên dịch file CertificateRegistry.sol")
#đọc file smart constract
with open("contracts/CertificateRegistry.sol", "r", encoding="utf-8") as f:
    contract_source_code = f.read()

#biên dịch mã nguồn
compile_sol = compile_source(
    contract_source_code,
    #trích xuất ra abi và bin
    output_values=["abi", "bin"],
    solc_version="0.8.20",
    evm_version="london"
)

#lấy hợp đồng từ điển, lấy ra tên định danh và từ điển
contract_id, contract_interface = compile_sol.popitem()
abi = contract_interface["abi"]
bytecode = contract_interface["bin"]

#tạo giao dịch deploy hợp đồng
print("gửi giao dịch triễn khai hợp đồng lên blockchain")
CertificateRegistry = w3.eth.contract(abi=abi, bytecode=bytecode)
nonce = w3.eth.get_transaction_count(DEPLOYER_ADDRESS)


#xây dựng giao dịch
transaction = CertificateRegistry.constructor(
    STUDENT_AFFAIRS,
    ACADEMIC_AFFAIRS,
    RECTOR
).build_transaction({
    "chainId": int(os.getenv("BESU_CHAIN_ID")),
    "gasPrice": 0, #phí gas =0
    "gas": 3000000, #giới hạn gas tối đa
    "nonce": nonce, #số thứ tự giao dịch
})


#ký bằng khoá bí mật và gửi đi
#ký số giao dịch
signed_txn = w3.eth.account.sign_transaction(transaction, private_key=DEPLOYER_PRIVATE_KEY)
#đẩy lên mạng giao dịch
tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

#chờ xác nhận giao dịch và đóng block
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
#lấy địa chỉ giao dịch
contract_address = tx_receipt.contractAddress


print("\nTRIỂN KHAI THÀNH CÔNG")
print(f"Địa chỉ Contract vừa tạo : {contract_address}")
print(f"Mã giao dịch (Tx Hash)   : {tx_receipt.transactionHash.hex()}")


#lưa ABI và địa chỉ vào file JSION
os.makedirs("contracts/compiled", exist_ok=True)
with open("contracts/compiled/contract_info.json", "w", encoding="utf-8") as f:
    json.dump({
        "address": contract_address,
        "abi": abi
    }, f, indent=4)
print("đã lưu thông tin")