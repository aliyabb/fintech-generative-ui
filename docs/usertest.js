/* 用户理解度测试执行器。
   组内对照：每名被试两种条件都做，用两组不同数字抵消记忆效应，
   条件顺序按被试编号奇偶交叉，抵消学习效应。
   全程本地运行，数据不上传，结束后导出 JSON。 */
const app = document.getElementById("app");
let M = null, S = null;

// esc() 由 render.js 提供，此处不再重复声明
fetch("test_materials.json").then(r => r.json()).then(m => { M = m; welcome(); });

function welcome() {
  app.innerHTML = `
  <h1>分期费率理解度测试</h1>
  <p class="lede">大约 10 分钟。你会看到两组关于信用卡分期的说明，每组回答 5 个问题。
  <strong>凭说明回答即可，不需要有金融背景，答不上来就写"不确定"。</strong>
  没有对错评价——我们测的是说明写得清不清楚，不是你。</p>
  <p class="lede">全程在你的浏览器里运行，不上传任何数据。</p>
  <div class="row"><label>被试编号
    <input id="pid" placeholder="P1 / P2 / …" autocomplete="off"></label></div>
  <button class="primary" id="go">开始</button>`;
  document.getElementById("go").onclick = () => {
    const pid = document.getElementById("pid").value.trim();
    if (!pid) return document.getElementById("pid").focus();
    const n = parseInt(pid.replace(/\D/g, ""), 10) || 1;
    // 奇数：先文字(A组数字) 后UI(B组数字)；偶数：先UI(A组) 后文字(B组)
    const plan = n % 2
      ? [{ mode:"text", set:"A" }, { mode:"ui", set:"B" }]
      : [{ mode:"ui",   set:"A" }, { mode:"text", set:"B" }];
    S = { pid, started: new Date().toISOString(), plan, block: 0, task: 0, answers: [] };
    intro();
  };
}

function intro() {
  const b = S.plan[S.block];
  app.innerHTML = `<h2>第 ${S.block + 1} 组，共 2 组</h2>
  <p class="lede">下面是一份关于分期的说明。看完后回答 5 个问题，
  <strong>回答时说明会一直在页面上，可以随时往回看。</strong></p>
  <button class="primary" id="go">看说明</button>`;
  document.getElementById("go").onclick = () => { S.task = 0; showTask(); };
}

function showTask() {
  const b = S.plan[S.block], set = M.sets[b.set], t = M.tasks[S.task];
  const body = b.mode === "text"
    ? `<div class="txtans">${esc(set.text[t.id]).replace(/\n/g, "<br>")}</div>`
    : `<div id="uibox"></div>`;
  app.innerHTML = `
  <div class="prog">第 ${S.block + 1}/2 组 · 问题 ${S.task + 1}/${M.tasks.length}</div>
  <div class="stim">${body}</div>
  <div class="qbox"><div class="q">${esc(t.q)}</div>
    <input id="ans" placeholder="填写你的答案，不确定就写「不确定」" autocomplete="off">
    <div class="row2">
      <label class="conf">有多确定？
        <select id="conf"><option value="1">1 很不确定</option><option value="2">2</option>
        <option value="3" selected>3 一般</option><option value="4">4</option>
        <option value="5">5 很确定</option></select></label>
      <button class="primary" id="next">下一题</button>
    </div></div>`;
  if (b.mode === "ui") renderComponents(set.ui[t.id], document.getElementById("uibox"));
  const t0 = performance.now();
  const submit = () => {
    S.answers.push({
      block: S.block, mode: b.mode, set: b.set, task: t.id, question: t.q,
      answer: document.getElementById("ans").value.trim(),
      confidence: +document.getElementById("conf").value,
      seconds: Math.round((performance.now() - t0) / 100) / 10,
    });
    S.task++;
    if (S.task < M.tasks.length) showTask();
    else if (++S.block < S.plan.length) intro();
    else finish();
  };
  document.getElementById("next").onclick = submit;
  document.getElementById("ans").addEventListener("keydown", e => { if (e.key === "Enter") submit(); });
  document.getElementById("ans").focus();
}

function finish() {
  S.finished = new Date().toISOString();
  const json = JSON.stringify(S, null, 1);
  app.innerHTML = `<h2>完成，谢谢！</h2>
  <p class="lede">把下面的内容整段复制，发回给测试组织者即可。</p>
  <textarea id="out" readonly>${esc(json)}</textarea>
  <button class="primary" id="cp">复制</button> <span id="ok"></span>`;
  document.getElementById("cp").onclick = async () => {
    const ta = document.getElementById("out");
    ta.select();
    try { await navigator.clipboard.writeText(json); }
    catch (e) { document.execCommand("copy"); }
    document.getElementById("ok").textContent = "已复制";
  };
}
