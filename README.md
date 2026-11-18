# HỆ THỐNG XÁC THỰC VĂN BẰNG ĐẠI HỌC BẰNG BLOCKCHAIN
Đề án: Quản lý, cấp phát và chống làm giả văn bằng tốt nghiệp (CTUT)
Nền tảng: Python (Django) - Cơ sở dữ liệu PostgreSQL - Mạng Blockchain Hyperledger Besu (QBFT)

---

## 1. GIỚI THIỆU DỰ ÁN

Hệ thống Degree Authentication được xây dựng nhằm số hóa, quản lý và xác thực tính hợp pháp của văn bằng tốt nghiệp đại học, loại bỏ nguy cơ làm giả văn bằng hoặc tự ý sửa đổi điểm số trong cơ sở dữ liệu truyền thống.

Các đặc điểm cốt lõi:
- Lưu trữ kép (Dual-Storage): Thông tin chi tiết lưu trong cơ sở dữ liệu PostgreSQL (off-chain) để truy vấn nhanh; Dấu băm dữ liệu (Data Hash SHA-256) được neo cố định trên mạng Blockchain Hyperledger Besu (on-chain) để chống sửa đổi.
- Quy trình ký duyệt 3 cấp: Văn bằng chỉ có hiệu lực pháp lý khi có đủ 3 chữ ký số từ 3 ví riêng biệt trên Blockchain theo thứ tự: Phòng Quản lý Sinh viên -> Phòng Đào tạo -> Hiệu trưởng.
- Xác thực và đối soát tức thì: Nhà tuyển dụng và xã hội có thể tra cứu bằng Số hiệu văn bằng hoặc quét mã QR. Hệ thống tự động tính lại dấu băm từ CSDL và đối chiếu trực tiếp với dấu băm gốc trên Blockchain để phát hiện mọi hành vi gian lận.
- Bảo mật danh tính: Không lưu số CCCD dạng rõ; sử dụng mã băm HMAC-SHA256 và chỉ hiển thị 4 số cuối để bảo vệ quyền riêng tư công dân.

---


## 2. CÔNG NGHỆ VÀ CÔNG CỤ SỬ DỤNG

- Nền tảng Blockchain: Hyperledger Besu (phiên bản 24.x), mạng Consortium nội bộ gồm 3 Validator Nodes.
- Thuật toán đồng thuận: QBFT (Quorum Byzantine Fault Tolerance), chu kỳ tạo khối 2 giây/block, hoàn tất tức thì (instant finality), min-gas-price = 0 (không tốn phí giao dịch).
- Hợp đồng thông minh: Solidity v0.8.20 (CertificateRegistry.sol).
- Giao tiếp Blockchain: Web3.py v7.x kết hợp ExtraDataToPOAMiddleware, py-solc-x.
- Backend Web: Python 3.11, Django 5.x.
- Cơ sở dữ liệu: PostgreSQL 16.
- Xử lý dữ liệu và đồ họa: OpenPyXL (xử lý Excel), Pillow và qrcode (tạo mã QR và phôi bằng), jsQR (quét mã QR bằng camera trên trình duyệt).
- Môi trường vận hành: Docker và Docker Compose (điều phối 5 containers trong subnet 172.16.239.0/24).

---

## 3. HƯỚNG DẪN KHỞI CHẠY HỆ THỐNG

### Bước 1: Chuẩn bị môi trường
Máy tính cần cài đặt:
- Docker và Docker Compose
- Python 3.11 trở lên

### Bước 2: Khởi động các dịch vụ bằng Docker Compose
Mở cửa sổ dòng lệnh (Terminal / PowerShell) tại thư mục gốc của dự án và chạy lệnh:
```bash
docker compose up -d
```
Lệnh này sẽ khởi động 5 containers chạy ngầm:
- degree-postgres: Database PostgreSQL (Cổng máy thật 5433 -> container 5432)
- besu-node1: Validator Node 1 (RPC Cổng 8545, P2P Cổng 30303)
- besu-node2: Validator Node 2 (RPC Cổng 8546)
- besu-node3: Validator Node 3 (RPC Cổng 8547)
- degree-web: Ứng dụng Web Django (Cổng máy thật 8000)

### Bước 3: Triển khai Smart Contract (Thực hiện ở lần đầu tiên chạy mạng)
```bash
python deploy.py
```
Script sẽ tự động biên dịch hợp đồng CertificateRegistry.sol, gửi giao dịch triển khai lên Node 1 và lưu thông tin địa chỉ contract cùng ABI vào thư mục contracts/compiled/contract_info.json.

### Bước 4: Truy cập các phân hệ trên trình duyệt
- Trang tra cứu công khai và quét mã QR: http://localhost:8000/
- Trình khám phá Blockchain (Explorer): http://localhost:8000/blockchain/
- Cổng Sinh viên: http://localhost:8000/portal/sinh-vien/
- Cổng Phòng Quản lý Sinh viên: http://localhost:8000/portal/qlsv/
- Cổng Phòng Đào tạo: http://localhost:8000/portal/daotao/
- Cổng Hiệu trưởng: http://localhost:8000/portal/hieu-truong/
- Trang quản trị hệ thống (Django Admin): http://localhost:8000/admin/

---

## 4. CẤU TRÚC THƯ MỤC DỰ ÁN

- besu/: Chứa cấu hình mạng QBFT (genesis.json, static-nodes.json, keys) và thư mục lưu trữ data của 3 nodes.
- contracts/: Mã nguồn hợp đồng CertificateRegistry.sol và file contract_info.json sau khi deploy.
- web/: Ứng dụng web Django (certificates/, templates/, static/, media/).
- deploy.py: Script biên dịch và deploy contract lên mạng Besu.
- docker-compose.yml: File cấu hình khởi chạy 5 dịch vụ hệ thống.
- Dockerfile: Hướng dẫn đóng gói container cho ứng dụng Django.
- requirements.txt: Danh sách thư viện Python cần thiết.
- .env: File lưu trữ khóa bí mật, cấu hình database và địa chỉ các ví phòng ban.
