"""生成式UI 的组件契约。

设计立场：模型不返回段落，返回**界面结构**。
金融产品的核心体验问题是"看不懂成本"，而成本本身是结构化的
（费率、期数、时间、金额），用表格与对比条呈现比用文字描述更接近事实形态。

可靠性代价：模型可能返回无效结构。因此每次生成都经过校验，
校验失败一律降级为纯文本回答——宁可退回文字，不可渲染出错误界面。
"""
from __future__ import annotations
import json

COMPONENTS = {
    "fee_comparison": {
        # total_fee 是后加的必需字段。起因：可查找性测量（src/findability.py）发现
        # 有一次用户问"手续费一共多少钱"，模型选了本组件，而组件里只有费率没有金额——
        # 答案根本不在界面上。一个讲成本的组件不显示成本金额，是契约本身的缺陷。
        "说明": "宣传费率 vs IRR口径真实年化，对比条（含手续费总额）",
        "必需字段": ["title", "advertised_label", "advertised_value",
                     "actual_label", "actual_value", "total_fee", "note"],
    },
    "repayment_schedule": {
        # rows 不是必需字段：逐期明细由确定性模块注入，模型不必复述。
        # 让模型复述 12~24 行表格会撑爆输出长度并导致 JSON 截断（实测降级主因）。
        # 分工：模型决定"用什么组件、怎么组织"，代码决定"里面是什么数字"。
        "说明": "分期还款计划表（逐期明细由计算模块填充）",
        "必需字段": ["title", "principal", "periods", "per_period", "total"],
    },
    "product_compare": {
        "说明": "多产品客观参数对比表（不含推荐结论）",
        "必需字段": ["title", "columns", "rows", "disclaimer"],
    },
    "risk_card": {
        "说明": "风险等级卡",
        "必需字段": ["title", "level", "level_name", "description", "warning"],
    },
    "clarify": {
        "说明": "参数不足时的追问表单",
        "必需字段": ["title", "fields"],
    },
    "text": {"说明": "降级纯文本", "必需字段": ["content"]},
}

SYSTEM = (
 "你是民信银行的界面生成器。不要输出段落文字，只输出 JSON 描述界面。\n"
 "格式：一个 JSON 数组，元素为组件对象，按展示顺序排列。\n"
 "  [{\"component\":\"组件名\",\"data\":{...}}, ...]\n"
 "简单问题用一个组件即可；需要多层信息时可组合多个组件。\n\n"
 "可用组件与必需字段：\n"
 + "\n".join(f"  {k}（{v['说明']}）: {', '.join(v['必需字段'])}"
             for k, v in COMPONENTS.items())
 + "\n\n规则：\n"
   "1. 涉及金额或年化利率时，直接使用【计算结果】中的数值，不要自行计算。\n"
   "2. product_compare 只呈现客观参数，disclaimer 必须写明本表不构成投资建议。\n"
   "3. 参数不足以计算时，返回 clarify 组件追问。\n"
   "4. repayment_schedule 不要输出 rows 字段，逐期明细由系统填充。\n"
   "5. fee_comparison 的 total_fee 必须填手续费总额（金额，不是费率）。\n"
   "6. 只输出 JSON，不要任何解释文字或代码块标记。")


class InvalidSchema(Exception):
    pass


def _iter_json_objects(raw: str):
    """扫描平衡括号，逐个取出顶层 JSON 值。

    起因：初版契约只允许单个组件对象，用贪婪正则 r"\{.*\}" 提取。
    实测模型倾向于**连续输出多个组件对象**（想组合出一个多层界面），
    贪婪正则会把它们连成一段而解析失败，降级率因此高达 33%。
    契约改为组件序列后，这类输出成为合法结果而非失败。
    """
    depth, start, in_str, esc = 0, None, False, False
    for i, ch in enumerate(raw):
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch in "{[":
            if depth == 0: start = i
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0 and start is not None:
                yield raw[start:i + 1]; start = None


def _validate_one(obj) -> dict:
    if not isinstance(obj, dict):
        raise InvalidSchema("组件不是对象")
    comp = obj.get("component")
    if comp not in COMPONENTS:
        raise InvalidSchema(f"未知组件: {comp!r}")
    data = obj.get("data")
    if not isinstance(data, dict):
        raise InvalidSchema("data 字段缺失或类型错误")
    missing = [f for f in COMPONENTS[comp]["必需字段"] if f not in data]
    if missing:
        raise InvalidSchema(f"{comp} 缺少必需字段: {missing}")
    return obj


def _salvage(chunk: str) -> list:
    """整块解析失败时，退而求其次，逐个救出内部的合法对象。

    起因：模型偶尔会写出 {"component":"text","data":"content":"..."} 这类
    残缺 JSON。初版一旦整块 json.loads 失败就全盘放弃，
    连同数组里其它完全正常的组件一起丢掉。
    """
    out = []
    for inner in _iter_json_objects(chunk[1:-1] if chunk[:1] in "[{" else chunk):
        try:
            v = json.loads(inner)
        except json.JSONDecodeError:
            continue
        out.extend(v if isinstance(v, list) else [v])
    return out


def parse_and_validate(raw: str) -> list[dict]:
    """返回组件序列。

    容错策略：**局部失败不等于整体失败。**
    - 整块 JSON 解析失败 → 尝试救出内部的合法对象
    - 单个组件字段不全 → 丢掉该组件，保留其余组件
    - 一个合法组件都没有 → 才降级为纯文本

    产品理由：模型组合出 3 个组件、其中 1 个缺字段时，
    把另外 2 个正确的组件一起丢掉、退回一段纯文字，对用户是更差的结果。
    """
    found = []
    for chunk in _iter_json_objects(raw):
        try:
            v = json.loads(chunk)
            found.extend(v if isinstance(v, list) else [v])
        except json.JSONDecodeError:
            found.extend(_salvage(chunk))
    if not found:
        # 整个响应的括号都不平衡（实测：数组少了一个 "}"），
        # 扫描器一个块也吐不出来。直接在原文里找内部的合法对象。
        found = _salvage(raw)
    if not found:
        raise InvalidSchema("响应中未找到可解析的 JSON")

    ok, dropped = [], []
    for o in found:
        try:
            ok.append(_validate_one(o))
        except InvalidSchema as e:
            dropped.append(str(e))
    if not ok:
        raise InvalidSchema("无合法组件；" + "；".join(dropped[:2]))
    if dropped:
        ok[0].setdefault("_dropped", []).extend(dropped)
    return ok


def fallback(text: str) -> list[dict]:
    return [{"component": "text", "data": {"content": text}}]
