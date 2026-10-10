// DOM Ready Event
document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initDropZone();
    loadSystemOverview();
    loadDocuments();
    loadRootCA();
    loadCertificates();
});

// Navigation Handling
function initNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const pageTitle = document.getElementById("page-title");
    const pageSub = document.getElementById("page-sub");

    const titles = {
        overview: { title: "System Overview", sub: "Post-Quantum Cryptography Infrastructure Monitoring" },
        vault: { title: "Document Vault", sub: "Quantum-Resistant Hybrid Storage (AES-256 + ML-KEM + ML-DSA)" },
        ca: { title: "Certificate Authority (PKI)", sub: "Automated ML-DSA-65 Digital Certificate Management" },
        benchmark: { title: "Benchmark & Metrics", sub: "Empirical Overhead & Latency Evaluation" }
    };

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");

            navItems.forEach(btn => btn.classList.remove("active"));
            tabPanes.forEach(pane => pane.classList.remove("active"));

            item.classList.add("active");
            document.getElementById(`tab-${targetTab}`).classList.add("active");

            if (titles[targetTab]) {
                pageTitle.textContent = titles[targetTab].title;
                pageSub.textContent = titles[targetTab].sub;
            }

            if (targetTab === "benchmark" && window.renderBenchmarkCharts) {
                window.renderBenchmarkCharts();
            }
        });
    });
}

// 1. Overview Loader
async function loadSystemOverview() {
    try {
        const statsRes = await fetch("/api/vault/stats");
        if (statsRes.ok) {
            const stats = await statsRes.json();
            document.getElementById("stat-doc-count").textContent = stats.total_documents;
            document.getElementById("stat-doc-storage").textContent = `${(stats.total_encrypted_bytes / 1024).toFixed(1)} KB`;
        }
    } catch (e) {
        console.warn("Vault stats fetch:", e);
    }

    try {
        const caRes = await fetch("/ca/api/ca/certificates");
        if (caRes.ok) {
            const caData = await caRes.json();
            document.getElementById("stat-ca-count").textContent = `${caData.total} Active`;
        }
    } catch (e) {
        console.warn("CA certs fetch:", e);
    }
}

// 2. Vault Drop Zone & Upload
function initDropZone() {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");

    ["dragenter", "dragover"].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });
}

