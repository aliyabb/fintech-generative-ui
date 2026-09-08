"""契约的三个版本。用于量化每次设计修改各自带来的可靠性变化。

v1  单组件契约；还款明细由模型输出；贪婪正则解析
v2  组件序列契约；还款明细由 calc.py 注入；严格解析（任一组件不合法即整体降级）
v3  在 v2 基础上加入分层容错：整块解析失败救内部对象，
    单个组件不合法则丢弃该组件保留其余

三个版本各自保留独立的解析器，保证任何人重跑 bench.py v1/v2/v3
都能复现出对应那一行的数字——否则"改进了多少"这个结论就无法核验。
"""
from __future__ import annotations
import json, re
from schema import COMPONENTS

_COMP_LINES = "\n".join(f"  {k}（{v['说明']}）: {', '.join(v['必需字段'])}"
                        for k, v in COMPONENTS.items())

SYSTEM_V1 = (
 "你是民信银行的界面生成器。不要输出段落文字，只输出一个 JSON 对象描述界面。\n"
 "格式：{\"component\":\"组件名\",\"data\":{...}}\n\n"
 "可用组件与必需字段：\n" + _COMP_LINES +
 "\n  repayment_schedule 还需输出 rows 字段（逐期明细数组）\n\n"
 "规则：\n"
 "1. 涉及金额或年化利率时，直接使用【计算结果】中的数值。\n"
 "2. product_compare 只呈现客观参数，disclaimer 须写明不构成投资建议。\n"
 "3. 参数不足时返回 clarify 组件追问。\n"
 "4. 只输出 JSON，不要解释文字或代码块标记。")


class InvalidSchema(Exception):
    pass


def _validate_one(obj) -> dict:
    if not isinstance(obj, dict):
        raise InvalidSchema("组件不是对象")
    comp = obj.get("component")
    if comp not in COMPONENTS:
        raise InvalidSchema(f"未知组件: {comp!r}")
    data = obj.get("data")
    if not isinstance(data, dict):
        raise InvalidSchema("data 字段缺失或类型错误")
    req = list(COMPONENTS[comp]["必需字段"])
    if comp == "repayment_schedule":
        req.append("rows")          # v1 要求模型自行输出明细
    missing = [f for f in req if f not in data]
    if missing:
        raise InvalidSchema(f"{comp} 缺少必需字段: {missing}")
    return obj


def parse_v1(raw: str) -> list[dict]:
    """初版解析：贪婪正则取单个对象。"""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise InvalidSchema("响应中未找到 JSON 对象")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise InvalidSchema(f"JSON 解析失败: {e}")
    return [_validate_one(obj)]


def parse_v2_strict(raw: str) -> list[dict]:
    """v2 的解析：接受组件序列，但任一组件不合法即整体失败（无救回）。"""
    from schema import _iter_json_objects
    found = []
    for chunk in _iter_json_objects(raw):
        try:
            val = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        found.extend(val if isinstance(val, list) else [val])
    if not found:
        raise InvalidSchema("响应中未找到可解析的 JSON")
    return [_validate_one_v2(o) for o in found]


def _validate_one_v2(obj) -> dict:
    """与 v1 的差别：repayment_schedule 不再要求模型输出 rows。"""
    from schema import COMPONENTS
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
