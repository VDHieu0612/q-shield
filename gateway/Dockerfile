# ==========================================
# STAGE 1: BUILDER
# ==========================================
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Cài đặt toàn bộ dependencies cần thiết để biên dịch C/C++
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    ninja-build \
    gcc \
    g++ \
    libtool \
    autoconf \
    automake \
    pkg-config \
    zlib1g-dev \
    libffi-dev \
    libssl-dev \
    ca-certificates \
    wget \
    perl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 1. Biên dịch liboqs (Cung cấp các thuật toán PQC NIST FIPS 203 & 204)
RUN git clone --depth 1 --branch main https://github.com/open-quantum-safe/liboqs.git && \
    cd liboqs && \
    mkdir build && cd build && \
    cmake -GNinja -DCMAKE_INSTALL_PREFIX=/opt/liboqs -DBUILD_SHARED_LIBS=ON .. && \
    ninja && \
    ninja install

# 2. Biên dịch OpenSSL 3.5.0
RUN git clone --depth 1 --branch openssl-3.5.0 https://github.com/openssl/openssl.git && \
    cd openssl && \
    ./config --prefix=/opt/openssl-pqc --openssldir=/opt/openssl-pqc/ssl shared zlib enable-ktls && \
    make -j$(nproc) && \
    make install_sw

# Cấu hình dynamic linker cho builder để bước sau tìm thấy OpenSSL và liboqs
RUN echo "/opt/openssl-pqc/lib64" > /etc/ld.so.conf.d/openssl-pqc.conf && \
    echo "/opt/liboqs/lib" > /etc/ld.so.conf.d/liboqs.conf && \
    ldconfig

# 3. Biên dịch OQS Provider (Module cầu nối OpenSSL 3.x <-> liboqs)
RUN git clone --depth 1 --branch main https://github.com/open-quantum-safe/oqs-provider.git && \
    cd oqs-provider && \
    mkdir build && cd build && \
    cmake -GNinja \
      -DOPENSSL_ROOT_DIR=/opt/openssl-pqc \
      -DLIBOQS_ROOT_DIR=/opt/liboqs \
      -DCMAKE_INSTALL_PREFIX=/opt/openssl-pqc .. && \
    ninja && \
    ninja install

# 4. Biên dịch Nginx 1.24.0 với OpenSSL PQC
RUN apt-get update && apt-get install -y libpcre3-dev && \
    (wget --no-check-certificate https://nginx.org/download/nginx-1.24.0.tar.gz || curl -k -O https://nginx.org/download/nginx-1.24.0.tar.gz) && \
    tar -xzf nginx-1.24.0.tar.gz && \
    cd nginx-1.24.0 && \
    ./configure \
      --prefix=/opt/nginx-pqc \
      --with-http_ssl_module \
      --with-http_v2_module \
      --with-http_stub_status_module \
      --with-cc-opt="-I/opt/openssl-pqc/include" \
      --with-ld-opt="-L/opt/openssl-pqc/lib64 -Wl,-rpath,/opt/openssl-pqc/lib64" && \
    make -j$(nproc) && \
    make install

# 5. Biên dịch curl PQC (Dùng để kiểm thử kết nối trực tiếp trong container)
RUN git clone --depth 1 https://github.com/curl/curl.git && \
    cd curl && \
    autoreconf -fi && \
    ./configure \
      --prefix=/opt/curl-pqc \
      --with-openssl=/opt/openssl-pqc \
      --without-libpsl \
      --without-gnutls && \
    make -j$(nproc) && \
    make install


# ==========================================
# STAGE 2: RUNTIME (Image thành phẩm siêu nhẹ)
# ==========================================
FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# Chỉ cài runtime libraries cần thiết (bổ sung libpcre3 cho Nginx)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    zlib1g \
    libffi8 \
    libpcre3 \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy các thành phần đã build từ stage builder sang
COPY --from=builder /opt/liboqs /opt/liboqs
COPY --from=builder /opt/openssl-pqc /opt/openssl-pqc
COPY --from=builder /opt/nginx-pqc /opt/nginx-pqc
COPY --from=builder /opt/curl-pqc /opt/curl-pqc

# Cấu hình dynamic linker
RUN echo "/opt/openssl-pqc/lib64" > /etc/ld.so.conf.d/openssl-pqc.conf && \
    echo "/opt/liboqs/lib" > /etc/ld.so.conf.d/liboqs.conf && \
    ldconfig

# Đưa các công cụ PQC vào PATH hệ thống
ENV PATH="/opt/nginx-pqc/sbin:/opt/openssl-pqc/bin:/opt/curl-pqc/bin:$PATH"

# Chuẩn bị thư mục cho chứng chỉ và cấu hình
RUN mkdir -p /etc/ssl/pqc /opt/nginx-pqc/conf /var/log/nginx

# Copy file cấu hình openssl.cnf và nginx.conf
COPY openssl.cnf /opt/openssl-pqc/ssl/openssl.cnf
COPY nginx.conf /opt/nginx-pqc/conf/nginx.conf
COPY verify.sh /usr/local/bin/verify.sh
RUN chmod +x /usr/local/bin/verify.sh

# Port 8443 cho PQC HTTPS Gateway
EXPOSE 8443

WORKDIR /opt/nginx-pqc

# Lệnh mặc định: sinh cert test (nếu chưa có) và khởi động Nginx
CMD ["/bin/bash", "-c", "/usr/local/bin/verify.sh && nginx -g 'daemon off;'"]
