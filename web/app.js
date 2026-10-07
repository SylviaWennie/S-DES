"use strict";
const $ = (id) => document.getElementById(id);
let blockResult = null;
let blockOperation = "encrypt";
let asciiCiphertext = null;
let timingSamples = [];
let chartFrame = null;
let simulationResult = null;
let simulationRow = 0;
let asciiPlayer = null;

function showError(error) {
  $("notice").textContent = error.message || String(error);
  $("notice").hidden = false;
}

async function api(path, payload) {
  const response = await fetch(`/api/${path}`, {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}

function formAction(id, action) {
  $(id).addEventListener("submit", async (event) => {
    event.preventDefault();
    $("notice").hidden = true;
    const buttons = [...$(id).querySelectorAll("button")];
    buttons.forEach((button) => { button.disabled = true; });
    try { await action(); } catch (error) { showError(error); }
    finally { buttons.forEach((button) => { button.disabled = false; }); }
  });
}

const tabs = [...document.querySelectorAll("[data-tab]")];
function selectTab(tab) {
  window.SDESVisuals.pauseAll();
  for (const item of tabs) {
    const active = item === tab;
    item.setAttribute("aria-selected", String(active));
    item.tabIndex = active ? 0 : -1;
    $(`panel-${item.dataset.tab}`).hidden = !active;
  }
  $("notice").hidden = true;
  if (tab.dataset.tab === "brute" && timingSamples.length) drawChart(1);
}
tabs.forEach((tab, index) => {
  tab.tabIndex = index === 0 ? 0 : -1;
  tab.addEventListener("click", () => selectTab(tab));
  tab.addEventListener("keydown", (event) => {
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") next = (index + tabs.length - 1) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next !== undefined) { event.preventDefault(); selectTab(tabs[next]); tabs[next].focus(); }
  });
});

function renderRounds(result) {
  const container = $("round-trace");
  container.className = "rounds";
  container.replaceChildren();
  for (const round of result.rounds) {
    const section = document.createElement("div");
    section.className = "round";
    const title = document.createElement("h4");
    title.textContent = `ROUND ${round.round} · 子密钥 ${round.subkey}`;
    section.append(title);
    const list = document.createElement("dl");
    for (const [label, value] of [["轮输入", round.input], ["EP 扩展", round.ep],
      ["与子密钥异或", round.xor], ["S-box1 / S-box2", `${round.sbox1} / ${round.sbox2}`],
      ["P4 置换", round.p4], ["轮输出", round.output]]) {
      const term = document.createElement("dt"), detail = document.createElement("dd");
      term.textContent = label; detail.textContent = value; list.append(term, detail);
    }
    section.append(list); container.append(section);
  }
}

formAction("basic-form", async () => {
  const operation = $("operation").value;
  const payload = {operation, block: $("block").value, key: $("key").value};
  const [result, visual] = await Promise.all([api("block", payload), api("visual", payload)]);
  $("cipher-visual").dataset.result = visual.result;
  window.SDESVisuals.createPlayer($("cipher-visual"), visual.steps);
  blockResult = result.result;
  blockOperation = operation;
  $("block-result").textContent = result.result;
  $("result-direction").textContent = operation === "encrypt" ? "密文 · 8 bit" : "明文 · 8 bit";
  $("k1").textContent = result.k1;
  $("k2").textContent = result.k2;
  $("key-trace").textContent = `P10: ${result.p10} → LS-1: ${result.ls1} → 继续 LS-2: ${result.ls2}\nIP: ${result.ip} · SW: ${result.swap}`;
  renderRounds(result);
});

$("use-result").addEventListener("click", () => {
  if (blockResult === null) return showError(new Error("请先运行一次加密或解密"));
  $("block").value = blockResult;
  $("operation").value = blockOperation === "encrypt" ? "decrypt" : "encrypt";
});

function downloadJson(document, filename = "sdes-exchange.json") {
  const url = URL.createObjectURL(new Blob([JSON.stringify(document, null, 2) + "\n"], {type: "application/json"}));
  const link = window.document.createElement("a");
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

formAction("export-form", async () => {
  const document = await api("export", {key: $("exchange-key").value, plaintexts: $("exchange-plaintexts").value});
  $("exchange-json").value = JSON.stringify(document, null, 2);
  downloadJson(document);
});

function renderSimulationPlayer() {
  if (!simulationResult) return;
  const row = simulationResult.rows[simulationRow];
  const direction = $("simulation-direction").value;
  const forward = direction === "a_to_b";
  const sender = forward ? "A" : "B", receiver = forward ? "B" : "A";
  const ciphertext = forward ? row.a_ciphertext : row.b_ciphertext;
  const restored = forward ? row.b_decrypted : row.a_decrypted;
  const steps = [
    {id: "encrypt", kind: "transfer", title: `${sender} 端加密`, input: row.plaintext, output: ciphertext,
      description: `模拟端 ${sender} 使用共享演示密钥 ${row.key}，独立完成加密。`},
    {id: "transfer", kind: "transfer", title: `模拟信道 · ${sender} → ${receiver}`, input: ciphertext, output: ciphertext,
      description: "在本机模拟信道中传递密文，不进行真实网络通信。"},
    {id: "decrypt", kind: "transfer", title: `${receiver} 端解密`, input: ciphertext, output: restored,
      description: `模拟端 ${receiver} 使用自己的实现解密；与原明文 ${row.plaintext} 对照。`},
  ];
  window.SDESVisuals.createPlayer($("simulation-visual"), steps, {direction, ciphertext, key: row.key});
  $("simulation-visual").dataset.result = restored;
  $("simulation-table").querySelectorAll("tbody tr").forEach((element, index) => {
    element.setAttribute("aria-selected", String(index === simulationRow));
  });
}

formAction("simulation-form", async () => {
  const result = await api("simulate", {key: $("simulation-key").value, plaintexts: $("simulation-plaintexts").value});
  simulationResult = result;
  simulationRow = 0;
  const counts = [result.counts.encrypt_equal, result.counts.a_to_b_ok, result.counts.b_to_a_ok];
  $("simulation-summary").querySelectorAll("strong").forEach((element, index) => { element.textContent = `${counts[index]} / ${result.total}`; });
  $("simulation-result").textContent = `${result.passed ? "全部通过" : "存在不一致"} · 个人 A/B 模拟，共 ${result.total} 条数据。点击任一行“演示”查看该样本的双向过程。`;
  const body = $("simulation-table").querySelector("tbody");
  body.replaceChildren();
  result.rows.forEach((row, index) => {
    const tr = document.createElement("tr");
    for (const value of [row.plaintext, row.a_ciphertext, row.b_ciphertext]) {
      const cell = document.createElement("td"); cell.textContent = value; tr.append(cell);
    }
    const outcome = document.createElement("td");
    outcome.className = "simulation-outcome";
    outcome.textContent = `B: ${row.b_decrypted} ${row.a_to_b_ok ? "✓" : "×"}\nA: ${row.a_decrypted} ${row.b_to_a_ok ? "✓" : "×"}`;
    tr.append(outcome);
    const cell = document.createElement("td"), button = document.createElement("button");
    button.type = "button"; button.textContent = "演示"; button.setAttribute("aria-label", `演示第 ${index + 1} 条明文 ${row.plaintext}`);
    button.addEventListener("click", () => { simulationRow = index; renderSimulationPlayer(); });
    cell.append(button); tr.append(cell); body.append(tr);
  });
  renderSimulationPlayer();
  $("simulation-download").disabled = false;
});
$("simulation-direction").addEventListener("change", renderSimulationPlayer);
$("simulation-all").addEventListener("click", () => {
  $("simulation-plaintexts").value = Array.from({length: 256}, (_, index) => index.toString(2).padStart(8, "0")).join("\n");
});
$("simulation-download").addEventListener("click", () => {
  if (simulationResult) downloadJson(simulationResult, "sdes-personal-simulation.json");
});
$("exchange-file").addEventListener("change", async () => {
  try {
    const file = $("exchange-file").files[0];
    if (!file) return;
    if (file.size > 60000) throw new Error("交换文件不能超过 60 KB");
    $("exchange-json").value = await file.text();
  } catch (error) { showError(error); }
});
formAction("verify-form", async () => {
  let document;
  try { document = JSON.parse($("exchange-json").value.replace(/^\uFEFF/, "")); }
  catch { throw new Error("请输入合法的 JSON 交换文件"); }
  const result = await api("verify", {document});
  $("verify-result").textContent = `${result.passed ? "全部通过" : "存在不一致"} · 共 ${result.total} 条向量\n` + result.results.map((row) =>
    `#${row.index} 加密 ${row.encrypt_ok ? "✓" : "×"} / 解密 ${row.decrypt_ok ? "✓" : "×"} · 本机 C=${row.actual_ciphertext} P=${row.actual_plaintext}`).join("\n");
});
formAction("ascii-form", async () => {
  const operation = $("ascii-operation").value;
  const key = $("ascii-key").value, input = $("ascii-text").value;
  const result = await api("ascii", {operation, key, text: input});
  let plainText, restoredText, cipherBytes;
  if (operation === "encrypt") {
    asciiCiphertext = result.hex;
    $("ascii-result").textContent = `${result.bytes} 字节\n\n十六进制密文\n${result.hex || "（空串）"}\n\n二进制密文\n${result.binary || "（空串）"}\n\nASCII 明文分组\n${result.plaintext_binary || "（空串）"}`;
    const restored = await api("ascii", {operation: "decrypt", key, text: result.hex});
    plainText = input; restoredText = restored.text;
    cipherBytes = result.binary ? result.binary.split(" ") : [];
  } else {
    $("ascii-result").textContent = `${result.bytes} 字节\n\n恢复的文本\n${result.text || "（空串）"}\n\n转义表示（保留控制字符）\n${JSON.stringify(result.text)}`;
    plainText = result.text; restoredText = result.text;
    cipherBytes = (input.replace(/\s/g, "").match(/../g) || []).map((value) => parseInt(value, 16).toString(2).padStart(8, "0"));
  }
  const displayCharacter = (character) => character === " " ? "空格" : JSON.stringify(character);
  const steps = cipherBytes.slice(0, 128).map((ciphertext, index) => ({id: `byte-${index}`, kind: "byte",
    title: `字节 ${index + 1} · ${displayCharacter(plainText[index])}`, byte_index: index, key, operation,
    character: displayCharacter(plainText[index]), plaintext: plainText.charCodeAt(index).toString(2).padStart(8, "0"),
    ciphertext, restored: displayCharacter(restoredText[index]),
    description: `第 ${index + 1} 个字节：ASCII ${plainText.charCodeAt(index)}，密文 ${ciphertext}，恢复 ${displayCharacter(restoredText[index])}。`}));
  asciiPlayer = window.SDESVisuals.createPlayer($("ascii-visual"), steps);
  $("ascii-inspect-byte").disabled = !steps.length;
  $("ascii-inspect-byte").textContent = `展开当前字节的${operation === "encrypt" ? "加密" : "解密"}过程 →`;
  $("ascii-visual-note").textContent = `全部 ${result.bytes} 个字节已处理。${result.bytes > 128 ? "动画展示前 128 个字节，完整结果保留在上方。" : "可逐字节播放或选择任意字节查看。"}`;
});
$("ascii-inspect-byte").addEventListener("click", () => {
  const step = asciiPlayer?.getStep();
  if (!step) return;
  $("block").value = step.operation === "decrypt" ? step.ciphertext : step.plaintext;
  $("key").value = step.key; $("operation").value = step.operation;
  selectTab($("tab-basic")); $("basic-form").requestSubmit();
});
$("ascii-refill").addEventListener("click", () => {
  if (asciiCiphertext === null) return showError(new Error("请先加密一段 ASCII 文本"));
  $("ascii-text").value = asciiCiphertext;
  $("ascii-operation").value = "decrypt";
});

async function loadBruteExample() {
  const data = await api("export", {key: "1010000010", plaintexts: "00000000\n00000001\n00001000"});
  $("pairs").value = data.vectors.map((row) => `${row.plaintext} ${row.ciphertext}`).join("\n");
}
$("brute-example").addEventListener("click", () => loadBruteExample().catch(showError));
formAction("brute-form", async () => {
  const result = await api("brute", {pairs: $("pairs").value});
  const values = $("brute-summary").querySelectorAll("strong");
  [result.count, result.elapsed_ms.toFixed(3), result.checked].forEach((value, index) => { values[index].textContent = value; });
  $("brute-keys").textContent = result.keys.length ? result.keys.join("  ") : "无匹配密钥。检查数据是否使用相同密钥或是否存在抄写错误。";
  $("convergence").textContent = "候选收敛：1024 → " + result.prefix_counts.map((count, index) => `${count}（前 ${index + 1} 对）`).join(" → ");
  window.SDESVisuals.renderConvergence($("candidate-visual"), result.prefix_counts);
  timingSamples = result.samples;
  $("chart-description").textContent = `共 ${result.samples.length} 个实测采样点；枚举 1024 个密钥，总耗时 ${result.elapsed_ms.toFixed(3)} ms，最终找到 ${result.count} 个候选。重复运行会受机器负载与缓存影响。`;
  replayChart();
});

function drawChart(progress) {
  const canvas = $("timing-chart"), context = canvas.getContext("2d");
  const width = Math.max(280, canvas.clientWidth), height = 240;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio;
  context.scale(ratio, ratio);
  const left = 56, right = width - 20, top = 26, bottom = height - 36;
  const maximum = Math.max(0.001, timingSamples.at(-1)?.elapsed_ms || 1) * 1.1;
  context.font = "11px Segoe UI";
  for (let index = 0; index <= 4; index++) {
    const y = bottom - (bottom - top) * index / 4;
    context.strokeStyle = "#e4ebef"; context.beginPath(); context.moveTo(left, y); context.lineTo(right, y); context.stroke();
    context.fillStyle = "#67798a"; context.fillText((maximum * index / 4).toFixed(2), 4, y + 4);
    const x = left + (right - left) * index / 4;
    context.fillText(String(index * 256), x - 12, bottom + 22);
  }
  context.fillText("累计 ms", 4, 13); context.fillText("已枚举密钥", right - 65, height - 2);
  context.beginPath(); context.strokeStyle = "#256581"; context.lineWidth = 2.5;
  const visible = Math.max(1, Math.ceil(timingSamples.length * progress));
  timingSamples.slice(0, visible).forEach((point, index) => {
    const x = left + (right - left) * point.checked / 1024;
    const y = bottom - (bottom - top) * point.elapsed_ms / maximum;
    if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
  });
  context.stroke();
}
function replayChart() {
  cancelAnimationFrame(chartFrame);
  if (!timingSamples.length) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return drawChart(1);
  const started = performance.now();
  const frame = (now) => {
    const progress = Math.min(1, (now - started) / 1200);
    drawChart(progress);
    if (progress < 1) chartFrame = requestAnimationFrame(frame);
  };
  chartFrame = requestAnimationFrame(frame);
}
$("replay-chart").addEventListener("click", replayChart);
window.addEventListener("resize", () => { if (timingSamples.length && !$("panel-brute").hidden) drawChart(1); });

formAction("collision-form", async () => {
  const result = await api("collision", {plaintext: $("collision-plaintext").value});
  $("collision-result").textContent = `固定明文：${result.plaintext}\n不同密文数：${result.distinct_ciphertexts} / 256\n有碰撞的密文组：${result.collision_groups}\n仅一个密钥的密文组：${result.singleton_groups}\n单组最多密钥：${result.max_keys_per_ciphertext}\n\n碰撞实例 · 密文 ${result.example.ciphertext}\n密钥：${result.example.keys.join("  ")}\n\n分布（每组密钥数量 → 这样的密文组数）\n` + Object.entries(result.histogram).map(([count, frequency]) => `${count} 把 → ${frequency} 组`).join("\n");
  window.SDESVisuals.renderCollision($("collision-visual"), result);
});
loadBruteExample().catch(showError);
