# 开发手册

## 结构与取舍

Python 标准库实现算法和 HTTP 服务，原生 HTML/CSS/JavaScript 与 SVG 实现 GUI。算法是纯函数，CLI 和界面共用业务模块；个人模拟 B 端使用独立字符串算法，测试参考实现也独立书写，不复用生产常量。

| 文件 | 职责 |
| --- | --- |
| `sdes/core.py` | 置换、子密钥、轮函数、单分组、ASCII、逐轮轨迹 |
| `sdes/peer.py` | 模拟 B 端的字符串算法，不导入 A 端算法或常量 |
| `sdes/visualization.py` | 20 个实际运算图解步骤、A/B 双向交叉实验结果 |
| `sdes/experiments.py` | 全密钥枚举、多对收敛、单明文/全明文碰撞统计 |
| `sdes/exchange.py` | 交换文档生成与双向核验 |
| `sdes/server.py` | 本地 HTTP 服务、输入解析、JSON 路由 |
| `sdes/__main__.py` | `python -m sdes` 命令行 |
| `web/` | 五关 GUI，用户输入通过 `textContent` 展示 |
| `web/visuals.js` / `web/visuals.css` | SVG 置换盒、轮函数、S 盒查表、动画控制及五关实验图 |
| `tests/reference_sdes.py` | 独立字符串参考实现，仅用于测试 |
| `tests/test_visualization.py` | 逐帧数据、子密钥顺序、模拟 A/B 全空间互操作及接口校验 |
| `reports/` | 已保存的程序实验数据与验证结果 |
| `docs/` | 人工过程回顾、使用说明、实验报告与演示图示 |

1024 个密钥规模很小，采用单线程穷举，计时含采样成本。课程允许多线程但并不强制；Python CPU 密集线程不保证提速，当前工作量也不值得引入进程调度复杂性。

## Python 接口

```python
from sdes import encrypt_block, decrypt_block, generate_subkeys
from sdes.core import trace_block, encrypt_ascii, decrypt_ascii
from sdes.experiments import brute_force, collision_analysis, full_collision_study
from sdes.visualization import visual_trace, simulate_peers

key = int("1010000010", 2)
ciphertext = encrypt_block(int("11010111", 2), key)  # 140
assert decrypt_block(ciphertext, key) == 215
assert decrypt_ascii(encrypt_ascii("This is a test", key), key) == "This is a test"
steps = visual_trace(int("11010111", 2), key)["steps"]
simulation = simulate_peers(key, [0, 1, 8, 215, 255])
```

| 函数 | 输入 / 返回 |
| --- | --- |
| `encrypt_block(plaintext, key)` / `decrypt_block(ciphertext, key)` | 数据为 0–255 整数，key 为 0–1023；返回 0–255。拒绝布尔值 |
| `generate_subkeys(key)` | 返回 `(K1, K2)`，均为 0–255 整数 |
| `parse_bits(value, width, name)` | 严格固定宽度 0/1 字符串 → 整数 |
| `trace_block(block, key, decrypt=False)` | 返回密钥扩展、IP、SW、两轮中间值与最终二进制字符串 |
| `visual_trace(block, key, operation="encrypt")` | 输入整数分组与密钥；返回 `mode/input/key/result/k1/k2/spec_id/steps`，模式为 `encrypt` 或 `decrypt` |
| `sdes.peer.transform(block, key, decrypt=False)` | B 端独立计算；输入 8 位 / 10 位字符串，返回 8 位字符串 |
| `simulate_peers(key, plaintexts)` | 整数密钥与 1–256 条整数明文列表；返回 A/B 各自密文、双向解密、逐条检查与汇总 |
| `encrypt_ascii(text, key)` / `decrypt_ascii(data, key)` | ASCII `str` → `bytes` / `bytes` → ASCII `str` |
| `brute_force(pairs)` | 1–256 对整数 `(P,C)` → 全部密钥、前缀候选数、采样和毫秒数 |
| `collision_analysis(plaintext)` | 密文组数量、组大小直方图、可复核碰撞实例 |
| `full_collision_study()` | 全部 256 个明文的摘要和逐条统计 |
| `make_exchange(key, plaintexts)` | 公开演示 JSON 对象，包含测试密钥 |
| `verify_exchange(document)` | `passed`、`total` 和逐条双向核验结果 |

参数错误通常抛出 `ValueError`；CLI 打印简短错误并返回退出码 2。互测不一致返回退出码 1，成功返回 0。

## HTTP 接口

所有 POST 使用 JSON，成功返回 200，输入错误返回 400 和 `{"error":"说明"}`。服务限定 loopback Host，并拒绝非本机同源 Origin。静态文件仅允许服务显式列出的路径。请求体上限 64 KiB，不记录请求参数。

