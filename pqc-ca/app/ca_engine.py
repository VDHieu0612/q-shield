import os
import subprocess
import json
import logging
from datetime import datetime

logger = logging.getLogger("pqc_ca")
logging.basicConfig(level=logging.INFO)

OPENSSL_BIN = "/opt/openssl-pqc/bin/openssl"
CA_DIR = "/etc/ssl/pqc/ca"
ISSUED_DIR = "/etc/ssl/pqc/issued"
GATEWAY_CERT_DIR = "/etc/ssl/pqc"

ROOT_KEY = os.path.join(CA_DIR, "root_ca.key")
ROOT_CRT = os.path.join(CA_DIR, "root_ca.crt")
METADATA_FILE = os.path.join(CA_DIR, "certs_registry.json")


def _run_cmd(cmd_list):
    """Thực thi lệnh shell và trả về stdout."""
    res = subprocess.run(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    )
    return res.stdout


def init_root_ca():
    """Khởi tạo Root CA chạy chữ ký số ML-DSA-65 nếu chưa tồn tại."""
    os.makedirs(CA_DIR, exist_ok=True)
    os.makedirs(ISSUED_DIR, exist_ok=True)

    if not os.path.exists(ROOT_CRT):
        logger.info("Initializing new Post-Quantum Root CA with ML-DSA-65...")
        ext_conf = os.path.join(CA_DIR, "root_ext.cnf")
        with open(ext_conf, "w") as f:
            f.write(
                "basicConstraints = critical, CA:TRUE\n"
                "keyUsage = critical, digitalSignature, cRLSign, keyCertSign\n"
                "subjectKeyIdentifier = hash\n"
            )

        cmd = [
            OPENSSL_BIN, "req", "-x509", "-new",
            "-newkey", "mldsa65",
            "-keyout", ROOT_KEY,
            "-out", ROOT_CRT,
            "-nodes",
            "-days", "3650",
            "-subj", "/CN=Q-Shield Post-Quantum Root CA/O=Q-Shield Security/OU=PKI Authority",
            "-extensions", "v3_ca",
            "-config", "/opt/openssl-pqc/ssl/openssl.cnf"
        ]
        try:
            _run_cmd(cmd)
            logger.info("Root CA created successfully at %s", ROOT_CRT)
        except Exception as e:
            # Fallback nếu config mở rộng cần cú pháp chuẩn
            cmd_fallback = [
                OPENSSL_BIN, "req", "-x509", "-new",
                "-newkey", "mldsa65",
                "-keyout", ROOT_KEY,
                "-out", ROOT_CRT,
                "-nodes",
                "-days", "3650",
                "-subj", "/CN=Q-Shield Post-Quantum Root CA/O=Q-Shield Security/OU=PKI Authority"
            ]
            _run_cmd(cmd_fallback)
            logger.info("Root CA created with standard parameters at %s", ROOT_CRT)

        if not os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, "w") as f:
                json.dump([], f)
    else:
        logger.info("Root CA already exists at %s", ROOT_CRT)


def get_cert_info(cert_path):
    """Trích xuất thông tin chi tiết của chứng chỉ X.509."""
    raw_text = _run_cmd([OPENSSL_BIN, "x509", "-in", cert_path, "-text", "-noout"])
    
    subject = "Unknown"
    issuer = "Unknown"
    sig_alg = "ML-DSA-65"
    not_before = ""
    not_after = ""
    serial = ""

    for line in raw_text.splitlines():
        line_s = line.strip()
        if line_s.startswith("Subject:"):
            subject = line_s.replace("Subject:", "").strip()
        elif line_s.startswith("Issuer:"):
            issuer = line_s.replace("Issuer:", "").strip()
        elif line_s.startswith("Signature Algorithm:"):
            sig_alg = line_s.replace("Signature Algorithm:", "").strip()
        elif line_s.startswith("Not Before:"):
            not_before = line_s.replace("Not Before:", "").strip()
        elif line_s.startswith("Not After :"):
            not_after = line_s.replace("Not After :", "").strip()
        elif line_s.startswith("Serial Number:"):
            serial = line_s.replace("Serial Number:", "").strip()

    file_size = os.path.getsize(cert_path)
    return {
        "subject": subject,
        "issuer": issuer,
        "signature_algorithm": sig_alg,
        "valid_from": not_before,
        "valid_to": not_after,
        "serial": serial,
        "size_bytes": file_size
    }


def issue_certificate(common_name: str, san_list=None, valid_days: int = 365, apply_to_gateway: bool = False):
    """Cấp phát chứng chỉ số mới ký bởi Root CA ML-DSA-65."""
    if san_list is None:
        san_list = ["localhost", "127.0.0.1", "qshield-gateway"]

    san_str = ",".join([f"IP:{s}" if s.replace(".", "").isdigit() else f"DNS:{s}" for s in san_list])

    safe_name = common_name.replace("*", "wildcard").replace(".", "_")
    key_path = os.path.join(ISSUED_DIR, f"{safe_name}.key")
    csr_path = os.path.join(ISSUED_DIR, f"{safe_name}.csr")
    crt_path = os.path.join(ISSUED_DIR, f"{safe_name}.crt")
    ext_path = os.path.join(ISSUED_DIR, f"{safe_name}.ext")

    # 1. Sinh Private Key và CSR với ML-DSA-65
    _run_cmd([
        OPENSSL_BIN, "req", "-new",
        "-newkey", "mldsa65",
        "-keyout", key_path,
        "-out", csr_path,
        "-nodes",
        "-subj", f"/CN={common_name}/O=Q-Shield Security/OU=Issued Services"
    ])

    # 2. Tạo file cấu hình phần mở rộng (SAN)
    with open(ext_path, "w") as f:
        f.write(
            "basicConstraints = CA:FALSE\n"
            "keyUsage = digitalSignature, keyEncipherment\n"
            "extendedKeyUsage = serverAuth, clientAuth\n"
            f"subjectAltName = {san_str}\n"
        )

    # 3. Ký CSR bằng Root CA ML-DSA-65
    _run_cmd([
        OPENSSL_BIN, "x509", "-req",
        "-in", csr_path,
        "-CA", ROOT_CRT,
        "-CAkey", ROOT_KEY,
        "-CAcreateserial",
        "-out", crt_path,
        "-days", str(valid_days),
        "-extfile", ext_path
    ])

    # Cập nhật registry
    info = get_cert_info(crt_path)
    info["common_name"] = common_name
    info["san"] = san_list
    info["issued_at"] = datetime.utcnow().isoformat()
    info["key_path"] = key_path
    info["crt_path"] = crt_path

    registry = []
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r") as f:
                registry = json.load(f)
        except Exception:
            registry = []

    registry.append(info)
    with open(METADATA_FILE, "w") as f:
        json.dump(registry, f, indent=2)

    # Nếu được chỉ định áp dụng cho Gateway
    if apply_to_gateway:
        import shutil
        shutil.copyfile(crt_path, os.path.join(GATEWAY_CERT_DIR, "pqc_server.crt"))
        shutil.copyfile(key_path, os.path.join(GATEWAY_CERT_DIR, "pqc_server.key"))
        logger.info("Updated Gateway certificate with CA-signed ML-DSA-65 cert")

    return info


def list_certificates():
    """Lấy danh sách chứng chỉ đã phát hành."""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []
