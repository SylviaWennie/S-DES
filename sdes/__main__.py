"""脚本化运行和小组交叉测试入口。"""

import argparse
import json
from pathlib import Path

from .core import bits, decrypt_block, encrypt_block, parse_bits, trace_block
from .exchange import make_exchange, verify_exchange
from .experiments import brute_force, collision_analysis
from .server import parse_pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="课程 S-DES 命令行工具")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("encrypt", "decrypt", "trace"):
        command = commands.add_parser(name)
        command.add_argument("block")
        command.add_argument("key")
    brute = commands.add_parser("brute")
    brute.add_argument("pairs_file", type=Path, help="UTF-8 文件，每行：8位明文 8位密文")
    collision = commands.add_parser("collision")
    collision.add_argument("plaintext")
    export = commands.add_parser("export")
    export.add_argument("key")
    export.add_argument("plaintexts", nargs="+")
    verify = commands.add_parser("verify")
    verify.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        if args.command in ("encrypt", "decrypt", "trace"):
            block, key = parse_bits(args.block, 8), parse_bits(args.key, 10, "密钥")
            if args.command == "trace":
                result = trace_block(block, key)
            else:
                function = encrypt_block if args.command == "encrypt" else decrypt_block
                result = {"result": bits(function(block, key))}
        elif args.command == "brute":
            result = brute_force(parse_pairs(args.pairs_file.read_text(encoding="utf-8-sig")))
        elif args.command == "collision":
            result = collision_analysis(parse_bits(args.plaintext, 8))
        elif args.command == "export":
            result = make_exchange(parse_bits(args.key, 10), [parse_bits(value, 8) for value in args.plaintexts])
        else:
            result = verify_exchange(json.loads(args.file.read_text(encoding="utf-8-sig")))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "verify" and not result["passed"]:
            raise SystemExit(1)
    except (ValueError, OSError) as error:
        parser.exit(2, f"输入错误：{error}\n")


if __name__ == "__main__":
    main()
