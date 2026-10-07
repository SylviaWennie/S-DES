"use strict";

// SVG 只呈现后端已计算的真实中间值，不在界面中维护另一套密码算法。
window.SDESVisuals = (() => {
  const namespace = "http://www.w3.org/2000/svg";
  const players = new Set();
  const colors = ["#b45309", "#15803d", "#2563a5", "#9c3673", "#7c5aa6", "#087f8c", "#b04c36", "#66751e", "#555ca6", "#8d6137"];
  let serial = 0;

  function html(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function svgNode(parent, tag, attributes = {}, text) {
    const element = document.createElementNS(namespace, tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    parent.append(element);
    return element;
  }

  function label(parent, x, y, text, className = "viz-label", anchor = "middle") {
    return svgNode(parent, "text", {x, y, class: className, "text-anchor": anchor}, text);
  }

  function makeSvg(title, height = 490) {
    const svg = document.createElementNS(namespace, "svg");
    const id = `viz-arrow-${++serial}`;
    svg.setAttribute("viewBox", `0 0 1000 ${height}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", title);
    svg.classList.add("viz-diagram");
    svgNode(svg, "title", {}, title);
    const defs = svgNode(svg, "defs");
    const marker = svgNode(defs, "marker", {id, viewBox: "0 0 10 10", refX: 9, refY: 5,
      markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse"});
    svgNode(marker, "path", {d: "M 0 0 L 10 5 L 0 10 z", fill: "context-stroke"});
    return {svg, arrow: `url(#${id})`};
  }

  function line(parent, points, arrow, attributes = {}) {
    return svgNode(parent, "path", {d: points, fill: "none", stroke: "#639174", "stroke-width": 2,
      "marker-end": arrow, ...attributes});
  }

  function bit(parent, x, y, value, position, row, source = position, color = "#4f7c43") {
    const group = svgNode(parent, "g", {class: "viz-bit", "data-value": value, "data-position": position,
      "data-row": row, "data-source": source});
    svgNode(group, "rect", {x: x - 22, y, width: 44, height: 40, rx: 4, fill: color});
    label(group, x, y + 27, value, "viz-bit-value");
    return group;
  }

  function drawPermutation(step) {
    const {svg, arrow} = makeSvg(step.title, 460);
    const keyPhase = step.phase === "key";
    const color = keyPhase ? "#b96520" : "#527f3a";
    const start = 225, end = 920;
    const position = (index, count) => count === 1 ? (start + end) / 2 : start + index * (end - start) / (count - 1);
    const inputY = 70, outputY = 335;
    // 与作业图一致：输入位号在上，置换盒内连线，输出位号来自指定输入位置。
    svgNode(svg, "path", {d: step.input.length === step.output.length
      ? "M 60 137 H 955 Q 975 137 975 158 V 283 Q 975 304 955 304 H 60 Q 40 304 40 283 V 158 Q 40 137 60 137 Z"
      : step.input.length > step.output.length
        ? "M 40 137 H 975 L 940 304 H 75 Z" : "M 95 137 H 920 L 975 304 H 40 Z",
    fill: keyPhase ? "#fff1d2" : "#e5f0d8", stroke: color, "stroke-width": 2});
    label(svg, 130, 220, step.box_label || step.title, "viz-box-name");
    label(svg, 115, 99, "输入位值", "viz-label");
    label(svg, 115, 362, "输出位值", "viz-label");
    label(svg, 115, 410, "来源位号", "viz-label");
    const particles = [];
    step.mapping.forEach((source, index) => {
      const inputX = position(source - 1, step.input.length);
      const outputX = position(index, step.output.length);
      const path = line(svg, `M ${inputX} ${inputY + 40} L ${inputX} 147 L ${outputX} 294 L ${outputX} ${outputY - 5}`, arrow,
        {stroke: colors[(source - 1) % colors.length], "stroke-opacity": 0.68,
          class: "viz-wire", "data-source": source, "data-target": index + 1});
      const particle = svgNode(svg, "g", {class: "viz-particle", visibility: "hidden"});
      svgNode(particle, "circle", {r: 14, fill: colors[(source - 1) % colors.length], stroke: "white", "stroke-width": 2});
      label(particle, 0, 6, step.input[source - 1], "viz-particle-value");
      particles.push({path, particle});
    });
    [...step.input].forEach((value, index) => {
      const x = position(index, step.input.length);
      label(svg, x, inputY - 13, String(index + 1), "viz-index");
      bit(svg, x, inputY, value, index + 1, "input", index + 1, color);
    });
    [...step.output].forEach((value, index) => {
      const x = position(index, step.output.length);
      bit(svg, x, outputY, value, index + 1, "output", step.mapping[index], color);
      label(svg, x, 409, String(step.mapping[index]), "viz-source-index");
    });
    if (step.half_width) {
      const divider = (position(step.half_width - 1, step.input.length) + position(step.half_width, step.input.length)) / 2;
      svgNode(svg, "path", {d: `M ${divider} 38 V 115 M ${divider} 323 V 418`, stroke: "#9b7b55", "stroke-dasharray": "5 4"});
      label(svg, 400, 445, `左半部 ${step.half_width} bit`, "viz-small");
      label(svg, 790, 445, `右半部 ${step.half_width} bit`, "viz-small");
    } else {
      label(svg, 590, 445, `${step.box_label}: (${step.mapping.join(", ")})`, "viz-small");
    }
    return {svg, frame(progress, active) {
      particles.forEach(({path, particle}, index) => {
        const fraction = Math.min(1, Math.max(0, progress * 1.3 - index * 0.028));
        const point = path.getPointAtLength(path.getTotalLength() * fraction);
        particle.setAttribute("transform", `translate(${point.x},${point.y})`);
        particle.setAttribute("visibility", active && progress < 0.97 ? "visible" : "hidden");
      });
    }};
  }

  function drawXor(step) {
    const {svg, arrow} = makeSvg(step.title, 400);
    const count = step.output.length;
    const positions = Array.from({length: count}, (_, index) => 290 + index * 590 / Math.max(1, count - 1));
    label(svg, 150, 88, step.left_label || "输入", "viz-label");
    label(svg, 150, 178, step.right_label || "子密钥", "viz-label");
    label(svg, 150, 299, "XOR 输出", "viz-label");
    const groups = positions.map((x, index) => {
      const group = svgNode(svg, "g", {class: "viz-xor-column"});
      bit(group, x, 60, step.left[index], index + 1, "input");
      bit(group, x, 150, step.right[index], index + 1, "key", index + 1, "#b96520");
      line(group, `M ${x} 192 V 257`, arrow);
      label(group, x, 134, "⊕", "viz-xor-symbol");
      bit(group, x, 272, step.output[index], index + 1, "output", index + 1, "#2b6980");
      return svgNode(group, "rect", {x: x - 29, y: 48, width: 58, height: 280, rx: 9,
        fill: "none", stroke: "#d26940", "stroke-width": 3, visibility: "hidden"});
    });
    label(svg, 580, 373, step.retained_right
      ? `右半 R=${step.retained_right} 原样保留；拼接 ${step.output} ‖ ${step.retained_right} = ${step.block_output}`
      : "逐位异或：相同为 0，不同为 1。", "viz-label");
    return {svg, frame(progress, active) {
      groups.forEach((group, index) => group.setAttribute("visibility", active && index === Math.min(count - 1, Math.floor(progress * count)) ? "visible" : "hidden"));
    }};
  }

  function drawSboxes(step) {
    const {svg} = makeSvg(step.title, 485);
    const activeCells = [];
    step.boxes.forEach((box, boxIndex) => {
      const left = 50 + boxIndex * 500;
      label(svg, left + 195, 32, box.name, "viz-box-name");
      const inputGroup = svgNode(svg, "g", {class: "viz-sbox-input"});
      [...box.input].forEach((value, index) => {
        bit(inputGroup, left + 105 + index * 60, 52, value, index + 1, "input", index + 1,
          index === 0 || index === 3 ? "#15803d" : "#087ea5");
      });
      label(svg, left + 195, 122, `首尾 ${box.input[0]}${box.input[3]} → 行 ${box.row}；中间 ${box.input.slice(1, 3)} → 列 ${box.column}`, "viz-small");
      const tableX = left + 50, tableY = 155, cell = 60;
      label(svg, tableX - 21, tableY + 35, "行", "viz-small");
      label(svg, tableX + 180, tableY - 13, "列", "viz-small");
      for (let row = -1; row < 4; row++) {
        for (let column = -1; column < 4; column++) {
          const selected = row === box.row && column === box.column;
          const group = svgNode(svg, "g", {class: selected ? "viz-sbox-cell selected viz-sbox-hit" : "viz-sbox-cell",
            "data-box-name": box.name,
            "data-box": boxIndex + 1, "data-row": row, "data-column": column,
            "data-value": row >= 0 && column >= 0 ? box.table[row][column] : ""});
          const x = tableX + (column + 1) * cell, y = tableY + (row + 1) * 49;
          const fill = row === -1 && column === -1 ? "#edf2f5" : row === -1 ? "#08a9d1"
            : column === -1 ? "#16a05c" : selected ? "#f3b660"
              : row === box.row || column === box.column ? "#fff0d4" : "#f3f5f7";
          const rect = svgNode(group, "rect", {x, y, width: cell, height: 49, fill, stroke: "#7c8c93", "stroke-width": 1});
          const value = row === -1 && column === -1 ? "r/c" : row === -1 ? column.toString(2).padStart(2, "0")
            : column === -1 ? row.toString(2).padStart(2, "0") : box.table[row][column].toString(2).padStart(2, "0");
          label(group, x + cell / 2, y + 32, value, row === -1 && column === -1 ? "viz-small"
            : row === -1 || column === -1 ? "viz-table-header" : "viz-table-value");
          if (selected) { rect.setAttribute("stroke", "#bd6217"); rect.setAttribute("stroke-width", "3"); activeCells.push(rect); }
        }
      }
      label(svg, left + 195, 438, `${box.input} → ${box.output}`, "viz-output-label");
    });
    label(svg, 500, 477, `S-box1 ‖ S-box2 = ${step.output}；使用作业修订版 S-box2。`, "viz-small");
    return {svg, frame(progress, active) {
      activeCells.forEach((cell) => cell.setAttribute("fill", active && progress < 0.6 ? "#ffcf8f" : "#f3b660"));
    }};
  }

  function box(svg, x, y, width, height, title, value, className = "viz-node") {
    const group = svgNode(svg, "g", {class: className});
    svgNode(group, "rect", {x, y, width, height, rx: 8});
    label(group, x + width / 2, y + 21, title, "viz-small");
    label(group, x + width / 2, y + height - 12, value, "viz-node-value");
    return group;
  }

  function drawRound(step) {
    const {svg, arrow} = makeSvg(step.title, 610);
    const nodes = [];
    box(svg, 85, 20, 170, 60, "L · 左半部", step.left);
    box(svg, 495, 20, 170, 60, "R · 右半部", step.right);
    line(svg, "M 170 80 V 438", arrow);
    line(svg, "M 580 80 V 140", arrow);
    line(svg, "M 580 104 H 960 V 530 H 670", arrow);
    label(svg, 948, 322, "R 保留", "viz-small", "end");
    nodes.push(box(svg, 490, 140, 180, 60, "EP 扩展", step.ep));
    line(svg, "M 580 200 V 231", arrow);
    svgNode(svg, "circle", {cx: 580, cy: 251, r: 20, class: "viz-xor-gate"});
    label(svg, 580, 258, "⊕", "viz-xor-symbol");
    box(svg, 745, 219, 175, 63, step.subkey_name || "子密钥", step.subkey, "viz-node key-node");
    line(svg, "M 745 251 H 604", arrow, {stroke: "#b96520"});
    label(svg, 625, 291, step.mixed, "viz-small", "start");
    line(svg, "M 580 271 V 299 H 430 V 321", arrow);
    line(svg, "M 580 299 H 710 V 321", arrow);
    nodes.push(box(svg, 335, 325, 190, 65, "S-box1", `${step.mixed.slice(0, 4)} → ${step.sbox_output.slice(0, 2)}`));
    nodes.push(box(svg, 615, 325, 190, 65, "S-box2", `${step.mixed.slice(4)} → ${step.sbox_output.slice(2)}`));
    line(svg, "M 430 390 V 413 H 580 V 430", arrow);
    line(svg, "M 710 390 V 413 H 580", "none");
    nodes.push(box(svg, 490, 433, 180, 60, "P4 / SP 置换", step.p4));
    line(svg, "M 490 461 H 193", arrow);
    svgNode(svg, "circle", {cx: 170, cy: 461, r: 21, class: "viz-xor-gate"});
    label(svg, 170, 468, "⊕", "viz-xor-symbol");
    line(svg, "M 170 482 V 499", arrow);
    nodes.push(box(svg, 85, 503, 170, 60, "L ⊕ F(R,K)", step.output.slice(0, 4)));
    box(svg, 495, 503, 170, 60, "R · 不变", step.output.slice(4));
    label(svg, 500, 601, `fₖ(${step.input}) = ${step.output}；只有第一轮之后才进行 SW。`, "viz-small");
    return {svg, frame(progress, active) {
      nodes.forEach((node, index) => node.classList.toggle("active-node", active && index === Math.min(nodes.length - 1, Math.floor(progress * nodes.length))));
    }};
  }

  function drawTransfer(step, options) {
    const {svg, arrow} = makeSvg(step.title, 405);
    const forward = options.direction !== "b_to_a";
    const sender = forward ? "A" : "B", receiver = forward ? "B" : "A";
    const senderInfo = sender === "A" ? "整数位运算实现" : "独立字符串实现";
    const receiverInfo = receiver === "A" ? "整数位运算实现" : "独立字符串实现";
    const ciphertext = options.ciphertext;
    const stage = options.stepIndex;
    label(svg, 500, 45, `双方共享演示密钥 K = ${options.key}`, "viz-small");
    const left = box(svg, 35, 95, 260, 195, `模拟端 ${sender} · ${senderInfo}`,
      stage === 0 ? `${step.input} → ${step.output}` : ciphertext, "viz-node peer-node");
    const right = box(svg, 705, 95, 260, 195, `模拟端 ${receiver} · ${receiverInfo}`,
      stage === 2 ? `${step.input} → ${step.output}` : "等待接收", "viz-node peer-node");
    label(svg, 165, 177, "加密", "viz-box-name");
    label(svg, 835, 177, "解密", "viz-box-name");
    const path = line(svg, "M 307 196 H 693", arrow, {stroke: "#26738a", "stroke-width": 3, class: "viz-channel"});
    label(svg, 500, 144, "本地模拟信道 · 传递 8 位密文", "viz-small");
    const packet = svgNode(svg, "g", {class: "viz-packet"});
    svgNode(packet, "rect", {x: -70, y: -23, width: 140, height: 46, rx: 8, fill: "#fff1d2", stroke: "#b96520", "stroke-width": 2});
    label(packet, 0, 7, ciphertext, "viz-node-value");
    label(svg, 500, 342, stage === 2 ? "对照发送前明文，验证跨实现还原" : stage === 1 ? "只传递密文；双方预先约定同一个演示密钥" : "两个端点分别调用各自算法，结果由后端实际计算", "viz-label");
    label(svg, 500, 386, "个人在同一台机器上模拟 A/B，无外部小组或真实网络通信。", "viz-small");
    const frame = (progress, active) => {
      const fraction = stage === 0 ? 0 : stage === 2 ? 1 : active ? progress : 0.5;
      const point = path.getPointAtLength(path.getTotalLength() * (0.17 + fraction * 0.66));
      packet.setAttribute("transform", `translate(${point.x},${point.y})`);
      left.classList.toggle("active-node", stage === 0);
      right.classList.toggle("active-node", stage === 2);
    };
    return {svg, frame};
  }

  function drawByte(step) {
    const {svg, arrow} = makeSvg(step.title, 330);
    const decrypt = step.operation === "decrypt";
    const names = decrypt ? ["密文字节", "S-DES 解密", "ASCII · 8 bit", "恢复字符"]
      : ["原始字符", "ASCII · 8 bit", "S-DES 密文", "解密还原"];
    const values = decrypt ? [step.ciphertext, "K2 → K1", step.plaintext, step.restored]
      : [step.character, step.plaintext, step.ciphertext, step.restored];
    const nodes = names.map((name, index) => box(svg, 22 + index * 250, 110, 205, 105, name, values[index]));
    for (let index = 0; index < 3; index++) line(svg, `M ${232 + index * 250} 164 H ${265 + index * 250}`, arrow);
    label(svg, 500, 53, `第 ${step.byte_index + 1} 个字节 · 演示密钥 ${step.key}`, "viz-box-name");
    label(svg, 500, 285, "每个 ASCII 字符独立加密；解密后按原顺序拼接，不添加填充。", "viz-small");
    return {svg, frame(progress, active) {
      nodes.forEach((node, index) => node.classList.toggle("active-node", active && index === Math.min(3, Math.floor(progress * 4))));
    }};
  }

  function createPlayer(host, steps, options = {}) {
    if (host._sdesPlayer) host._sdesPlayer.destroy();
    host.replaceChildren();
    if (!steps.length) { host.append(html("p", "hint", "没有可播放的步骤。")); return null; }
    const root = html("div", "viz-player");
    const toolbar = html("div", "viz-toolbar");
    const previous = html("button", "viz-prev", "← 上一步");
    const play = html("button", "viz-play primary", "播放");
    const next = html("button", "viz-next", "下一步 →");
    const reset = html("button", "viz-reset", "回到起点");
    [previous, play, next, reset].forEach((button) => { button.type = "button"; toolbar.append(button); });
    const speed = html("select", "viz-speed");
    speed.setAttribute("aria-label", "动画速度");
    for (const factor of [0.5, 1, 2, 4]) {
      const option = html("option", "", `${factor}× 速度`); option.value = factor; speed.append(option);
    }
    speed.value = "1";
    toolbar.append(speed);
    const stage = html("select", "viz-stage");
    stage.setAttribute("aria-label", "选择演示步骤");
    steps.forEach((step, index) => {
      const option = html("option", "", `${String(index + 1).padStart(2, "0")} · ${step.title}`);
      option.value = step.id || String(index); stage.append(option);
    });
    const heading = html("div", "viz-heading");
    const title = html("h4", "viz-step-title");
    const counter = html("span", "tag viz-step-count");
    heading.append(title, counter);
    const wrap = html("div", "viz-canvas-wrap");
    wrap.tabIndex = 0;
    wrap.setAttribute("aria-label", "算法示意图，窄屏可左右滚动");
    const caption = html("p", "viz-caption"); caption.setAttribute("aria-live", "polite");
    const progress = html("progress", "viz-progress"); progress.max = 1; progress.value = 0;
    progress.setAttribute("aria-label", "当前步骤播放进度");
    const note = html("p", "hint viz-motion-note", "图中每个值均来自本次运算。可暂停逐步查看；动画速度只影响展示，不代表计算耗时。窄屏可横向滚动示意图。");
    root.append(toolbar, stage, heading, wrap, caption, progress, note);
    host.append(root);
    let index = 0, playing = false, elapsed = 0, lastTime = 0, frameId = null, renderer = null;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const renderers = {permutation: drawPermutation, xor: drawXor, sboxes: drawSboxes, round: drawRound,
      transfer: drawTransfer, byte: drawByte};
    function draw() {
      const step = steps[index];
      elapsed = 0; progress.value = 0;
      root.dataset.stepIndex = index; root.dataset.stepId = step.id || index; root.dataset.playing = String(playing);
      root.dataset.kind = step.kind;
      stage.selectedIndex = index;
      title.textContent = step.title;
      counter.textContent = `${index + 1} / ${steps.length}`;
      const io = step.kind === "xor" ? `  输入 ${step.left} ⊕ ${step.right} → 输出 ${step.output}`
        : step.input !== undefined && step.output !== undefined ? `  输入 ${step.input} → 输出 ${step.output}` : "";
      caption.textContent = (step.description || "") + io;
      const render = renderers[step.kind] || drawTransfer;
      renderer = render(step, {...options, stepIndex: index});
      wrap.replaceChildren(renderer.svg);
      renderer.frame(0, false);
      previous.disabled = index === 0; next.disabled = index === steps.length - 1;
    }
    function pause() {
      playing = false; root.dataset.playing = "false"; play.textContent = "播放";
      cancelAnimationFrame(frameId); frameId = null;
      renderer?.frame(progress.value, false);
    }
    function tick(time) {
      if (!playing) return;
      elapsed += Math.min(100, time - lastTime) * Number(speed.value);
      lastTime = time;
      progress.value = Math.min(1, elapsed / 3200);
      renderer.frame(progress.value, !reduceMotion.matches);
      if (progress.value >= 1) {
        if (index === steps.length - 1) { pause(); return; }
        index += 1; draw();
      }
      frameId = requestAnimationFrame(tick);
    }
    function select(selected) { pause(); index = Math.max(0, Math.min(steps.length - 1, selected)); draw(); }
    play.addEventListener("click", () => {
      if (playing) { pause(); return; }
      if (index === steps.length - 1 && progress.value >= 1) { index = 0; draw(); }
      pauseAll(); playing = true; root.dataset.playing = "true"; play.textContent = "暂停";
      lastTime = performance.now(); frameId = requestAnimationFrame(tick);
    });
    previous.addEventListener("click", () => select(index - 1));
    next.addEventListener("click", () => select(index + 1));
    reset.addEventListener("click", () => select(0));
    stage.addEventListener("change", () => select(stage.selectedIndex));
    const controller = {pause, select, getStep() { return steps[index]; },
      destroy() { pause(); players.delete(controller); host._sdesPlayer = null; }};
    players.add(controller); host._sdesPlayer = controller;
    draw();
    return controller;
  }

  function pauseAll() { players.forEach((player) => player.pause()); }
  document.addEventListener("visibilitychange", () => { if (document.hidden) pauseAll(); });

  function renderConvergence(host, counts) {
    host.replaceChildren();
    const list = html("div", "candidate-flow");
    [1024, ...counts].forEach((count, index) => {
      if (index) list.append(html("span", "candidate-arrow", "→"));
      const item = html("div", "candidate-node");
      item.append(html("strong", "", String(count)), html("span", "", index ? `前 ${index} 对` : "完整密钥空间"));
      item.dataset.count = count;
      list.append(item);
    });
    host.append(list);
  }

  function renderCollision(host, result) {
    host.replaceChildren();
    const {svg, arrow} = makeSvg("不同密钥汇聚到相同密文的碰撞实例", 350);
    const keys = result.example.keys;
    const shown = keys.slice(0, 12);
    shown.forEach((key, index) => {
      const y = 30 + index * 260 / Math.max(1, shown.length - 1);
      label(svg, 105, y + 6, key, "viz-node-value");
      line(svg, `M 190 ${y} L 520 160`, arrow, {stroke: colors[index % colors.length], "stroke-opacity": 0.6});
    });
    box(svg, 525, 105, 245, 110, "相同密文", result.example.ciphertext);
    label(svg, 877, 160, `${keys.length} 把密钥`, "viz-output-label");
    label(svg, 535, 315, `固定明文 ${result.plaintext}；每条连线对应一把真实候选密钥。`, "viz-small");
    const wrap = html("div", "viz-canvas-wrap"); wrap.append(svg); host.append(wrap);
    const chart = html("div", "histogram");
    const maximum = Math.max(...Object.values(result.histogram));
    for (const [size, count] of Object.entries(result.histogram)) {
      const row = html("div", "histogram-row");
      const meter = html("meter"); meter.min = 0; meter.max = maximum; meter.value = count;
      meter.setAttribute("aria-label", `${size} 把密钥对应的密文组数 ${count}`);
      row.append(html("span", "", `${size} 把 / 组`), meter, html("strong", "", `${count} 组`));
      chart.append(row);
    }
    host.append(html("h4", "", "密文组大小分布"), chart);
  }
  return {createPlayer, pauseAll, renderConvergence, renderCollision};
})();
