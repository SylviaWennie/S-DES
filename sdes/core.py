"""8-bit 分组 / 10-bit 密钥；置换表使用从 1 开始的最高位索引。"""

from functools import lru_cache

P10 = (3, 5, 2, 7, 4, 10, 1, 9, 8, 6)
P8 = (6, 3, 7, 4, 8, 5, 10, 9)
IP = (2, 6, 3, 1, 4, 8, 5, 7)
IP_INVERSE = (4, 1, 3, 5, 7, 2, 8, 6)
EP = (4, 1, 2, 3, 2, 3, 4, 1)
P4 = (2, 4, 3, 1)
SBOX1 = ((1, 0, 3, 2), (3, 2, 1, 0), (0, 2, 1, 3), (3, 1, 0, 2))
# 作业明确要求使用这一版 S-box2，不能直接照搬其他教材的表。
SBOX2 = ((0, 1, 2, 3), (2, 3, 1, 0), (3, 0, 1, 2), (2, 1, 0, 3))
SPEC_ID = "course-sdes-v1-ls1-ls2-sbox2-3012"


def validate_integer(value: int, width: int, name: str) -> int:
    if type(value) is not int or not 0 <= value < (1 << width):
        raise ValueError(f"{name}必须是 0 到 {(1 << width) - 1} 的整数")
    return value


def parse_bits(value: str, width: int, name: str = "输入") -> int:
    if not isinstance(value, str) or len(value) != width or set(value) - {"0", "1"}:
        raise ValueError(f"{name}必须恰好是 {width} 位二进制字符（0/1）")
    return int(value, 2)


def bits(value: int, width: int = 8) -> str:
    return format(value, f"0{width}b")


def permute(value: int, width: int, table: tuple[int, ...]) -> int:
    result = 0
    for position in table:
        result = (result << 1) | ((value >> (width - position)) & 1)
    return result


def rotate_half(value: int, count: int) -> int:
    return ((value << count) | (value >> (5 - count))) & 31


def shift_halves(value: int, count: int) -> int:
    return (rotate_half(value >> 5, count) << 5) | rotate_half(value & 31, count)


@lru_cache(maxsize=1024)
def _subkeys(key: int) -> tuple[int, int]:
    shifted_once = shift_halves(permute(key, 10, P10), 1)
    # LS-2 在 LS-1 结果上继续左移两位，累计左移三位。
    shifted_twice = shift_halves(shifted_once, 2)
    return permute(shifted_once, 10, P8), permute(shifted_twice, 10, P8)


def generate_subkeys(key: int) -> tuple[int, int]:
    return _subkeys(validate_integer(key, 10, "密钥"))


def substitute(value: int, box: tuple[tuple[int, ...], ...]) -> int:
    row = ((value >> 2) & 2) | (value & 1)
    column = (value >> 1) & 3
    return box[row][column]


def round_function(right: int, subkey: int) -> int:
    mixed = permute(right, 4, EP) ^ subkey
    combined = (substitute(mixed >> 4, SBOX1) << 2) | substitute(mixed & 15, SBOX2)
    return permute(combined, 4, P4)


def fk(block: int, subkey: int) -> int:
    left, right = block >> 4, block & 15
    return ((left ^ round_function(right, subkey)) << 4) | right


def _transform(block: int, subkeys: tuple[int, int]) -> int:
    state = fk(permute(block, 8, IP), subkeys[0])
    state = ((state & 15) << 4) | (state >> 4)
    return permute(fk(state, subkeys[1]), 8, IP_INVERSE)


def encrypt_block(plaintext: int, key: int) -> int:
    validate_integer(plaintext, 8, "明文")
    return _transform(plaintext, generate_subkeys(key))


def decrypt_block(ciphertext: int, key: int) -> int:
    validate_integer(ciphertext, 8, "密文")
    return _transform(ciphertext, generate_subkeys(key)[::-1])


def trace_block(block: int, key: int, decrypt: bool = False) -> dict:
    """返回密钥扩展和每一轮的教学轨迹；不保存用户数据。"""
    validate_integer(block, 8, "分组")
    first_key, second_key = generate_subkeys(key)
    permuted_key = permute(key, 10, P10)
    shifted_once = shift_halves(permuted_key, 1)
    shifted_twice = shift_halves(shifted_once, 2)
    state = permute(block, 8, IP)
    initial = state
    rounds = []
    for index, subkey in enumerate((second_key, first_key) if decrypt else (first_key, second_key)):
        left, right = state >> 4, state & 15
        expanded = permute(right, 4, EP)
        mixed = expanded ^ subkey
        sbox_left = substitute(mixed >> 4, SBOX1)
        sbox_right = substitute(mixed & 15, SBOX2)
        p4_result = permute((sbox_left << 2) | sbox_right, 4, P4)
        output = ((left ^ p4_result) << 4) | right
        rounds.append({"round": index + 1, "input": bits(state), "subkey": bits(subkey),
                       "ep": bits(expanded), "xor": bits(mixed),
                       "sbox1": bits(sbox_left, 2), "sbox2": bits(sbox_right, 2),
                       "p4": bits(p4_result, 4), "output": bits(output)})
        state = ((output & 15) << 4) | (output >> 4) if index == 0 else output
    return {"key": bits(key, 10), "p10": bits(permuted_key, 10),
            "ls1": bits(shifted_once, 10), "ls2": bits(shifted_twice, 10),
            "k1": bits(first_key), "k2": bits(second_key), "ip": bits(initial),
            "swap": rounds[1]["input"], "rounds": rounds,
            "result": bits(permute(state, 8, IP_INVERSE))}


def encrypt_ascii(text: str, key: int) -> bytes:
    generate_subkeys(key)
    if not isinstance(text, str):
        raise ValueError("明文必须是 ASCII 字符串")
    try:
        data = text.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("本关使用 ASCII（0–127），不接受中文或 emoji") from error
    return bytes(encrypt_block(value, key) for value in data)


def decrypt_ascii(data: bytes, key: int) -> str:
    generate_subkeys(key)
    if not isinstance(data, bytes):
        raise ValueError("密文必须是 bytes")
    plaintext = bytes(decrypt_block(value, key) for value in data)
    try:
        return plaintext.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("解密结果不是 ASCII，请检查密钥和密文") from error
