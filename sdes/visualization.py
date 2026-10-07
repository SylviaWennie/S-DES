"""可视化数据模型：每根置换连线和每次运算均携带实际输入 / 输出。"""

from .core import (EP, IP, IP_INVERSE, P4, P8, P10, SBOX1, SBOX2, SPEC_ID,
                   bits, decrypt_block, encrypt_block, permute, substitute, validate_integer)
from .peer import transform as peer_transform

LS1_MAPPING = (2, 3, 4, 5, 1, 7, 8, 9, 10, 6)
LS2_MAPPING = (3, 4, 5, 1, 2, 8, 9, 10, 6, 7)
SW_MAPPING = (5, 6, 7, 8, 1, 2, 3, 4)


def visual_trace(block: int, key: int, operation: str = "encrypt") -> dict:
    """生成按实际计算顺序排列的密钥扩展、两轮 Feistel、最终置换。"""
    validate_integer(block, 8, "分组")
    validate_integer(key, 10, "密钥")
    if operation not in ("encrypt", "decrypt"):
        raise ValueError("请选择加密或解密")
    steps = []

    def permutation(step_id, title, phase, value, width, mapping, label, description, **extra):
        output = permute(value, width, mapping)
        steps.append({"id": step_id, "title": title, "phase": phase,
                      "kind": "permutation", "description": description,
                      "input": bits(value, width), "output": bits(output, len(mapping)),
                      "mapping": list(mapping), "box_label": label, **extra})
        return output

    permuted_key = permutation("p10", "P10 · 密钥初始置换", "key", key, 10, P10,
                               "P10", "输出第 i 位取输入的 P10[i] 位；位置从左往右、从 1 开始。")
    shifted_once = permutation("ls1", "LS-1 · 两半分别循环左移 1 位", "key", permuted_key,
                               10, LS1_MAPPING, "LS-1", "按 5 + 5 位分开，各自循环左移 1 位。", half_width=5)
    first_key = permutation("p8-k1", "P8 · 生成 K1", "key", shifted_once, 10, P8,
                            "P8", "从 LS-1 的 10 位结果中选择 8 位，得到第一子密钥 K1。")
    shifted_twice = permutation("ls2", "LS-2 · 在 LS-1 结果上继续左移 2 位", "key", shifted_once,
                                10, LS2_MAPPING, "LS-2", "两半各自再循环左移 2 位；相对 P10 的结果累计左移 3 位。", half_width=5)
    second_key = permutation("p8-k2", "P8 · 生成 K2", "key", shifted_twice, 10, P8,
                             "P8", "从继续 LS-2 的 10 位结果中选择 8 位，得到第二子密钥 K2。")
    state = permutation("ip", "IP · 分组初始置换", "round1", block, 8, IP,
                        "IP", "8 位输入经过 IP 后分为左半 L 和右半 R，各 4 位。")
    round_keys = (("K2", second_key), ("K1", first_key)) if operation == "decrypt" else (("K1", first_key), ("K2", second_key))
    for index, (subkey_name, subkey) in enumerate(round_keys, 1):
        phase = f"round{index}"
        left, right = state >> 4, state & 15
        expanded = permute(right, 4, EP)
        mixed = expanded ^ subkey
        substituted = (substitute(mixed >> 4, SBOX1) << 2) | substitute(mixed & 15, SBOX2)
        p4 = permute(substituted, 4, P4)
        output = ((left ^ p4) << 4) | right
        steps.append({"id": f"r{index}-overview", "title": f"第 {index} 轮 · fₖ 使用 {subkey_name}",
                      "phase": phase, "kind": "round", "description": "F(R, K) = P4(S1 ‖ S2)，fₖ(L ‖ R) = (L ⊕ F) ‖ R；本步骤展示全景，随后逐项计算。",
                      "input": bits(state), "output": bits(output), "left": bits(left, 4), "right": bits(right, 4),
                      "ep": bits(expanded), "mixed": bits(mixed), "sbox_output": bits(substituted, 4),
                      "p4": bits(p4, 4), "subkey": bits(subkey), "subkey_name": subkey_name})
        permutation(f"r{index}-ep", f"第 {index} 轮 · EP 扩展置换", phase, right, 4, EP,
                    "EP", "仅取右半 R，将 4 位按 EP 复制 / 排列成 8 位；左半 L 暂存。")
        steps.append({"id": f"r{index}-xor-key", "title": f"第 {index} 轮 · 与 {subkey_name} 异或",
                      "phase": phase, "kind": "xor", "description": "逐位异或：相同得 0，不同得 1。",
                      "left": bits(expanded), "right": bits(subkey), "output": bits(mixed),
                      "left_label": "EP(R)", "right_label": subkey_name})
        boxes = []
        for name, part, table in (("S-box1", mixed >> 4, SBOX1), ("S-box2", mixed & 15, SBOX2)):
            part_bits = bits(part, 4)
            boxes.append({"name": name, "input": part_bits, "output": bits(substitute(part, table), 2),
                          "row": int(part_bits[0] + part_bits[3], 2), "column": int(part_bits[1:3], 2),
                          "table": [list(row) for row in table]})
        steps.append({"id": f"r{index}-sboxes", "title": f"第 {index} 轮 · S-box 查表",
                      "phase": phase, "kind": "sboxes", "description": "每 4 位的首尾两位选择行，中间两位选择列；行列均从 00 计数。S-box2 按作业图片修订版。",
                      "input": bits(mixed), "output": bits(substituted, 4), "boxes": boxes})
        permutation(f"r{index}-p4", f"第 {index} 轮 · P4 / SPBox", phase, substituted, 4, P4,
                    "P4", "先拼接两个 S-box 的各 2 位输出，再按 (2, 4, 3, 1) 置换。")
        steps.append({"id": f"r{index}-xor-left", "title": f"第 {index} 轮 · 左半异或与拼接",
                      "phase": phase, "kind": "xor", "description": f"L 与 F(R, {subkey_name}) 异或，右半 R 原样保留。拼接后为 {bits(output)}。",
                      "left": bits(left, 4), "right": bits(p4, 4), "output": bits(left ^ p4, 4),
                      "left_label": "L", "right_label": f"F(R, {subkey_name})", "retained_right": bits(right, 4),
                      "block_output": bits(output)})
        if index == 1:
            state = permutation("sw", "SW · 交换左右两半", "round1", output, 8, SW_MAPPING,
                                "SW", "仅在两轮之间交换一次：左 4 位与右 4 位互换。", half_width=4)
        else:
            state = output
    result = permutation("ip-inverse", "IP⁻¹ · 最终逆置换", "output", state, 8, IP_INVERSE,
                         "IP⁻¹", "第二轮结束后不交换，直接做 IP 的逆置换，得到最终 8 位结果。")
    return {"mode": operation, "input": bits(block), "key": bits(key, 10), "result": bits(result),
            "k1": bits(first_key), "k2": bits(second_key), "spec_id": SPEC_ID, "steps": steps}


