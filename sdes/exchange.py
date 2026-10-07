"""可由另一组程序读取的显式算法约定和演示向量。"""

from .core import SPEC_ID, bits, decrypt_block, encrypt_block, parse_bits


def make_exchange(key: int, plaintexts: list[int]) -> dict:
    if not plaintexts or len(plaintexts) > 256:
        raise ValueError("交换文件需要 1–256 条向量")
    return {"schema": "sdes-cross-test-v1", "spec_id": SPEC_ID,
            "purpose": "public educational test vectors; keys intentionally included",
            "vectors": [{"key": bits(key, 10), "plaintext": bits(plaintext),
                         "ciphertext": bits(encrypt_block(plaintext, key))} for plaintext in plaintexts]}


def verify_exchange(document: dict) -> dict:
    if not isinstance(document, dict) or document.get("schema") != "sdes-cross-test-v1":
        raise ValueError("不支持的交换文件格式")
    if document.get("spec_id") != SPEC_ID:
        raise ValueError("算法约定不同：请核对 S-box2 和 LS-1 后继续 LS-2 的顺序")
    vectors = document.get("vectors")
    if not isinstance(vectors, list) or not 1 <= len(vectors) <= 256:
        raise ValueError("交换文件需要 1–256 条向量")
    rows = []
    for index, vector in enumerate(vectors, 1):
        if not isinstance(vector, dict):
            raise ValueError("向量必须是对象")
        key = parse_bits(vector.get("key"), 10, "密钥")
        plaintext = parse_bits(vector.get("plaintext"), 8, "明文")
        ciphertext = parse_bits(vector.get("ciphertext"), 8, "密文")
        actual_ciphertext = encrypt_block(plaintext, key)
        actual_plaintext = decrypt_block(ciphertext, key)
        rows.append({"index": index, "encrypt_ok": actual_ciphertext == ciphertext,
                     "decrypt_ok": actual_plaintext == plaintext,
                     "actual_ciphertext": bits(actual_ciphertext), "actual_plaintext": bits(actual_plaintext)})
    return {"passed": all(row["encrypt_ok"] and row["decrypt_ok"] for row in rows),
            "total": len(rows), "results": rows}
