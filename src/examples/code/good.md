## 改动清单
- `checks/validate_output.py`：新增章节与字数校验
- `tests/cases.jsonl`：补 3 条 learn 用例

## 关键 diff 摘要
```python
if missing:
    errors.append(f"缺少章节: {name}")
```
遍历全部章节后统一报错，不提前退出，方便一次看完所有问题。

## 验证方式
`python checks/validate_output.py --family learn --file src/examples/learn/good.md`
预期输出：`OK learn`

## 回滚点
`git revert <sha>`。本次不涉及数据迁移，回滚无副作用。

## 自检
| 依据 | 骨架 | 字数 | 例外 | 无编造 |
|---|---|---|---|---|
| ✔ | ✔ | ✔ | ✔ | ✔ |
