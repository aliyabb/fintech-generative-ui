"""可靠性基准：结构有效率与降级率。这是本项目唯一由代码实测的指标。"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from generate import build

QUESTIONS = [
 "12000元分12期，实际成本到底是多少？",
 "给我看一下12000元分12期的还款计划",
 "稳盈90天和智选混合C有什么区别？",
 "智选混合C的风险等级是什么意思？",
 "我想办个分期，成本高吗？",
 "12000元分3期的真实年化是多少？",
 "20000元分24期的还款计划",
 "添利债券A和货币宝的参数对比一下",
 "R4风险等级是什么？",
 "5000元分6期每期还多少钱？",
 "稳盈90天的风险等级和封闭期",
 "12000元分6期，宣传费率和真实年化差多少？",
]

def main(repeats: int = 2, variant: str = "v2"):
    out, ok = [], 0
    for q in QUESTIONS:
        for i in range(repeats):
            o = build(q, variant=variant)
            out.append(o); ok += (not o["_fallback"])
            names = "+".join(c["component"] for c in o["components"])
            print(f"{'OK ' if not o['_fallback'] else 'FB '} {names[:34]:34s} "
                  f"{o['_latency_s']:5.1f}s  {q[:24]}", flush=True)
    n = len(out)
    m = {"样本数": n, "结构有效数": ok, "结构有效率": round(ok / n, 4),
         "降级率": round(1 - ok / n, 4),
         "截断率": round(sum(o["_truncated"] for o in out) / n, 4),
         "部分救回率": round(sum(bool(o.get("_dropped_components")) for o in out) / n, 4),
         "平均延迟_s": round(sum(o["_latency_s"] for o in out) / n, 2),
         "平均组件数": round(sum(len(o["components"]) for o in out) / n, 2),
         "组件分布": {}}
    for o in out:
        for c in o["components"]:
            m["组件分布"][c["component"]] = m["组件分布"].get(c["component"], 0) + 1
    pathlib.Path("results").mkdir(exist_ok=True)
    m["契约版本"] = variant
    pathlib.Path(f"results/schemas_{variant}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    pathlib.Path(f"results/reliability_{variant}.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n", json.dumps(m, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main(variant=sys.argv[1] if len(sys.argv) > 1 else "v2")
