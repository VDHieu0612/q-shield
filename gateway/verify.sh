#!/bin/bash
set -e

echo "=========================================================="
echo "   Q-SHIELD POST-QUANTUM GATEWAY VERIFICATION"
echo "=========================================================="

# 1. Kiểm tra phiên bản OpenSSL
echo "[1] Checking OpenSSL Version..."
openssl version

# 2. Kiểm tra thuật toán KEM (ML-KEM)
echo ""
echo "[2] Checking Available PQC KEM Algorithms (ML-KEM):"
openssl list -kem-algorithms | grep -E "MLKEM|mlkem" || echo "Warning: ML-KEM filter empty"

# 3. Kiểm tra thuật toán Chữ ký số (ML-DSA)
echo ""
echo "[3] Checking Available PQC Signature Algorithms (ML-DSA):"
openssl list -signature-algorithms | grep -E "mldsa|dilithium" || echo "Warning: ML-DSA filter empty"

# 4. Kiểm tra hoặc sinh chứng chỉ ML-DSA-65 khởi tạo
mkdir -p /etc/ssl/pqc
if [ ! -f /etc/ssl/pqc/pqc_server.crt ]; then
    echo ""
    echo "[4] Generating Initial ML-DSA-65 Server Certificate..."
    openssl req -x509 -new \
        -newkey mldsa65 \
        -keyout /etc/ssl/pqc/pqc_server.key \
        -out /etc/ssl/pqc/pqc_server.crt \
        -nodes \
        -days 365 \
        -subj "/CN=localhost/O=Q-Shield Security/OU=Gateway"
    echo ">> Generated ML-DSA-65 Certificate successfully at /etc/ssl/pqc/pqc_server.crt"
else
    echo ""
    echo "[4] Existing certificate detected at /etc/ssl/pqc/pqc_server.crt"
fi

# 5. Kiểm tra cú pháp Nginx
echo ""
echo "[5] Testing Nginx Configuration Syntax..."
nginx -t

echo "=========================================================="
echo "   READY: Starting Q-Shield PQC Gateway on :8443"
echo "=========================================================="
