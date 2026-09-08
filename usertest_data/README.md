# 用户测试原始数据

每名被试完成 `docs/usertest.html` 后会导出一段 JSON，存为 `P1.json`、`P2.json`… 放在本目录。

然后运行：

```bash
python3 src/analyze_usertest.py
```

**本目录为空时，分析脚本不会产出任何指标。** 这是刻意的：
在测试真正执行之前，README 与演示页上理解度相关的数字一律保持"未测量"。
