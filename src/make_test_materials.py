"""生成用户测试材料：同样 5 个任务，两种呈现形式 × 两组数字。

两组数字用于抵消记忆效应——被试在文字条件下做 A 组，
在生成式 UI 条件下做 B 组（或反之，由分组决定）。
两种条件下**呈现的信息内容完全一致**，只有形式不同。这是关键控制。

正确答案一律由 calc.py 计算，不由模型给出。

--------------------------------------------------------------------
v2 修正（重要）：初版检索是**每组只做一次**，用一条关于分期的查询
（"{金额}元分{期数}期 手续费 年化 提前还款"）取回 5 个片段，
然后把同一份上下文喂给全部 5 道题。

后果：风险等级那道题问的是「智选混合C」，而这份上下文里
根本没有理财产品的片段，模型于是正确地回答"无法提供该产品信息"。
而 UI 分支（generate.py）是**逐题检索**的，拿到了 risk_card 所需的片段。

也就是说两个条件呈现的内容并不一致 —— 关键控制被破坏，
基于该题得出的任何结论都不成立。首轮 6 名被试用的就是这一版材料，
已归档为 results/test_materials_v1_flawed.json。

修正：两个条件一律**逐题检索、同一条查询**。
--------------------------------------------------------------------
"""
from __future__ import annotations
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from calc import installment_apr
from llm import generate as llm_gen
from generate import build
from retriever import search

RATES = {3: 0.0055, 6: 0.0058, 12: 0.0060, 24: 0.0062}
SETS = {"A": (12000, 12), "B": (20000, 6)}

TASKS = [
    ("apr",   "这笔分期的实际年化利率（IRR口径）是多少？", "实际年化利率_IRR口径", 0.5, "百分数"),
    ("fee",   "手续费一共要付多少钱？",                  "手续费合计",          1.0, "金额"),
    ("ratio", "宣传的费率合计和实际年化差几倍？",          None,                 0.3, "倍数"),
    ("early", "提前还款能省下手续费吗？",                 None,                 None, "是否"),
    ("risk",  "智选混合C是什么风险等级，意味着什么？",       None,                 None, "简答"),
]

SYS_TEXT = ("你是民信银行的智能客服助手。依据【参考资料】回答客户问题，"
            "用连贯的自然语言，不要使用表格或列表。回答控制在 120 字以内。")


def truth(principal: int, periods: int) -> dict:
    r = installment_apr(principal, periods, RATES[periods])
    return {
        "apr": round(r["实际年化利率_IRR口径"] * 100, 2),
        "fee": r["手续费合计"],
        "ratio": round(r["实际年化利率_IRR口径"] / r["名义费率之和"], 2),
        "early": "不能，剩余期数手续费一次性收取、不予减免（F004）",
        "risk": "R4 进取型；本金可能发生较大亏损（F014/F015）",
        "每期还款": r["每期还款"], "名义费率之和": round(r["名义费率之和"] * 100, 2),
    }


def main():
    out = {"sets": {}, "tasks": [{"id": t[0], "q": t[1], "kind": t[4]} for t in TASKS]}
    for name, (principal, periods) in SETS.items():
        t = truth(principal, periods)
        ctx_q = f"{principal}元分{periods}期"
        calc_block = json.dumps(installment_apr(principal, periods, RATES[periods]),
                                ensure_ascii=False)

        text_answers, ui_answers = {}, {}
        for tid, q, *_ in TASKS:
            full_q = f"{ctx_q}，{q}" if tid != "risk" else q
            # 逐题检索，与 UI 分支（generate.py）使用同一条查询，
            # 保证两个条件拿到的材料一致。见文件头 v2 修正说明。
            hits = search(full_q, k=5)
            ctx = "\n".join(f"[{h['id']}] {h['正文']}" for h in hits)
            r = llm_gen(SYS_TEXT,
                        f"【参考资料】\n{ctx}\n【计算结果】{calc_block}\n\n【客户问题】{full_q}",
                        max_tokens=320)
            text_answers[tid] = r["text"]
            print(f"  [{name}/{tid}] text {r['latency_s']}s", flush=True)
            o = build(full_q)
            ui_answers[tid] = o["components"]
            print(f"  [{name}/{tid}] ui   {o['_latency_s']}s "
                  f"{[c['component'] for c in o['components']]}", flush=True)

        out["sets"][name] = {"principal": principal, "periods": periods,
                             "truth": t, "text": text_answers, "ui": ui_answers}

    pathlib.Path("docs/test_materials.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已生成 docs/test_materials.json（{len(SETS)} 组 × {len(TASKS)} 任务 × 2 形式）")


if __name__ == "__main__":
    main()