def simulate_peers(key: int, plaintexts: list[int]) -> dict:
    """用本地 A/B 两种实现完成同密钥、双向互解；不代表真实跨组验收。"""
    validate_integer(key, 10, "密钥")
    if not isinstance(plaintexts, list) or not 1 <= len(plaintexts) <= 256:
        raise ValueError("个人模拟需要 1–256 条明文")
    key_bits = bits(key, 10)
    rows = []
    for plaintext in plaintexts:
        validate_integer(plaintext, 8, "明文")
        plain_bits = bits(plaintext)
        a_ciphertext = bits(encrypt_block(plaintext, key))
        b_ciphertext = peer_transform(plain_bits, key_bits)
        b_decrypted = peer_transform(a_ciphertext, key_bits, decrypt=True)
        a_decrypted = bits(decrypt_block(int(b_ciphertext, 2), key))
        rows.append({"plaintext": plain_bits, "key": key_bits, "a_ciphertext": a_ciphertext,
                     "b_ciphertext": b_ciphertext, "b_decrypted": b_decrypted, "a_decrypted": a_decrypted,
                     "encrypt_equal": a_ciphertext == b_ciphertext,
                     "a_to_b_ok": b_decrypted == plain_bits, "b_to_a_ok": a_decrypted == plain_bits})
    counts = {field: sum(row[field] for row in rows) for field in ("encrypt_equal", "a_to_b_ok", "b_to_a_ok")}
    example = rows[0]

    def transfer(sender, receiver, ciphertext, decoded):
        return [{"title": f"{sender} 端加密", "actor": sender, "operation": "encrypt",
                 "input": example["plaintext"], "output": ciphertext,
                 "description": f"{sender} 端用共享的 10 位演示密钥加密 8 位明文。"},
                {"title": f"模拟信道 · {sender} → {receiver}", "actor": "channel", "operation": "transfer",
                 "input": ciphertext, "output": ciphertext,
                 "description": "本地模拟传递密文，未发送到网络或其他同学。"},
                {"title": f"{receiver} 端解密", "actor": receiver, "operation": "decrypt",
                 "input": ciphertext, "output": decoded,
                 "description": f"{receiver} 端使用自己的实现解密，核对结果是否等于原明文。"}]

    return {"simulation": True, "implementation_a": "A 端 · 整数位运算（sdes.core）",
            "implementation_b": "B 端 · 独立字符串实现（sdes.peer）", "spec_id": SPEC_ID,
            "notice": "个人完成的双实现模拟实验；未进行真人跨组测试，不冒充小组实验结果。",
            "passed": all(value == len(rows) for value in counts.values()), "total": len(rows),
            "rows": rows, "counts": counts,
            "demo": {"plaintext": example["plaintext"], "key": key_bits, "ciphertext": example["a_ciphertext"],
                     "a_to_b": transfer("A", "B", example["a_ciphertext"], example["b_decrypted"]),
                     "b_to_a": transfer("B", "A", example["b_ciphertext"], example["a_decrypted"])}}
