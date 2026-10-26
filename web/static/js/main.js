/**
 * HỆ THỐNG XÁC THỰC VĂN BẰNG & CHỨNG CHỈ SỐ
 * Client-side JavaScript Handlers
 */

document.addEventListener("DOMContentLoaded", function () {
    // 1. Sao chép vào clipboard (Hash, Tx Hash, Contract Address)
    const copyButtons = document.querySelectorAll(".btn-copy");
    copyButtons.forEach((btn) => {
        btn.addEventListener("click", function () {
            const textToCopy = this.getAttribute("data-copy");
            if (textToCopy) {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="bi bi-check2"></i> Đã sao chép!';
                    this.classList.add("btn-success");
                    this.classList.remove("btn-outline-secondary");

                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.classList.remove("btn-success");
                        this.classList.add("btn-outline-secondary");
                    }, 2000);
                });
            }
        });
    });

    // 2. Modal Từ chối hồ sơ (Reject Modal) Handler
    const rejectModal = document.getElementById("rejectModal");
    if (rejectModal) {
        rejectModal.addEventListener("show.bs.modal", function (event) {
            const button = event.relatedTarget;
            const certId = button.getAttribute("data-cert-id");
            const certSerial = button.getAttribute("data-cert-serial");
            const certName = button.getAttribute("data-cert-name");

            const form = rejectModal.querySelector("#rejectForm");
            form.action = `/certificates/${certId}/reject/`;

            const infoEl = rejectModal.querySelector("#rejectCertInfo");
            if (infoEl) {
                infoEl.textContent = `${certSerial} - ${certName}`;
            }
        });
    }

    // 5. Modal Thu hồi văn bằng (Revoke Modal) Handler
    const revokeModal = document.getElementById("revokeModal");
    if (revokeModal) {
        revokeModal.addEventListener("show.bs.modal", function (event) {
            const button = event.relatedTarget;
            const certId = button.getAttribute("data-cert-id");
            const certSerial = button.getAttribute("data-cert-serial");
            const certName = button.getAttribute("data-cert-name");

            const form = revokeModal.querySelector("#revokeForm");
            form.action = `/certificates/${certId}/revoke/`;

            const infoEl = revokeModal.querySelector("#revokeCertInfo");
            if (infoEl) {
                infoEl.textContent = `${certSerial} - ${certName}`;
            }
        });
    }

    // 6. Modal Chỉnh sửa hồ sơ bị từ chối (Edit Modal) Handler
    const editModal = document.getElementById("editModal");
    if (editModal) {
        editModal.addEventListener("show.bs.modal", function (event) {
            const button = event.relatedTarget;
            const certId = button.getAttribute("data-cert-id");
            const serial = button.getAttribute("data-cert-serial");
            const studentId = button.getAttribute("data-cert-studentid");
            const name = button.getAttribute("data-cert-name");
            const dob = button.getAttribute("data-cert-dob");
            const major = button.getAttribute("data-cert-major");
            const year = button.getAttribute("data-cert-year");
            const classification = button.getAttribute("data-cert-classification");
            const degreeType = button.getAttribute("data-cert-degreetype");
            const rejectReason = button.getAttribute("data-cert-rejectreason");

            const form = editModal.querySelector("#editForm");
            form.action = `/certificates/${certId}/edit/`;

            editModal.querySelector("#editSerial").value = serial;
            editModal.querySelector("#editStudentId").value = studentId;
            editModal.querySelector("#editName").value = name;
            editModal.querySelector("#editDob").value = dob;
            editModal.querySelector("#editMajor").value = major;
            editModal.querySelector("#editYear").value = year;
            editModal.querySelector("#editClassification").value = classification;
            editModal.querySelector("#editDegreeType").value = degreeType || "Bằng Cử nhân";

            const reasonEl = editModal.querySelector("#editRejectReasonAlert");
            if (reasonEl) {
                reasonEl.textContent = rejectReason || "Hồ sơ cần chỉnh sửa lại theo yêu cầu của phòng ban.";
            }
        });
    }

    // 7. Modal Xem chi tiết kỹ thuật & Lịch sử (Detail Modal) Handler
    const detailModal = document.getElementById("detailModal");
    if (detailModal) {
        detailModal.addEventListener("show.bs.modal", function (event) {
            const button = event.relatedTarget;
            const serial = button.getAttribute("data-cert-serial");
            const studentId = button.getAttribute("data-cert-studentid");
            const name = button.getAttribute("data-cert-name");
            const major = button.getAttribute("data-cert-major");
            const dataHash = button.getAttribute("data-cert-hash");
            const txHash = button.getAttribute("data-cert-tx") || "Chưa phát hành On-Chain";
            const status = button.getAttribute("data-cert-status");
            const date = button.getAttribute("data-cert-date");

            detailModal.querySelector("#detailSerial").textContent = serial;
            detailModal.querySelector("#detailStudent").textContent = `${name} (${studentId})`;
            detailModal.querySelector("#detailMajor").textContent = major;
            detailModal.querySelector("#detailDataHash").textContent = dataHash;
            detailModal.querySelector("#detailTxHash").textContent = txHash;
            detailModal.querySelector("#detailStatus").textContent = status;
            detailModal.querySelector("#detailDate").textContent = date;

            const copyHashBtn = detailModal.querySelector("#btnCopyDataHash");
            if (copyHashBtn) {
                copyHashBtn.setAttribute("data-copy", dataHash);
            }
            const copyTxBtn = detailModal.querySelector("#btnCopyTxHash");
            if (copyTxBtn) {
                copyTxBtn.setAttribute("data-copy", txHash);
            }
        });
    }
});