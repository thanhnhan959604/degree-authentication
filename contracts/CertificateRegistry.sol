// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract CertificateRegistry {
    /**
     * khai báo trạng thái văn bằng:
     * 0 = chưa có
     * 1 = chờ duyệt
     * 2 = đã phát hành
     * 3 = đã thu hồi
    */
   enum Status {
    None, Pending, Issued, Revoked
   }

    //định nghĩa một struct để lưu thông tin văn bằng
   struct Certificate {
    bytes32 dataHash; //dấu băm dữ liệu chuẩn hoá
    Status status;
    bool studentAffairsApproved; //phòng qlsv duyệt phát hành
    bool academicAffairsApproved;// Phòng Đào tạo duyệt phát hành
        bool rectorApproved;         // Phòng Hiệu trưởng duyệt phát hành
        bool studentAffairsRevoke;   // Phòng QLSV xác nhận thu hồi
        bool academicAffairsRevoke;  // Phòng Đào tạo xác nhận thu hồi
        bool rectorRevoke;           // Phòng Hiệu trưởng xác nhận thu hồi
        uint256 issuedAt; //lưu ngày phát hành
        uint256 revokedAt; //lưu ngày thu hồi
   }

    //lưu địa chỉ các ví có thẩm quyền
   address public studentAffairsAddr;
   address public academicAffairsAddr;
   address public rectorAddr;

   //lưu theo số hiệu văn bằng
   mapping (string => Certificate) private certificates;

    event Registered(string indexed serialNumber, bytes32 dataHash, address indexed by);
    event ApprovedIssue(string indexed serialNumber, string role, address indexed approver);
    event Issued(string indexed serialNumber, bytes32 dataHash, uint256 timestamp);
    event ApprovedRevoke(string indexed serialNumber, string role, address indexed approver, string reason);
    event Revoked(string indexed serialNumber, uint256 timestamp);



    constructor(
        address _studentAffairs,
        address _academicAffairs,
        address _rector
    ) {
        studentAffairsAddr = _studentAffairs;
        academicAffairsAddr = _academicAffairs;
        rectorAddr = _rector;
    }

    //Đăng ký hồ sơ mới (hoặc đẩy lại hồ sơ sau khi sửa lỗi bị từ chối)
    function register(string memory serialNumber, bytes32 dataHash) external {
        require(
            msg.sender == studentAffairsAddr || msg.sender == academicAffairsAddr || msg.sender == rectorAddr,
            "Khong co quyen"
        );
        Certificate storage cert = certificates[serialNumber];
        require(cert.status != Status.Issued && cert.status != Status.Revoked, "Van bang da phat hanh hoac thu hoi");

        //lưu lại dấu băm
        cert.dataHash = dataHash;
        //đổi trạng thái văn bằng
        cert.status = Status.Pending;
        //reset tất cả về false
        cert.studentAffairsApproved = false;
        cert.academicAffairsApproved = false;
        cert.rectorApproved = false;

        //phát sự kiện
        emit Registered(serialNumber, dataHash, msg.sender);
    }

    //duyệt theo vai trò của phòng ban (nếu đủ 3 phòng chuyển sang Issued)
    function approve(string memory serialNumber, bytes32 expectedHash) external {
        Certificate storage cert = certificates[serialNumber];
        require(cert.status == Status.Pending, "Ho so khong o trang thai cho duyet");
        require(cert.dataHash == expectedHash, "Dau bam du lieu khong hop le");

        //phòng quản lý sinh viên duyệt
        if (msg.sender == studentAffairsAddr) {
            cert.studentAffairsApproved = true;
            emit ApprovedIssue(serialNumber, "STUDENT_AFFAIRS", msg.sender);
        } else if (msg.sender == academicAffairsAddr) {
            require(cert.studentAffairsApproved, "Can phong QLSV duyet truoc");
            cert.academicAffairsApproved = true;
            emit ApprovedIssue(serialNumber, "ACADEMIC_AFFAIRS", msg.sender);
        } else if (msg.sender == rectorAddr) {
            require(cert.studentAffairsApproved && cert.academicAffairsApproved, "Can 2 phong truoc duyet");
            cert.rectorApproved = true;
            cert.status = Status.Issued;
            cert.issuedAt = block.timestamp;
            emit ApprovedIssue(serialNumber, "RECTOR", msg.sender);
            emit Issued(serialNumber, cert.dataHash, block.timestamp);
        } else {
            revert("Tai khoan khong thuoc 3 phong ban");
        }
    }

    //thu hồi văn bằng cũng phải được xét duyệt của 3 phòng ban
    function revoke(string memory serialNumber, string memory reason) external {
        Certificate storage cert = certificates[serialNumber];
        require(cert.status == Status.Issued, "Van bang chua duoc phat hanh nen khong the thu hoi");

        if (msg.sender == studentAffairsAddr) {
            cert.studentAffairsRevoke = true;
            emit ApprovedRevoke(serialNumber, "STUDENT_AFFAIRS", msg.sender, reason);
        } else if (msg.sender == academicAffairsAddr) {
            cert.academicAffairsRevoke = true;
            emit ApprovedRevoke(serialNumber, "ACADEMIC_AFFAIRS", msg.sender, reason);
        } else if (msg.sender == rectorAddr) {
            cert.rectorRevoke = true;
            emit ApprovedRevoke(serialNumber, "RECTOR", msg.sender, reason);
        } else {
            revert("Tai khoan khong thuoc 3 phong ban");
        }

        if (cert.studentAffairsRevoke && cert.academicAffairsRevoke && cert.rectorRevoke) {
            cert.status = Status.Revoked;
            cert.revokedAt = block.timestamp;
            emit Revoked(serialNumber, block.timestamp);
        }
    }

    //tra cứu trạng thái và dấu băm văng bằng
    function getStatus(string memory serialNumber) external view returns (
        bytes32 dataHash,
        Status status,
        bool studentAffairsApproved,
        bool academicAffairsApproved,
        bool rectorApproved,
        bool studentAffairsRevoke,
        bool academicAffairsRevoke,
        bool rectorRevoke,
        uint256 issuedAt,
        uint256 revokedAt
    ) {
        Certificate memory cert = certificates[serialNumber];
        return (
            cert.dataHash,
            cert.status,
            cert.studentAffairsApproved,
            cert.academicAffairsApproved,
            cert.rectorApproved,
            cert.studentAffairsRevoke,
            cert.academicAffairsRevoke,
            cert.rectorRevoke,
            cert.issuedAt,
            cert.revokedAt
        );
    }
        
}