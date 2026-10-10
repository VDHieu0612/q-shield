import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, JSONResponse
import database
import crypto_vault

app = FastAPI(
    title="Q-Shield Secure Document Vault",
    description="Post-Quantum Document Vault with Hybrid AES-256-GCM, ML-KEM-768, and ML-DSA-65",
    version="1.0.0"
)

@app.on_event("startup")
def on_startup():
    database.init_db()
    crypto_vault.init_vault_keys()


@app.get("/")
def root_info():
    return {
        "service": "Q-Shield Secure Document Vault Backend",
        "status": "online",
        "encryption": "Hybrid AES-256-GCM + ML-KEM-768 (NIST FIPS 203)",
        "digital_signature": "ML-DSA-65 (NIST FIPS 204)"
    }


@app.post("/api/vault/upload")
async def upload_and_secure(file: UploadFile = File(...)):
    """Tải file lên, mã hóa lai bằng ML-KEM-768 + AES-256-GCM và ký số bằng ML-DSA-65."""
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        meta = crypto_vault.encrypt_and_sign(content, file.filename)
        database.save_document_meta(meta)

        return {
            "status": "success",
            "message": f"Document '{file.filename}' secured with Post-Quantum Hybrid Cryptography",
            "document": meta
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vault/documents")
def list_documents():
    """Xem danh sách các tài liệu đang được bảo vệ trong kho mật."""
    docs = database.get_all_documents()
    return {
        "total": len(docs),
        "documents": docs
    }


@app.get("/api/vault/documents/{doc_id}")
def get_document(doc_id: str):
    doc = database.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.get("/api/vault/verify/{doc_id}")
def verify_document_integrity(doc_id: str):
    """Xác minh tính toàn vẹn và chữ ký số ML-DSA-65 mà không tải file về."""
    try:
        _, filename, is_valid, msg = crypto_vault.decrypt_and_verify(doc_id)
        return {
            "doc_id": doc_id,
            "filename": filename,
            "signature_valid": is_valid,
            "signature_algorithm": "ML-DSA-65 (NIST FIPS 204)",
            "verification_result": msg
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vault/download/{doc_id}")
def download_decrypted_document(doc_id: str):
    """Giải mã bằng khóa riêng ML-KEM-768 và tải file gốc về máy."""
    try:
        plaintext, filename, is_valid, msg = crypto_vault.decrypt_and_verify(doc_id)

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-PQC-Signature-Valid": str(is_valid),
            "X-PQC-Verification-Message": msg,
            "X-PQC-KEM-Algorithm": "ML-KEM-768",
            "X-PQC-Signature-Algorithm": "ML-DSA-65"
        }

        return Response(
            content=plaintext,
            media_type="application/octet-stream",
            headers=headers
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vault/stats")
def vault_stats():
    docs = database.get_all_documents()
    total_original = sum(d["original_size"] for d in docs)
    total_encrypted = sum(d["encrypted_size"] for d in docs)
    return {
        "total_documents": len(docs),
        "total_original_bytes": total_original,
        "total_encrypted_bytes": total_encrypted,
        "kem_standard": "ML-KEM-768 (FIPS 203)",
        "signature_standard": "ML-DSA-65 (FIPS 204)"
    }
