import os
import subprocess
import hashlib
import json
import uuid
import logging
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("crypto_vault")
logging.basicConfig(level=logging.INFO)

OPENSSL_BIN = "/opt/openssl-pqc/bin/openssl"
KEYS_DIR = "/app/keys"
STORAGE_DIR = "/app/storage"

KEM_KEY = os.path.join(KEYS_DIR, "vault_kem768.key")
KEM_PUB = os.path.join(KEYS_DIR, "vault_kem768.pub")

DSA_KEY = os.path.join(KEYS_DIR, "vault_mldsa65.key")
DSA_PUB = os.path.join(KEYS_DIR, "vault_mldsa65.pub")


def _run_cmd(cmd_list):
    res = subprocess.run(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    )
    return res.stdout


def init_vault_keys():
    """Khởi tạo cặp khóa Master Vault (ML-KEM-768 và ML-DSA-65)."""
    os.makedirs(KEYS_DIR, exist_ok=True)
    os.makedirs(STORAGE_DIR, exist_ok=True)

    # 1. Khóa ML-KEM-768 (Dùng để bọc khóa phiên KEM)
    if not os.path.exists(KEM_KEY) or not os.path.exists(KEM_PUB):
        logger.info("Generating Vault ML-KEM-768 Master Keypair...")
        _run_cmd([OPENSSL_BIN, "genpkey", "-algorithm", "MLKEM768", "-out", KEM_KEY])
        _run_cmd([OPENSSL_BIN, "pkey", "-in", KEM_KEY, "-pubout", "-out", KEM_PUB])
        logger.info("Generated ML-KEM-768 Keypair successfully.")

    # 2. Khóa ML-DSA-65 (Dùng để ký số xác thực tài liệu)
    if not os.path.exists(DSA_KEY) or not os.path.exists(DSA_PUB):
        logger.info("Generating Vault ML-DSA-65 Master Signing Keypair...")
        _run_cmd([OPENSSL_BIN, "genpkey", "-algorithm", "mldsa65", "-out", DSA_KEY])
        _run_cmd([OPENSSL_BIN, "pkey", "-in", DSA_KEY, "-pubout", "-out", DSA_PUB])
        logger.info("Generated ML-DSA-65 Signing Keypair successfully.")


def encrypt_and_sign(file_bytes: bytes, filename: str) -> dict:
    """
    Quy trình Mã hóa Lai Hậu lượng tử (PQC Hybrid Encryption):
    1. Băm SHA-256 dữ liệu và ký số bằng ML-DSA-65.
    2. Sử dụng ML-KEM-768 bọc một khóa bí mật 256-bit (Shared Secret / DEK).
    3. Mã hóa dữ liệu bằng AES-256-GCM với khóa bí mật vừa sinh.
    """
    doc_id = str(uuid.uuid4())
    tmp_dir = os.path.join(STORAGE_DIR, f"tmp_{doc_id}")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        # Bước 1: Ký số ML-DSA-65
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        raw_file_path = os.path.join(tmp_dir, "raw.bin")
        sig_path = os.path.join(tmp_dir, "sig.bin")

        with open(raw_file_path, "wb") as f:
            f.write(file_bytes)

        _run_cmd([
            OPENSSL_BIN, "pkeyutl", "-sign",
            "-inkey", DSA_KEY,
            "-rawin", "-in", raw_file_path,
            "-out", sig_path
        ])

        with open(sig_path, "rb") as f:
            signature_bytes = f.read()

        # Bước 2: Bọc khóa bằng ML-KEM-768
        kem_ct_path = os.path.join(tmp_dir, "kem_ct.bin")
        secret_path = os.path.join(tmp_dir, "secret.bin")

        _run_cmd([
            OPENSSL_BIN, "pkeyutl", "-encap",
            "-inkey", KEM_PUB, "-pubin",
            "-out", kem_ct_path,
            "-secret", secret_path
        ])

        with open(kem_ct_path, "rb") as f:
            kem_ciphertext = f.read()

        with open(secret_path, "rb") as f:
            shared_secret = f.read()

        # Cắt đúng 32 bytes (256-bit) cho AES-256
        dek = shared_secret[:32]

        # Bước 3: Mã hóa đối xứng AES-256-GCM
        nonce = os.urandom(12)
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, file_bytes, None)

        # Bước 4: Đóng gói gói tin an toàn lưu vào ổ đĩa
        bundle_file = os.path.join(STORAGE_DIR, f"{doc_id}.qbundle")
        package = {
            "version": "1.0",
            "doc_id": doc_id,
            "filename": filename,
            "kem_algorithm": "ML-KEM-768",
            "sig_algorithm": "ML-DSA-65",
            "sha256_hash": file_hash,
            "nonce_hex": nonce.hex(),
            "kem_ct_hex": kem_ciphertext.hex(),
            "signature_hex": signature_bytes.hex(),
            "ciphertext_hex": ciphertext.hex()
        }

        with open(bundle_file, "w") as f:
            json.dump(package, f)

        encrypted_size = os.path.getsize(bundle_file)

        return {
            "id": doc_id,
            "filename": filename,
            "original_size": len(file_bytes),
            "encrypted_size": encrypted_size,
            "kem_algorithm": "ML-KEM-768",
            "sig_algorithm": "ML-DSA-65",
            "sha256_hash": file_hash,
            "kem_ciphertext_len": len(kem_ciphertext),
            "sig_len": len(signature_bytes),
            "created_at": datetime.utcnow().isoformat(),
            "status": "SECURED_PQC"
        }
    finally:
        import shutil
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)


