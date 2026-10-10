import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import ca_engine

app = FastAPI(
    title="Q-Shield Post-Quantum CA Service",
    description="Automated Certificate Authority issuing ML-DSA-65 (NIST FIPS 204) X.509 Certificates",
    version="1.0.0"
)

# Khởi tạo Root CA khi khởi động ứng dụng
@app.on_event("startup")
def on_startup():
    ca_engine.init_root_ca()
    # Tự động cấp chứng chỉ chính thức cho Gateway nếu chưa có
    try:
        ca_engine.issue_certificate(
            common_name="localhost",
            san_list=["localhost", "127.0.0.1", "qshield-gateway"],
            valid_days=365,
            apply_to_gateway=True
        )
    except Exception as e:
        print(f"Initial gateway certificate issuance notice: {e}")


class IssueCertRequest(BaseModel):
    common_name: str = Field(..., example="localhost")
    san: Optional[List[str]] = Field(default=["localhost", "127.0.0.1", "qshield-gateway"])
    valid_days: Optional[int] = Field(default=365)
    apply_to_gateway: Optional[bool] = Field(default=False)


@app.get("/")
def get_status():
    return {
        "service": "Q-Shield Post-Quantum Certificate Authority (PQC-CA)",
        "status": "online",
        "algorithm": "ML-DSA-65 (CRYSTALS-Dilithium3 / NIST FIPS 204)",
        "standard": "NIST FIPS 204 PQC Digital Signature Standard"
    }


@app.get("/api/ca/root-info")
def get_root_info():
    """Lấy thông số kỹ thuật của Root CA ML-DSA-65."""
    if not os.path.exists(ca_engine.ROOT_CRT):
        raise HTTPException(status_code=404, detail="Root CA not found")
    return ca_engine.get_cert_info(ca_engine.ROOT_CRT)


@app.get("/api/ca/root-cert")
def download_root_cert():
    """Tải file chứng chỉ Root CA để import vào trust store của client."""
    if not os.path.exists(ca_engine.ROOT_CRT):
        raise HTTPException(status_code=404, detail="Root CA not found")
    return FileResponse(
        ca_engine.ROOT_CRT,
        media_type="application/x-x509-ca-cert",
        filename="qshield_root_ca_mldsa65.crt"
    )


@app.post("/api/ca/issue")
def issue_cert(req: IssueCertRequest):
    """Cấp phát chứng chỉ SSL mới ký bởi Root CA ML-DSA-65."""
    try:
        cert_info = ca_engine.issue_certificate(
            common_name=req.common_name,
            san_list=req.san,
            valid_days=req.valid_days,
            apply_to_gateway=req.apply_to_gateway
        )
        return {
            "status": "success",
            "message": f"Issued ML-DSA-65 certificate for {req.common_name}",
            "certificate": cert_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ca/certificates")
def get_certificates():
    """Danh sách các chứng chỉ đã được phát hành."""
    return {
        "total": len(ca_engine.list_certificates()),
        "certificates": ca_engine.list_certificates()
    }
