"""与课程作业参数一致的教学 S-DES。"""

from .core import decrypt_block, encrypt_block, generate_subkeys

__all__ = ["encrypt_block", "decrypt_block", "generate_subkeys"]
