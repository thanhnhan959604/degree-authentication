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
            // Update: hiện tiến độ xác nhận thu hồi của 3 phòng
            const prog = revokeModal.querySelector("#revokeProgress");
            const flags = button.getAttribute("data-revoke") || "000";
            if (prog) {
                const names = ["QLSV", "Đào tạo", "Hiệu trưởng"];
                const done = flags.split("").filter(function (f) { return f === "1"; }).length;
                prog.hidden = done === 0;
                prog.textContent = "Đã xác nhận " + done + "/3: " + names.map(function (n, i) { return (flags[i] === "1" ? "✓ " : "· ") + n; }).join("   ");
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
            // Update: xếp loại nằm ngoài danh sách (dữ liệu cũ) thì thêm vào để không mất giá trị
            const sel = editModal.querySelector("#editClassification");
            if (classification && ![...sel.options].some(function (o) { return o.value === classification; })) {
                sel.add(new Option(classification + " (dữ liệu cũ)", classification));
            }
            sel.value = classification;
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
// Update: Sidebar cổng sinh viên / cán bộ — mở, đóng trên màn hình nhỏ (Esc hoặc bấm nền tối để đóng)
document.addEventListener("DOMContentLoaded", function () {
    const body = document.body;
    const toggles = document.querySelectorAll("[data-ds-sidebar-toggle]");
    function setOpen(open) {
        body.classList.toggle("ds-sidebar-open", open);
        toggles.forEach(function (t) { t.setAttribute("aria-expanded", open ? "true" : "false"); });
    }
    toggles.forEach(function (t) {
        t.addEventListener("click", function () { setOpen(!body.classList.contains("ds-sidebar-open")); });
    });
    document.querySelectorAll("[data-ds-sidebar-close]").forEach(function (el) {
        el.addEventListener("click", function () { setOpen(false); });
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { setOpen(false); } });

    // Update: Mục "Tạo hồ sơ" / "Nhập từ Excel" ở sidebar mở đúng hộp thoại có sẵn trên dashboard (?action=create|excel)
    const action = new URLSearchParams(window.location.search).get("action");
    const modalId = { create: "createModal", excel: "excelModal" }[action];
    const modalEl = modalId && document.getElementById(modalId);
    if (modalEl && window.bootstrap) { window.bootstrap.Modal.getOrCreateInstance(modalEl).show(); }

    // Update: Trang đăng nhập — chọn nhóm tài khoản chỉ đổi hướng dẫn trên form; quyền vẫn do backend xác định
    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
        const panel = document.getElementById("loginPanel");
        const cards = document.querySelectorAll("[data-login-kind]");
        const kindInput = loginForm.querySelector("input[name=login_kind]");
        const label = loginForm.querySelector("[data-login-label]");
        const input = document.getElementById("id_username");
        const help = loginForm.querySelector("[data-login-help]");
        const title = document.querySelector("[data-login-panel-title]");
        const studentOnly = document.querySelectorAll("[data-student-only]");
        const texts = {
            student: { title: "Đăng nhập sinh viên", label: "Số căn cước công dân (CCCD)", ph: "Nhập 12 chữ số CCCD", mode: "numeric",
                help: "Dùng số CCCD đã đăng ký với nhà trường và mật khẩu bạn tự đặt qua email kích hoạt." },
            staff: { title: "Đăng nhập cán bộ nhà trường", label: "Tên đăng nhập hoặc email", ph: "Tên tài khoản cán bộ", mode: "text",
                help: "Quyền thao tác (QLSV, Đào tạo, Hiệu trưởng) được xác định theo tài khoản sau khi đăng nhập." }
        };
        function choose(kind, focus) {
            const t = texts[kind] || texts.staff;
            // Update: liên kết nhóm tài khoản dùng aria-current (thẻ cũ dùng aria-pressed)
            cards.forEach(function (c) {
                if (c.dataset.loginKind === kind) { c.setAttribute("aria-current", "true"); } else { c.removeAttribute("aria-current"); }
            });
            if (kindInput) { kindInput.value = kind; }
            if (label) { label.textContent = t.label; }
            if (title) { title.textContent = t.title; }
            if (help) { help.textContent = t.help; }
            if (input) { input.placeholder = t.ph; input.setAttribute("inputmode", t.mode); }
            studentOnly.forEach(function (el) { el.hidden = kind === "staff"; });
            if (panel) { panel.hidden = false; }
            if (focus && input) { input.focus(); }
        }
        cards.forEach(function (c) {
            c.addEventListener("click", function (e) {
                e.preventDefault();  // Update: đổi nhóm tại chỗ, không tải lại trang; không JS thì liên kết ?kind= vẫn hoạt động
                choose(c.dataset.loginKind, true);
                if (window.history && history.replaceState && window.URLSearchParams) { const q = new URLSearchParams(location.search); q.set("kind", c.dataset.loginKind); history.replaceState(null, "", "?" + q.toString()); }
            });
        });
        const initial = loginForm.dataset.initialKind;
        if (initial) { choose(initial, false); }
    }
});

// Update: Ô chọn trạng thái ở bảng điều khiển tự gửi form khi đổi (nút "Lọc" chỉ dùng khi tắt JavaScript)
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select[data-autosubmit]").forEach(function (sel) {
        const form = sel.form;
        if (!form) return;
        const btn = form.querySelector(".ds-toolbar-submit");
        if (btn) btn.hidden = true;
        sel.addEventListener("change", function () { form.submit(); });
    });
});

// Update: Nút "Xem thêm" mở các dòng đang ẩn (data-more) trong danh sách cùng khối
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-show-more]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const list = btn.parentElement.querySelector("[data-show-more-list]");
            if (list) { list.querySelectorAll("[data-more]").forEach(function (li) { li.hidden = false; }); }
            btn.remove();
        });
    });
});

// Update: Đợt 3 – hộp thoại mở thì con trỏ vào ô nhập đầu tiên; form nghiệp vụ khi gửi thì khoá nút và báo "Đang xử lý…"
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".modal").forEach(function (m) {
        m.addEventListener("shown.bs.modal", function () {
            const f = m.querySelector(".modal-body input:not([type=hidden]):not([readonly]):not([disabled]), .modal-body select, .modal-body textarea");
            if (f) { f.focus(); }
        });
    });
    document.querySelectorAll("form[data-busy], form[action*='/approve/']").forEach(function (form) {
        form.addEventListener("submit", function () {
            const btn = form.querySelector("button[type=submit]");
            if (!btn || btn.disabled) { return; }
            setTimeout(function () {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>Đang xử lý…';
            }, 0);
        });
    });
});
