"""分析用户测试结果。

把每名被试导出的 JSON 存进 usertest_data/，然后运行本脚本。
没有数据时脚本**不会**产出任何指标——这是刻意的，
不允许在未执行测试的情况下出现估计值。

评分标准写死在这里，不由人事后调整：
  apr / fee / ratio  数值题，按容差比对 calc.py 的真值
  early              是否题，答"不能省"为正确
  risk               三点采分：R4、进取型、本金可能较大亏损
"""
from __future__ import annotations
import json, pathlib, re, statistics, sys

DATA = pathlib.Path("usertest_data")
MAT = pathlib.Path("docs/test_materials.json")
TOL = {"apr": 0.5, "fee": 1.0, "ratio": 0.3}


def nums(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", (s or "").replace(",", ""))]


def grade(task: str, answer: str, truth: dict) -> bool:
    a = (answer or "").strip()
    if not a or "不确定" in a:
        return False
    if task in TOL:
        return any(abs(x - truth[task]) <= TOL[task] for x in nums(a))
    if task == "early":
        neg = re.search(r"(不能|不可以|不会|省不了|没有|不减免|不行)", a)
        pos = re.search(r"(可以省|能省|会减少|能减免)", a)
        return bool(neg) and not pos
    if task == "risk":
        pts = sum(bool(p) for p in (re.search(r"R\s*4", a, re.I),
                                    "进取" in a,
                                    re.search(r"(亏损|亏钱|损失|本金.*风险)", a)))
        return pts >= 2
    return False


def main() -> int:
    files = sorted(DATA.glob("*.json"))
    if not files:
        print("usertest_data/ 中没有数据。用户测试尚未执行，因此不产出任何指标。")
        print("执行步骤见 docs/用户测试方案.md，测试页面为 docs/usertest.html。")
        return 1

    materials = json.loads(MAT.read_text(encoding="utf-8"))
    rows = []
    for f in files:
        s = json.loads(f.read_text(encoding="utf-8"))
        for a in s["answers"]:
            truth = materials["sets"][a["set"]]["truth"]
            rows.append({**a, "pid": s["pid"], "correct": grade(a["task"], a["answer"], truth)})

    def agg(mode):
        r = [x for x in rows if x["mode"] == mode]
        return {
            "样本数": len(r),
            "正确率": round(sum(x["correct"] for x in r) / len(r), 4) if r else None,
            "中位耗时_s": round(statistics.median(x["seconds"] for x in r), 1) if r else None,
            "平均信心": round(statistics.mean(x["confidence"] for x in r), 2) if r else None,
        }

    t, u = agg("text"), agg("ui")
    by_task, conf_task = {}, {}
    for tid in {x["task"] for x in rows}:
        for m in ("text", "ui"):
            sub = [x for x in rows if x["task"] == tid and x["mode"] == m]
            if sub:
                by_task.setdefault(tid, {})[m] = round(
                    sum(x["correct"] for x in sub) / len(sub), 3)
                conf_task.setdefault(tid, {})[m] = round(
                    statistics.mean(x["confidence"] for x in sub), 2)

    n_participants = len(files)
    modes_present = {x["mode"] for x in rows}
    out = {
        "被试人数": n_participants,
        "状态": ("单人试点：仅验证工具可用与任务表述清晰，不足以比较两种形式"
               if n_participants < 2 or len(modes_present) < 2
               else f"小样本试点（{n_participants} 人）：可观察方向，不可给出比例结论"
               if n_participants < 6 else "正式测试"),
        "文字条件": t, "生成式UI条件": u,
        "正确率差_UI减文字": (round(u["正确率"] - t["正确率"], 4)
                        if t["正确率"] is not None and u["正确率"] is not None else None),
        "分任务正确率": by_task,
        "分任务信心": conf_task,
        "条件顺序": {p: ("先文字" if json.loads((DATA / f"{p}.json").read_text(encoding="utf-8"))
                            ["plan"][0]["mode"] == "text" else "先界面")
                   for p in sorted({x["pid"] for x in rows})},
        "逐人明细": [{"pid": p, "文字": round(sum(x["correct"] for x in rows
                                             if x["pid"] == p and x["mode"] == "text"), 1),
                    "UI": round(sum(x["correct"] for x in rows
                                    if x["pid"] == p and x["mode"] == "ui"), 1)}
                   for p in sorted({x["pid"] for x in rows})],
        "材料版本警告": ("首轮 6 名被试使用的是 v1 材料，其中文字条件在 risk 一题上"
                   "因检索缺陷未包含答案（模型回答'无法提供该产品信息'）。"
                   "两个条件内容不一致，该题的任何比较结论均不成立。"
                   "详见 results/test_materials_v1_flawed.json 与 src/make_test_materials.py 文件头。"),
        "样本量说明": (f"{n_participants} 名被试不足以做统计推断。"
                  "本结果用于发现明显差异与可用性问题，"
                  "不足以支持'提升了 N 个百分点'这类精确结论。"
                  + (" 当前仅 1 名被试，任何两种形式之间的差异都不可解读，"
                     "本次运行的唯一结论是：测试工具可用、任务表述无歧义。"
                     if n_participants < 2 else
                     " 可以陈述的是逐人的事实（谁在哪个条件下答对了哪题），"
                     "不能陈述比例。")),
    }
    pathlib.Path("results/user_test.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