| 路由 | 字段 |
| --- | --- |
| `/api/block` | `operation`: encrypt/decrypt；`block`: 8 位；`key`: 10 位 |
| `/api/visual` | 与 `/api/block` 相同；返回逐阶段 SVG 所需实际数据 |
| `/api/simulate` | `key`: 10 位；`plaintexts`: 每行 8 位明文，1–256 条 |
| `/api/ascii` | `operation`；`text`: ASCII 明文或十六进制密文；`key` |
| `/api/brute` | `pairs`: 每行 `明文 密文` 的字符串 |
| `/api/collision` | `plaintext`: 8 位 |
| `/api/export` | `key`；`plaintexts`: 每行 8 位明文 |
| `/api/verify` | `document`: 完整交换 JSON 对象 |

这是本机课程 GUI 的接口，不是经过生产安全加固的互联网服务。

## 图解数据与动画

`visual_trace()` 产生有序步骤：5 个密钥扩展步骤、IP、第一轮 6 步、SW、第二轮 6 步、IP⁻¹，共 20 步。每轮 6 步为 fₖ 全景、EP、子密钥异或、两个 S 盒查表、P4、左半部异或与拼接。全景概括该轮关系，其余步骤逐项展开；第二轮没有额外 SW。

| `kind` | 主要字段 | 渲染约定 |
| --- | --- | --- |
| `permutation` | `input/output/mapping/box_label`，部分含 `half_width` | 第 i 根输出连线取 `mapping[i]` 指定的输入位，使用从 1 开始的位置；EP 的重复位置保留各自连线 |
| `xor` | `left/right/output` 及操作数标签 | 每位对齐展示；左半部异或还含 `retained_right/block_output`，右半部直通 |
| `sboxes` | `input/output/boxes`；每盒含 `table/row/column` | 首尾位选行，中间位选列；高亮行列交点，拼接两个 2 位输出 |
| `round` | `left/right/ep/mixed/sbox_output/p4/subkey/subkey_name/output` | 展示 F 与 fₖ 的全景及本轮子密钥 |

图解中的 `input/output` 是计算值，`mapping` 是位置映射，两者不能混用。解密仍从同一密钥生成 K₁、K₂，但轮次顺序为 K₂、K₁。视觉代码仅绘图与播放，结果来自服务端实际运算；修改动画速度不会修改密文或算法耗时。

播放状态与计算状态分开：结果载入后停在第一阶段，用户显式播放；上一步、下一步、回到起点和阶段选择均可用于复核。图中的位置、数值与文字说明随同一阶段一起更新，不用颜色作为唯一线索。

`simulate_peers()` 的 `rows` 保留每条 `plaintext/key/a_ciphertext/b_ciphertext/b_decrypted/a_decrypted`，以及 `encrypt_equal/a_to_b_ok/b_to_a_ok` 三个布尔值。`counts` 汇总三项通过数量，`passed` 表示所有项均通过。`simulation: true` 与双方实现说明保留在结果中。`demo.a_to_b`、`demo.b_to_a` 各有加密、模拟传递、解密三帧，用于讲解第一条向量；界面可从批量记录选择其他向量回放。传递发生在本地，没有网络收发。

## 测试与数据复核

基础回归不依赖第三方库：`python -m unittest discover -v`。

覆盖全密钥子密钥对照、262,144 个独立实现对照与往返、固定密钥双射、ASCII 全范围、非法输入、矛盾明密文、交换格式及 HTTP。固定向量和参数回归共同防止“加解密互逆却用错课程 S 盒”。

新增图解测试核对置换映射、逐位异或、S 盒行列与选值、轮次衔接及解密的子密钥顺序；A/B 测试覆盖全部 1024×256 组合的密文一致与双向交叉解密。浏览器检查再核验播放控制、图形显示、仿真流程与其他关卡。实际运行状态及证据以 [实验报告](test-report.md) 为准。

发布内容只保留运行代码、必要测试、文档和实验材料。截图/动图制作工具及本地筹备文件不属于程序依赖，不随仓库上传。浏览器图解由 `web/visuals.js` 在运行时直接生成，无需预装 Node、Qt 或图形库。

完整 A/B 模拟可在 GUI 的第二关“载入 256 个明文”后运行，也可直接复核：

```bash
python -c "from sdes.visualization import simulate_peers; r = simulate_peers(642, list(range(256))); print(r['counts']); assert r['passed']"
python -m sdes verify examples/full-byte-exchange.json
python -m sdes brute examples/known-pairs.txt
```

重新生成数据时也可调用 `visual_trace()`、`full_collision_study()` 等公开函数，再使用标准库 `json` 保存返回值。记录自己的运行环境；耗时可能与已存结果不同。浏览器截图和动图属于程序验证/演示证据，不是操作者当时的人工日志。

离线统计图文案为英文以避免生成环境缺少中文字体，GUI 图解和报告正文使用中文说明。修改参数必须同步协议标识、B 端、参考实现、固定向量、图解、测试和文档，并重新核验；不要只为通过测试而修改期望值。
