/* 组件渲染器。模型返回结构，这里负责把结构变成界面。
   渲染器只认识 schema.py 中定义的组件；未知组件不渲染，避免把错误结构展示给用户。 */
const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const R = {
  fee_comparison(d) {
    const num = v => parseFloat(String(v).replace(/[^\d.]/g, "")) || 0;
    const a = num(d.advertised_value), b = num(d.actual_value);
    const max = Math.max(a, b) || 1;
    return `<div class="c"><div class="ct">${esc(d.title)}</div>
      <div class="fc"><div class="fl">${esc(d.advertised_label)}</div>
        <div class="fbar"><i style="width:${a / max * 100}%;background:var(--muted)"></i></div>
        <div class="fv">${esc(d.advertised_value)}</div></div>
      <div class="fc"><div class="fl">${esc(d.actual_label)}</div>
        <div class="fbar"><i style="width:${b / max * 100}%;background:var(--bad)"></i></div>
        <div class="fv bad">${esc(d.actual_value)}</div></div>
      ${d.total_fee!=null?`<div class="ftot">手续费总额 <b>${esc(d.total_fee)}</b></div>`:""}
      <div class="cn">${esc(d.note)}</div></div>`;
  },
  repayment_schedule(d) {
    const rows = (d.rows || []).map(r =>
      `<tr><td>${esc(r.期次)}</td><td class="num">${esc(r.还款额)}</td>
       <td class="num">${esc(r.其中本金 ?? "—")}</td><td class="num">${esc(r.其中手续费)}</td></tr>`).join("");
    return `<div class="c"><div class="ct">${esc(d.title)}</div>
      <div class="kv"><span>本金 ${esc(d.principal)} 元</span><span>期数 ${esc(d.periods)}</span>
        <span>每期 ${esc(d.per_period)} 元</span><span>总额 ${esc(d.total)} 元</span></div>
      <div class="sc"><table><thead><tr><th>期次</th><th>还款额</th><th>其中本金</th><th>其中手续费</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
      ${d._rows_source ? `<div class="cn">逐期明细由 <code>${esc(d._rows_source)}</code> 计算注入，未经过模型</div>` : ""}</div>`;
  },
  product_compare(d) {
    const head = (d.columns || []).map(c => `<th>${esc(c)}</th>`).join("");
    const body = (d.rows || []).map(r => `<tr>${(Array.isArray(r) ? r : Object.values(r))
      .map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("");
    return `<div class="c"><div class="ct">${esc(d.title)}</div>
      <div class="sc"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>
      <div class="cn warn">${esc(d.disclaimer)}</div></div>`;
  },
  risk_card(d) {
    return `<div class="c"><div class="ct">${esc(d.title)}</div>
      <div class="rl"><span class="rb">${esc(d.level)}</span>
        <span class="rn">${esc(d.level_name)}</span></div>
      <div class="cd">${esc(d.description)}</div>
      <div class="cn warn">${esc(d.warning)}</div></div>`;
  },
  clarify(d) {
    const f = (d.fields || []).map(x =>
      `<label><span>${esc(x.label || x.name)}</span><input placeholder="${esc(x.placeholder || "")}"></label>`).join("");
    return `<div class="c"><div class="ct">${esc(d.title)}</div><div class="cf">${f}</div>
      <div class="cn">参数不足时，模型选择追问而不是猜测——这是刻意的产品行为</div></div>`;
  },
  text(d) {
    return `<div class="c fb"><div class="ct">降级为纯文本</div>
      <div class="cd">${esc(d.content).slice(0, 700)}</div>
      <div class="cn">结构校验失败时一律降级。宁可退回文字，不可渲染出错误界面。</div></div>`;
  },
};

function renderComponents(list, el) {
  el.innerHTML = list.map(c => (R[c.component] || R.text)(c.data)).join("");
}
