import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from sdes.core import decrypt_block, encrypt_block, trace_block
from sdes.peer import transform as peer_transform
from sdes.server import Handler, dispatch
from sdes.visualization import simulate_peers, visual_trace


class VisualTraceTests(unittest.TestCase):
    def test_every_wire_and_operation_in_both_modes(self):
        """用输出数据本身重新计算各动画帧，避免图示与密码算法脱节。"""
        for key in (0, 1, 341, 642, 1023):
            for block in (0, 1, 8, 127, 140, 215, 255):
                for mode in ("encrypt", "decrypt"):
                    with self.subTest(key=key, block=block, mode=mode):
                        visual = visual_trace(block, key, mode)
                        expected = decrypt_block(block, key) if mode == "decrypt" else encrypt_block(block, key)
                        self.assertEqual(int(visual["result"], 2), expected)
                        self.assertEqual(visual["result"], trace_block(block, key, mode == "decrypt")["result"])
                        self.assertEqual(len(visual["steps"]), 20)
                        self.assertEqual(len({step["id"] for step in visual["steps"]}), 20)
                        for step in visual["steps"]:
                            if step["kind"] == "permutation":
                                self.assertEqual(step["output"], "".join(step["input"][position - 1] for position in step["mapping"]))
                            elif step["kind"] == "xor":
                                self.assertEqual(int(step["output"], 2), int(step["left"], 2) ^ int(step["right"], 2))
                                if "block_output" in step:
                                    self.assertEqual(step["block_output"], step["output"] + step["retained_right"])
                            elif step["kind"] == "sboxes":
                                self.assertEqual(step["input"], "".join(box["input"] for box in step["boxes"]))
                                self.assertEqual(step["output"], "".join(box["output"] for box in step["boxes"]))
                                for box in step["boxes"]:
                                    self.assertEqual(box["row"], int(box["input"][0] + box["input"][3], 2))
                                    self.assertEqual(box["column"], int(box["input"][1:3], 2))
                                    self.assertEqual(int(box["output"], 2), box["table"][box["row"]][box["column"]])
                            elif step["kind"] == "round":
                                self.assertEqual(step["input"], step["left"] + step["right"])
                                self.assertEqual(step["output"][4:], step["right"])
                                self.assertEqual(int(step["output"][:4], 2), int(step["left"], 2) ^ int(step["p4"], 2))
                                self.assertEqual(int(step["mixed"], 2), int(step["ep"], 2) ^ int(step["subkey"], 2))
                            else:
                                self.fail(f"未知图示类型：{step['kind']}")

    def test_stage_connections_and_key_order(self):
        for mode in ("encrypt", "decrypt"):
            visual = visual_trace(215, 642, mode)
            steps = {step["id"]: step for step in visual["steps"]}
            self.assertEqual(steps["p10"]["input"], visual["key"])
            self.assertEqual(steps["ls1"]["input"], steps["p10"]["output"])
            self.assertEqual(steps["p8-k1"]["input"], steps["ls1"]["output"])
            self.assertEqual(steps["ls2"]["input"], steps["ls1"]["output"])
            self.assertEqual(steps["p8-k2"]["input"], steps["ls2"]["output"])
            self.assertEqual(steps["p8-k1"]["output"], visual["k1"])
            self.assertEqual(steps["p8-k2"]["output"], visual["k2"])
            self.assertEqual(steps["ls1"]["half_width"], 5)
            self.assertEqual(steps["ls2"]["half_width"], 5)
            self.assertEqual(steps["ip"]["input"], visual["input"])
            self.assertEqual(steps["r1-overview"]["input"], steps["ip"]["output"])
            self.assertEqual(steps["sw"]["input"], steps["r1-overview"]["output"])
            self.assertEqual(steps["r2-overview"]["input"], steps["sw"]["output"])
            self.assertEqual(steps["ip-inverse"]["input"], steps["r2-overview"]["output"])
            key_order = ("K2", "K1") if mode == "decrypt" else ("K1", "K2")
            for index, name in enumerate(key_order, 1):
                overview = steps[f"r{index}-overview"]
                self.assertEqual(overview["subkey_name"], name)
                self.assertEqual(overview["subkey"], visual[name.lower()])
                self.assertEqual(steps[f"r{index}-ep"]["input"], overview["right"])
                self.assertEqual(steps[f"r{index}-ep"]["output"], overview["ep"])
                self.assertEqual(steps[f"r{index}-xor-key"]["output"], overview["mixed"])
                self.assertEqual(steps[f"r{index}-sboxes"]["input"], overview["mixed"])
                self.assertEqual(steps[f"r{index}-sboxes"]["output"], overview["sbox_output"])
                self.assertEqual(steps[f"r{index}-p4"]["input"], overview["sbox_output"])
                self.assertEqual(steps[f"r{index}-p4"]["output"], overview["p4"])
                self.assertEqual(steps[f"r{index}-xor-left"]["block_output"], overview["output"])

    def test_assignment_tables_in_trace(self):
        steps = {step["id"]: step for step in visual_trace(215, 642)["steps"]}
        expected = {"p10": [3, 5, 2, 7, 4, 10, 1, 9, 8, 6],
                    "p8-k1": [6, 3, 7, 4, 8, 5, 10, 9],
                    "ip": [2, 6, 3, 1, 4, 8, 5, 7],
                    "ip-inverse": [4, 1, 3, 5, 7, 2, 8, 6],
                    "r1-ep": [4, 1, 2, 3, 2, 3, 4, 1], "r1-p4": [2, 4, 3, 1]}
        for name, table in expected.items():
            self.assertEqual(steps[name]["mapping"], table)
        self.assertEqual(steps["r1-sboxes"]["boxes"][1]["table"],
                         [[0, 1, 2, 3], [2, 3, 1, 0], [3, 0, 1, 2], [2, 1, 0, 3]])


