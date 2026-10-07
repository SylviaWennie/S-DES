"""个人模拟 B 端：独立的字符串 S-DES 实现，不导入 A 端算法或常量。"""

from functools import lru_cache


def _binary(value: str, width: int, name: str) -> str:
    if not isinstance(value, str) or len(value) != width or set(value) - {"0", "1"}:
        raise ValueError(f"{name}必须恰好是 {width} 位二进制字符（0/1）")
    return value


def _pick(sequence: str, positions: tuple[int, ...]) -> str:
    return "".join(sequence[position - 1] for position in positions)


def _xor(first: str, second: str) -> str:
    return "".join("0" if left == right else "1" for left, right in zip(first, second))


@lru_cache(maxsize=1024)
def _keys(key: str) -> tuple[str, str]:
    permuted = _pick(key, (3, 5, 2, 7, 4, 10, 1, 9, 8, 6))
    left, right = permuted[:5], permuted[5:]
    left, right = left[1:] + left[:1], right[1:] + right[:1]
    first = _pick(left + right, (6, 3, 7, 4, 8, 5, 10, 9))
    # 第二次在已经 LS-1 的两半上继续 LS-2，累计移动三位。
    left, right = left[2:] + left[:2], right[2:] + right[:2]
    return first, _pick(left + right, (6, 3, 7, 4, 8, 5, 10, 9))


def _round(block: str, subkey: str) -> str:
    left, right = block[:4], block[4:]
    mixed = _xor(_pick(right, (4, 1, 2, 3, 2, 3, 4, 1)), subkey)
    boxes = (((1, 0, 3, 2), (3, 2, 1, 0), (0, 2, 1, 3), (3, 1, 0, 2)),
             ((0, 1, 2, 3), (2, 3, 1, 0), (3, 0, 1, 2), (2, 1, 0, 3)))
    substituted = ""
    for part, box in zip((mixed[:4], mixed[4:]), boxes):
        row = int(part[0] + part[3], 2)
        column = int(part[1:3], 2)
        substituted += f"{box[row][column]:02b}"
    return _xor(left, _pick(substituted, (2, 4, 3, 1))) + right


def transform(block: str, key: str, decrypt: bool = False) -> str:
    """B 端公开接口，输入 / 输出均为位串；不使用 A 端数据路径。"""
    _binary(block, 8, "分组")
    _binary(key, 10, "密钥")
    subkeys = _keys(key)
    if decrypt:
        subkeys = subkeys[::-1]
    state = _pick(block, (2, 6, 3, 1, 4, 8, 5, 7))
    state = _round(state, subkeys[0])
    state = _round(state[4:] + state[:4], subkeys[1])
    return _pick(state, (4, 1, 3, 5, 7, 2, 8, 6))
