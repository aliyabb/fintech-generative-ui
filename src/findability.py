"""可读性的客观替代指标：关键数字有多难找。

**这不是用户理解度测试的替代品。** 理解需要真人回答。
但有一部分是代码可以客观测量的：同样的信息，两种呈现形式下，
用户要读过多少内容才能碰到那个关键数字。

对同一组测试材料（内容完全一致，只有形式不同）测三件事：
  命中     —— 关键数字是否出现
  前置字符 —— 按阅读顺序，关键数字之前有多少字
  总字符   —— 全部内容长度

前置字符越少，说明信息越"迎面而来"而不是"埋在段落里"。
这是形式差异的直接后果，与被试无关，因此可以在没有用户的情况下测。
"""
from __future__ import annotations
import json, pathlib, re

MAT = pathlib.Path("docs/test_materials.json")
KEY = {"apr": "apr", "fee": "fee", "ratio": "ratio"}   # 只测有唯一数值答案的任务


def flatten(components: list[dict]) -> str:
    """把组件按阅读顺序拍平成文本。表格逐行展开。"""
    out = []
    for c in components:
        d = c.get("data", {})
        for k, v in d.items():
            if k.startswith("_"):
                continue
            if isinstance(v, list):
                for row in v:
                    if isinstance(row, dict):
                        out.append(" ".join(str(x) for x in row.values()))
                    elif isinstance(row, list):
                        out.append(" ".join(str(x) for x in row))
                    else:
                        out.append(str(row))
            elif isinstance(v, dict):
                out.append(" ".join(f"{a} {b}" for a, b in v.items()))
            else:
                out.append(str(v))
    return "\n".join(out)


def locate(text: str, target: float, tol: float) -> int | None:
    """返回关键数字首次出现前的字符数；未出现返回 None。"""
    for m in re.finditer(r"\d+(?:\.\d+)?", text.replace(",", "")):
        try:
            if abs(float(m.group()) - target) <= tol:
                return m.start()
        except ValueError:
            pass
    return None


TOL = {"apr": 0.05, "fee": 0.5, "ratio": 0.05}


def main():
    mat = json.loads(MAT.read_text(encoding="utf-8"))
    rows = []
    for sname, s in mat["sets"].items():
        for task in KEY:
            target = s["truth"][task]
            for mode, payload in (("text", s["text"][task]), ("ui", flatten(s["ui"][task]))):
                pos = locate(payload, target, TOL[task])
                rows.append({"set": sname, "task": task, "mode": mode,
                             "命中": pos is not None,
                             "前置字符": pos, "总字符": len(payload)})

    def agg(mode):
        r = [x for x in rows if x["mode"] == mode]
        hit = [x for x in r if x["命中"]]
        return {"样本": len(r), "命中率": round(len(hit) / len(r), 3),
                "中位前置字符": (sorted(x["前置字符"] for x in hit)[len(hit) // 2]
                          if hit else None),
                "中位总字符": sorted(x["总字符"] for x in r)[len(r) // 2]}

    out = {"说明": "客观替代指标，非用户理解度测试。见 src/findability.py 文档字符串。",
           "文字条件": agg("text"), "生成式UI条件": agg("ui"), "逐项": rows}
    pathlib.Path("results/findability.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    t, u = out["文字条件"], out["生成式UI条件"]
    print(f"{'':16s}{'命中率':>10}{'中位前置字符':>14}{'中位总字符':>12}")
    for name, d in (("文字", t), ("生成式UI", u)):
        print(f"{name:16s}{d['命中率']*100:>9.0f}%{str(d['中位前置字符']):>14}{d['中位总字符']:>12}")


if __name__ == "__main__":
    main()