class PeerSimulationTests(unittest.TestCase):
    def test_full_key_plaintext_space_both_implementations(self):
        # 1024 × 256：同文同钥加密一致、A→B 解密、B→A 解密三项全部覆盖。
        for key in range(1024):
            key_bits = f"{key:010b}"
            for plaintext in range(256):
                plain_bits = f"{plaintext:08b}"
                a_ciphertext = encrypt_block(plaintext, key)
                b_ciphertext = peer_transform(plain_bits, key_bits)
                self.assertEqual(a_ciphertext, int(b_ciphertext, 2), (plaintext, key))
                self.assertEqual(peer_transform(f"{a_ciphertext:08b}", key_bits, True), plain_bits, (plaintext, key))
                self.assertEqual(decrypt_block(int(b_ciphertext, 2), key), plaintext, (plaintext, key))

    def test_simulation_rows_and_bidirectional_transfers(self):
        result = simulate_peers(642, [0, 1, 8, 215, 255])
        self.assertTrue(result["simulation"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["counts"], {"encrypt_equal": 5, "a_to_b_ok": 5, "b_to_a_ok": 5})
        for row in result["rows"]:
            self.assertEqual(row["a_ciphertext"], row["b_ciphertext"])
            self.assertEqual(row["plaintext"], row["a_decrypted"])
            self.assertEqual(row["plaintext"], row["b_decrypted"])
        for direction, actors in (("a_to_b", ["A", "channel", "B"]), ("b_to_a", ["B", "channel", "A"])):
            transfer = result["demo"][direction]
            self.assertEqual([step["actor"] for step in transfer], actors)
            self.assertEqual(transfer[0]["input"], result["demo"]["plaintext"])
            self.assertEqual(transfer[0]["output"], transfer[1]["input"])
            self.assertEqual(transfer[1]["input"], transfer[1]["output"])
            self.assertEqual(transfer[1]["output"], transfer[2]["input"])
            self.assertEqual(transfer[2]["output"], result["demo"]["plaintext"])

    def test_invalid_peer_and_simulation_inputs(self):
        for block, key in [(None, "0000000000"), ("00000000", None), ("2" * 8, "0" * 10), ("0" * 7, "0" * 10)]:
            with self.assertRaises(ValueError):
                peer_transform(block, key)
        for key, plaintexts in [(False, [0]), (1024, [0]), (0, []), (0, [0] * 257), (0, [256]), (0, [True]), (0, "0")]:
            with self.assertRaises(ValueError):
                simulate_peers(key, plaintexts)
        with self.assertRaises(ValueError):
            visual_trace(0, 0, "other")


class VisualInterfaceTests(unittest.TestCase):
    def test_dispatch_inputs_and_results(self):
        self.assertEqual(dispatch("/api/visual", {"block": "11010111", "key": "1010000010", "operation": "encrypt"})["result"], "10001100")
        self.assertTrue(dispatch("/api/simulate", {"key": "1010000010", "plaintexts": "00000000\n00000001\n"})["passed"])
        bad_requests = [("/api/visual", {}), ("/api/visual", []),
                        ("/api/visual", {"block": "00000000", "key": "0000000000", "operation": "bad"}),
                        ("/api/visual", {"block": "000000000", "key": "0000000000", "operation": "encrypt"}),
                        ("/api/simulate", {"key": "0000000000", "plaintexts": []}),
                        ("/api/simulate", {"key": "0000000000", "plaintexts": ""}),
                        ("/api/simulate", {"key": "0000000000", "plaintexts": "00000000\nwrong"}),
                        ("/api/simulate", {"key": "0000000000", "plaintexts": "00000000\n" * 257})]
        for path, payload in bad_requests:
            with self.subTest(path=path, payload=payload):
                with self.assertRaises(ValueError):
                    dispatch(path, payload)

    def test_http_visual_routes_and_errors(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            for path, payload, status in [
                ("/api/visual", {"block": "10001100", "key": "1010000010", "operation": "decrypt"}, 200),
                ("/api/simulate", {"key": "1010000010", "plaintexts": "11010111"}, 200),
                ("/api/visual", {}, 400), ("/api/simulate", {}, 400)]:
                connection.request("POST", path, json.dumps(payload))
                response = connection.getresponse()
                self.assertEqual(response.status, status)
                result = json.loads(response.read())
                if path == "/api/visual" and status == 200:
                    self.assertEqual(result["result"], "11010111")
                if path == "/api/simulate" and status == 200:
                    self.assertEqual(result["rows"][0]["b_ciphertext"], "10001100")
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
