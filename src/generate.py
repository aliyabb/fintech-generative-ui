"""生成界面结构。金额与年化一律由 calc.py 计算后注入，模型只负责组织界面。"""
from __future__ import annotations
import json, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from llm import generate as llm_generate
from calc import installment_apr
from retriever import search
from schema import SYSTEM, parse_and_validate, fallback, InvalidSchema
import variants

# 需要还款明细的问法才注入逐期表格；否则只注入汇总。
# 起因：注入12行明细会把输出撑到 max_tokens 截断，导致 JSON 不完整而降级。
WANTS_SCHEDULE = re.compile(r"(计划|明细|每期|逐期|表)")

RATES = {3: 0.0055, 6: 0.0058, 12: 0.0060, 24: 0.0062}


def _extract_installment(q: str):
    amt = re.search(r"(\d[\d,]{2,})\s*元", q)
    per = re.search(r"(\d+)\s*期", q)
    if not (amt and per):
        return None
    n = int(per.group(1))
    if n not in RATES:
        return None
    return installment_apr(float(amt.group(1).replace(",", "")), n, RATES[n])


def build(question: str, variant: str = "v2") -> dict:
    calc = _extract_installment(question)
    block = ""
    if calc:
        payload = dict(calc)
        if variant == "v1":
            payload["还款计划"] = [{"期次": i + 1, "还款额": calc["每期还款"],
                                 "其中手续费": calc["每期手续费"]}
                                for i in range(calc["期数"])]
        block = ("\n【计算结果】（确定性模块产出，直接引用，不要自行计算）\n"
                 + json.dumps(payload, ensure_ascii=False))

    hits = search(question, k=3)
    ctx = "\n".join(f"[{h['id']}] {h['正文']}" for h in hits)
    block += f"\n【产品条款】（组件内容须与此一致）\n{ctx}"

    sys_prompt = variants.SYSTEM_V1 if variant == "v1" else SYSTEM
    r = llm_generate(sys_prompt, f"{question}{block}", max_tokens=2200)
    err = None
    parser = {"v1": variants.parse_v1,
              "v2": variants.parse_v2_strict}.get(variant, parse_and_validate)
    try:
        components = parser(r["text"])
        fell_back = False
    except (InvalidSchema, variants.InvalidSchema) as e:
        components, fell_back, err = fallback(r["text"] or "抱歉，暂时无法生成该界面。"), True, str(e)
    # 数据注入：逐期明细来自 calc.py，不经过模型（仅 v2）。
    if calc and variant == "v2":
        rows = [{"期次": i + 1, "还款额": calc["每期还款"],
                 "其中手续费": calc["每期手续费"],
                 "其中本金": round(calc["每期还款"] - calc["每期手续费"], 2)}
                for i in range(calc["期数"])]
        for c in components:
            if c["component"] == "repayment_schedule":
                c["data"]["rows"] = rows
                c["data"]["_rows_source"] = "calc.py"

    dropped = components[0].pop("_dropped", []) if components else []
    return {
        "variant": variant,
        "_dropped_components": dropped,
        "question": question,
        "components": components,
        "_fallback": fell_back,
        "_error": err,
        "_latency_s": r["latency_s"],
        "_calc_injected": bool(calc),
        "_contexts": [h["id"] for h in hits],
        "_truncated": r.get("finish_reason") == "length",
    }