def decrypt_and_verify(doc_id: str) -> tuple[bytes, str, bool, str]:
    """
    Giải mã và Xác thực tài liệu:
    1. Đọc gói tin qbundle.
    2. Giải bọc (Decapsulate) bằng ML-KEM-768 Private Key để khôi phục DEK.
    3. Giải mã AES-256-GCM bằng DEK.
    4. Kiểm tra chữ ký số ML-DSA-65 trên dữ liệu đã giải mã.
    """
    bundle_file = os.path.join(STORAGE_DIR, f"{doc_id}.qbundle")
    if not os.path.exists(bundle_file):
        raise FileNotFoundError(f"Document {doc_id} not found in vault")

    with open(bundle_file, "r") as f:
        pkg = json.load(f)

    tmp_dir = os.path.join(STORAGE_DIR, f"dec_{doc_id}")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        kem_ct = bytes.fromhex(pkg["kem_ct_hex"])
        nonce = bytes.fromhex(pkg["nonce_hex"])
        signature = bytes.fromhex(pkg["signature_hex"])
        ciphertext = bytes.fromhex(pkg["ciphertext_hex"])
        filename = pkg["filename"]

        # 1. Giải bọc ML-KEM-768
        ct_file = os.path.join(tmp_dir, "ct.bin")
        rec_secret_file = os.path.join(tmp_dir, "rec_secret.bin")

        with open(ct_file, "wb") as f:
            f.write(kem_ct)

        _run_cmd([
            OPENSSL_BIN, "pkeyutl", "-decap",
            "-inkey", KEM_KEY,
            "-in", ct_file,
            "-out", rec_secret_file
        ])

        with open(rec_secret_file, "rb") as f:
            recovered_secret = f.read()

        dek = recovered_secret[:32]

        # 2. Giải mã AES-256-GCM
        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        # 3. Xác minh chữ ký số ML-DSA-65
        dec_file = os.path.join(tmp_dir, "dec.bin")
        sig_file = os.path.join(tmp_dir, "sig.bin")

        with open(dec_file, "wb") as f:
            f.write(plaintext)
        with open(sig_file, "wb") as f:
            f.write(signature)

        verify_res = subprocess.run([
            OPENSSL_BIN, "pkeyutl", "-verify",
            "-inkey", DSA_PUB, "-pubin",
            "-rawin", "-in", dec_file,
            "-sigfile", sig_file
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        is_valid = ("Signature Verified Successfully" in verify_res.stdout) or (verify_res.returncode == 0)
        verify_message = "ML-DSA-65 Signature VALID - Integrity Verified" if is_valid else "Signature VERIFICATION FAILED"

        return plaintext, filename, is_valid, verify_message
    finally:
        import shutil
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
