import copy
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from sdes.core import (IP, IP_INVERSE, SBOX2, decrypt_ascii, decrypt_block, encrypt_ascii,
                       encrypt_block, generate_subkeys, parse_bits, permute, substitute, trace_block)
from sdes.exchange import make_exchange, verify_exchange
from sdes.experiments import brute_force, collision_analysis
from sdes.server import Handler, dispatch
from tests.reference_sdes import reference_keys, reference_transform


class CoreTests(unittest.TestCase):
    def test_known_vectors_and_key_schedule(self):
        self.assertEqual(generate_subkeys(642), (0b10100100, 0b01000011))
        for plaintext, key, ciphertext in [(215, 642, 140), (0, 0, 240), (255, 1023, 15)]:
            self.assertEqual(encrypt_block(plaintext, key), ciphertext)
            self.assertEqual(decrypt_block(ciphertext, key), plaintext)

    def test_course_specific_sbox2(self):
        # 输入 1000：首尾位 10 选择第 3 行，中间位 00 选择第 1 列，应输出 3。
        self.assertEqual(substitute(0b1000, SBOX2), 3)
        self.assertEqual(substitute(0b1110, SBOX2), 2)

    def test_all_subkeys_against_independent_reference(self):
        for key in range(1024):
            self.assertEqual(generate_subkeys(key), tuple(int(value, 2) for value in reference_keys(key)))

    def test_exhaustive_cipher_and_roundtrip(self):
        # 穷尽 1024 × 256，既核对独立算法又检查每个密钥下的双射和解密。
        for key in range(1024):
            ciphertexts = set()
            for plaintext in range(256):
                ciphertext = encrypt_block(plaintext, key)
                self.assertEqual(ciphertext, reference_transform(plaintext, key), (plaintext, key))
                self.assertEqual(decrypt_block(ciphertext, key), plaintext, (plaintext, key))
                ciphertexts.add(ciphertext)
            self.assertEqual(len(ciphertexts), 256)

    def test_inverse_permutation(self):
        for value in range(256):
            self.assertEqual(permute(permute(value, 8, IP), 8, IP_INVERSE), value)

    def test_trace_both_directions(self):
        for key in (0, 642, 1023):
            for plaintext in (0, 8, 127, 215, 255):
                ciphertext = encrypt_block(plaintext, key)
                self.assertEqual(int(trace_block(plaintext, key)["result"], 2), ciphertext)
                self.assertEqual(int(trace_block(ciphertext, key, True)["result"], 2), plaintext)

    def test_reject_invalid_inputs(self):
        for value in ("", "101", "000000002", " 00000000", "００００００００", None, 0):
            with self.assertRaises(ValueError):
                parse_bits(value, 8)
        for value in (-1, 256, True, 1.5, "0"):
            with self.assertRaises(ValueError):
                encrypt_block(value, 0)
            with self.assertRaises(ValueError):
                decrypt_block(value, 0)
        for key in (-1, 1024, False, "1010000010"):
            with self.assertRaises(ValueError):
                generate_subkeys(key)

    def test_ascii_roundtrip_full_range_and_empty(self):
        for text in ("", "This is a test", "a\na\t\x00", "".join(map(chr, range(128)))):
            ciphertext = encrypt_ascii(text, 642)
            self.assertEqual(len(ciphertext), len(text))
            self.assertEqual(decrypt_ascii(ciphertext, 642), text)

    def test_ascii_reject_non_ascii(self):
        for text in ("中文", "é", "😀"):
            with self.assertRaises(ValueError):
                encrypt_ascii(text, 642)
        with self.assertRaises(ValueError):
            decrypt_ascii(bytes([encrypt_block(255, 642)]), 642)


class ExperimentTests(unittest.TestCase):
    def test_brute_force_all_candidates_and_convergence(self):
        pairs = [(value, encrypt_block(value, 642)) for value in (0, 1, 8)]
        result = brute_force(pairs)
        self.assertEqual(result["keys"], ["1010000010"])
        self.assertEqual(result["prefix_counts"], [4, 2, 1])
        self.assertEqual(result["checked"], 1024)
        self.assertEqual(len(result["samples"]), 33)
        self.assertEqual([row["checked"] for row in result["samples"]], list(range(0, 1025, 32)))
        elapsed = [row["elapsed_ms"] for row in result["samples"]]
        self.assertEqual(elapsed, sorted(elapsed))
        self.assertEqual(brute_force(pairs[:1])["count"], 4)

    def test_brute_force_impossible_and_duplicate_pairs(self):
        self.assertEqual(brute_force([(0, 14), (0, 15)])["count"], 0)
        self.assertEqual(brute_force([(0, 14), (0, 14)])["prefix_counts"], [4, 4])
        for pairs in ([], [(0, 14)] * 257, [(0, 256)], [(0,) ]):
            with self.assertRaises(ValueError):
                brute_force(pairs)

    def test_collision_histogram_and_example(self):
        for plaintext in (0, 1, 127, 255):
            result = collision_analysis(plaintext)
            self.assertEqual(sum(int(size) * count for size, count in result["histogram"].items()), 1024)
            self.assertEqual(sum(result["histogram"].values()), result["distinct_ciphertexts"])
            self.assertGreater(result["collision_groups"], 0)
            ciphertext = int(result["example"]["ciphertext"], 2)
            keys = result["example"]["keys"]
            self.assertGreater(len(set(keys)), 1)
            for key in keys:
                self.assertEqual(encrypt_block(plaintext, int(key, 2)), ciphertext)

    def test_exchange_good_bad_and_mismatched_spec(self):
        document = make_exchange(642, [0, 1, 8, 215, 255])
        self.assertTrue(verify_exchange(document)["passed"])
        tampered = copy.deepcopy(document)
        tampered["vectors"][0]["ciphertext"] = "00000000"
        result = verify_exchange(tampered)
        self.assertFalse(result["passed"])
        self.assertFalse(result["results"][0]["encrypt_ok"])
        self.assertFalse(result["results"][0]["decrypt_ok"])
        for invalid in ({}, {**document, "spec_id": "other"}, {**document, "vectors": []}):
            with self.assertRaises(ValueError):
                verify_exchange(invalid)


class InterfaceTests(unittest.TestCase):
    def test_dispatch_valid_and_invalid_requests(self):
        result = dispatch("/api/block", {"operation": "encrypt", "block": "11010111", "key": "1010000010"})
        self.assertEqual(result["result"], "10001100")
        result = dispatch("/api/ascii", {"operation": "encrypt", "text": "This is a test", "key": "1010000010"})
        decoded = dispatch("/api/ascii", {"operation": "decrypt", "text": result["hex"], "key": "1010000010"})
        self.assertEqual(decoded["text"], "This is a test")
        for path, payload in [("/api/block", {}), ("/api/brute", {"pairs": "oops"}),
                              ("/api/ascii", {"operation": "decrypt", "key": "1010000010", "text": "gg"}),
                              ("/api/block", []), ("/api/unknown", {})]:
            with self.assertRaises(ValueError):
                dispatch(path, payload)

    def test_http_static_api_errors_and_origin(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            for resource in ("/", "/style.css", "/app.js"):
                connection.request("GET", resource)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(response.read())
            connection.request("GET", "/../README.md")
            response = connection.getresponse()
            self.assertEqual(response.status, 404)
            response.read()
            connection.request("POST", "/api/block", json.dumps({"operation": "encrypt", "block": "11010111", "key": "1010000010"}))
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["result"], "10001100")
            connection.request("POST", "/api/block", "{bad}")
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
            connection.request("POST", "/api/block", "{}", {"Origin": "https://example.invalid"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
