import sqlite3
import os

DB_PATH = "/app/storage/vault.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        original_size INTEGER NOT NULL,
        encrypted_size INTEGER NOT NULL,
        kem_algorithm TEXT NOT NULL,
        sig_algorithm TEXT NOT NULL,
        sha256_hash TEXT NOT NULL,
        kem_ciphertext_len INTEGER NOT NULL,
        sig_len INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def save_document_meta(doc: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO documents (
        id, filename, original_size, encrypted_size,
        kem_algorithm, sig_algorithm, sha256_hash,
        kem_ciphertext_len, sig_len, created_at, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc["id"], doc["filename"], doc["original_size"], doc["encrypted_size"],
        doc["kem_algorithm"], doc["sig_algorithm"], doc["sha256_hash"],
        doc["kem_ciphertext_len"], doc["sig_len"], doc["created_at"], doc["status"]
    ))
    conn.commit()
    conn.close()

def get_all_documents():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_document_by_id(doc_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
