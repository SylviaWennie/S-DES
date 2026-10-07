"""已知明密文的穷举实验及固定明文下的密钥碰撞统计。"""

from collections import Counter, defaultdict
from time import perf_counter_ns

from .core import bits, encrypt_block, validate_integer


def validate_pairs(pairs: list[tuple[int, int]]) -> None:
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 256:
        raise ValueError("请提供 1–256 对明密文")
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("每条记录必须包含明文和密文")
        validate_integer(pair[0], 8, "明文")
        validate_integer(pair[1], 8, "密文")


def brute_force(pairs: list[tuple[int, int]]) -> dict:
    """穷举全部 1024 个密钥；保留所有候选，不把第一个命中当作唯一解。"""
    validate_pairs(pairs)
    candidates = []
    prefix_counts = [0] * len(pairs)
    samples = [{"checked": 0, "elapsed_ms": 0.0, "matches": 0}]
    started = perf_counter_ns()
    for key in range(1024):
        for index, (plaintext, ciphertext) in enumerate(pairs):
            if encrypt_block(plaintext, key) != ciphertext:
                break
            prefix_counts[index] += 1
        else:
            candidates.append(bits(key, 10))
        if (key + 1) % 32 == 0:
            samples.append({"checked": key + 1,
                            "elapsed_ms": (perf_counter_ns() - started) / 1_000_000,
                            "matches": len(candidates)})
    elapsed_ms = (perf_counter_ns() - started) / 1_000_000
    return {"keys": candidates, "count": len(candidates), "checked": 1024,
            "prefix_counts": prefix_counts, "elapsed_ms": elapsed_ms, "samples": samples}


def collision_analysis(plaintext: int) -> dict:
    validate_integer(plaintext, 8, "明文")
    groups = defaultdict(list)
    for key in range(1024):
        groups[encrypt_block(plaintext, key)].append(bits(key, 10))
    collision_groups = [(ciphertext, keys) for ciphertext, keys in sorted(groups.items()) if len(keys) > 1]
    histogram = Counter(len(keys) for keys in groups.values())
    ciphertext, keys = collision_groups[0]  # 1024 个密钥映射到至多 256 个输出，必有碰撞。
    return {"plaintext": bits(plaintext), "distinct_ciphertexts": len(groups),
            "collision_groups": len(collision_groups), "singleton_groups": histogram.get(1, 0),
            "max_keys_per_ciphertext": max(map(len, groups.values())),
            "histogram": {str(count): frequency for count, frequency in sorted(histogram.items())},
            "example": {"ciphertext": bits(ciphertext), "keys": keys}}


def full_collision_study() -> dict:
    rows = [collision_analysis(plaintext) for plaintext in range(256)]
    return {"plaintexts_checked": 256, "encryptions": 256 * 1024,
            "all_have_collisions": all(row["collision_groups"] > 0 for row in rows),
            "min_distinct_ciphertexts": min(row["distinct_ciphertexts"] for row in rows),
            "max_distinct_ciphertexts": max(row["distinct_ciphertexts"] for row in rows),
            "rows": rows}
