"""测试用的独立字符串实现：不导入生产模块，也不复用其常量或函数。

这只是同一作者的第二种实现，不能冒充另一个小组的程序。
"""


def pick(sequence, positions):
    return "".join(sequence[position - 1] for position in positions)


def xor(first, second):
    return "".join("0" if left == right else "1" for left, right in zip(first, second))


def reference_keys(key):
    permuted = pick(f"{key:010b}", [3, 5, 2, 7, 4, 10, 1, 9, 8, 6])
    left, right = permuted[:5], permuted[5:]
    left, right = left[1:] + left[:1], right[1:] + right[:1]
    first = pick(left + right, [6, 3, 7, 4, 8, 5, 10, 9])
    left, right = left[2:] + left[:2], right[2:] + right[:2]
    second = pick(left + right, [6, 3, 7, 4, 8, 5, 10, 9])
    return first, second


def reference_round(block, key):
    left, right = block[:4], block[4:]
    mixed = xor(pick(right, [4, 1, 2, 3, 2, 3, 4, 1]), key)
    boxes = [[[1, 0, 3, 2], [3, 2, 1, 0], [0, 2, 1, 3], [3, 1, 0, 2]],
             [[0, 1, 2, 3], [2, 3, 1, 0], [3, 0, 1, 2], [2, 1, 0, 3]]]
    output = ""
    for part, box in zip((mixed[:4], mixed[4:]), boxes):
        row = int(part[0] + part[3], 2)
        column = int(part[1:3], 2)
        output += f"{box[row][column]:02b}"
    return xor(left, pick(output, [2, 4, 3, 1])) + right


def reference_transform(block, key, decrypt=False):
    keys = reference_keys(key)
    if decrypt:
        keys = keys[::-1]
    state = pick(f"{block:08b}", [2, 6, 3, 1, 4, 8, 5, 7])
    state = reference_round(state, keys[0])
    state = reference_round(state[4:] + state[:4], keys[1])
    return int(pick(state, [4, 1, 3, 5, 7, 2, 8, 6]), 2)