async function uploadFile(file) {
    const statusBox = document.getElementById("upload-status");
    statusBox.className = "alert-box alert-success";
    statusBox.textContent = `Encrypting '${file.name}' with ML-KEM-768 and signing via ML-DSA-65...`;
    statusBox.classList.remove("hidden");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch("/api/vault/upload", {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        if (res.ok) {
            statusBox.className = "alert-box alert-success";
            statusBox.textContent = `Document '${file.name}' successfully secured. KEM Ciphertext: ${data.document.kem_ciphertext_len} bytes, Signature: ${data.document.sig_len} bytes.`;
            loadDocuments();
            loadSystemOverview();
        } else {
            statusBox.className = "alert-box alert-error";
            statusBox.textContent = `Upload failed: ${data.detail || "Server error"}`;
        }
    } catch (err) {
        statusBox.className = "alert-box alert-error";
        statusBox.textContent = `Connection error: ${err.message}`;
    }
}

// 3. Document Repository Table
async function loadDocuments() {
    const tbody = document.getElementById("documents-tbody");
    try {
        const res = await fetch("/api/vault/documents");
        if (!res.ok) throw new Error("Failed to fetch documents");
        const data = await res.json();

        if (data.documents.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No documents secured in vault yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = data.documents.map(doc => `
            <tr>
                <td><strong>${escapeHtml(doc.filename)}</strong></td>
                <td>${doc.original_size} bytes</td>
                <td>${doc.encrypted_size} bytes</td>
                <td><span class="code">${doc.kem_algorithm} (${doc.kem_ciphertext_len} B)</span></td>
                <td><span class="code">${doc.sig_algorithm} (${doc.sig_len} B)</span></td>
                <td>${formatDate(doc.created_at)}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="verifyDocument('${doc.id}')">Verify</button>
                    <a href="/api/vault/download/${doc.id}" class="btn btn-sm btn-primary ml-1" download>Decrypt</a>
                </td>
            </tr>
        `).join("");
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">Error loading documents: ${err.message}</td></tr>`;
    }
}

async function verifyDocument(docId) {
    try {
        const res = await fetch(`/api/vault/verify/${docId}`);
        const data = await res.json();

        const modalBody = document.getElementById("modal-body");
        modalBody.innerHTML = `
            <div style="margin-bottom: 14px;">
                <strong>Document ID:</strong> <span class="code">${data.doc_id}</span>
            </div>
            <div style="margin-bottom: 14px;">
                <strong>Filename:</strong> ${escapeHtml(data.filename)}
            </div>
            <div style="margin-bottom: 14px;">
                <strong>Signature Algorithm:</strong> <span class="badge badge-success">${data.signature_algorithm}</span>
            </div>
            <div style="margin-bottom: 14px;">
                <strong>Integrity Status:</strong> 
                <span class="badge ${data.signature_valid ? 'badge-success' : 'badge-danger'}">
                    ${data.signature_valid ? 'VALID (MATCHED)' : 'INVALID'}
                </span>
            </div>
            <div class="alert-box ${data.signature_valid ? 'alert-success' : 'alert-error'}">
                ${data.verification_result}
            </div>
        `;
        document.getElementById("verify-modal").classList.remove("hidden");
    } catch (e) {
        alert("Failed to verify document: " + e.message);
    }
}

function closeModal() {
    document.getElementById("verify-modal").classList.add("hidden");
}

// 4. CA Management
async function loadRootCA() {
    const box = document.getElementById("root-ca-info");
    try {
        const res = await fetch("/ca/api/ca/root-info");
        if (!res.ok) throw new Error("CA unreachable");
        const data = await res.json();

        box.innerHTML = `
            <table class="spec-table">
                <tr><td>Subject</td><td><strong>${escapeHtml(data.subject)}</strong></td></tr>
                <tr><td>Issuer</td><td><strong>${escapeHtml(data.issuer)}</strong></td></tr>
                <tr><td>Algorithm</td><td><span class="badge badge-success">${data.signature_algorithm}</span></td></tr>
                <tr><td>Serial Number</td><td><span class="code">${data.serial}</span></td></tr>
                <tr><td>Valid From</td><td>${data.valid_from}</td></tr>
                <tr><td>Valid To</td><td>${data.valid_to}</td></tr>
                <tr><td>Certificate Size</td><td>${data.size_bytes} bytes</td></tr>
            </table>
        `;
    } catch (e) {
        box.innerHTML = `<p class="text-muted">Root CA offline or unreachable: ${e.message}</p>`;
    }
}

async function loadCertificates() {
    const tbody = document.getElementById("certs-tbody");
    try {
        const res = await fetch("/ca/api/ca/certificates");
        if (!res.ok) throw new Error("Certificates query failed");
        const data = await res.json();

        if (data.certificates.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No certificates registered.</td></tr>`;
            return;
        }

        tbody.innerHTML = data.certificates.map(c => `
            <tr>
                <td><strong>${escapeHtml(c.common_name || c.subject)}</strong></td>
                <td>${escapeHtml(c.issuer)}</td>
                <td><span class="code">${c.signature_algorithm}</span></td>
                <td>${c.valid_from} &rarr; ${c.valid_to}</td>
                <td>${c.size_bytes} B</td>
                <td><span class="badge badge-success">ACTIVE</span></td>
            </tr>
        `).join("");
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Failed to query registry: ${e.message}</td></tr>`;
    }
}

async function handleIssueCert(e) {
    e.preventDefault();
    const btn = document.getElementById("btn-issue");
    const statusBox = document.getElementById("issue-status");

    const cn = document.getElementById("cert-cn").value.trim();
    const sanRaw = document.getElementById("cert-san").value.trim();
    const days = parseInt(document.getElementById("cert-days").value, 10);

    const san = sanRaw ? sanRaw.split(",").map(s => s.trim()) : [cn];

    btn.disabled = true;
    btn.textContent = "Issuing...";
    statusBox.classList.add("hidden");

    try {
        const res = await fetch("/ca/api/ca/issue", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ common_name: cn, san: san, valid_days: days })
        });
        const data = await res.json();

        if (res.ok) {
            statusBox.className = "alert-box alert-success";
            statusBox.textContent = `Certificate issued for '${cn}' with Serial: ${data.certificate.serial}`;
            statusBox.classList.remove("hidden");
            document.getElementById("issue-cert-form").reset();
            loadCertificates();
            loadSystemOverview();
        } else {
            statusBox.className = "alert-box alert-error";
            statusBox.textContent = data.detail || "Issuance failed";
            statusBox.classList.remove("hidden");
        }
    } catch (err) {
        statusBox.className = "alert-box alert-error";
        statusBox.textContent = err.message;
        statusBox.classList.remove("hidden");
    } finally {
        btn.disabled = false;
        btn.textContent = "Issue X.509 PQC Certificate";
    }
}

// Utility Helpers
function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>"']/g, m => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
}

function formatDate(isoStr) {
    if (!isoStr) return "";
    const d = new Date(isoStr);
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
