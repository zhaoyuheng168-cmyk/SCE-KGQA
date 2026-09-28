# KQA Pro 非 Oracle 迁移实验协议

## 1. 为什么 99.96% 不是迁移正确率

现有 `11792/11797` 使用数据集提供的标准 KoPL 程序和官方规则执行语义，
测量的是程序执行上界。它不包含自然语言理解和程序生成，不能作为
SCE-KGQA 的端到端迁移准确率。

## 2. 真正的盲测链路

```text
question-only input
  -> Bart Program top-5 candidates
  -> SCE Schema legality scoring
  -> evidence-aware candidate execution
  -> answer prediction
  -> isolated evaluator joins gold answer
```

生成与执行阶段只能读取：

- `question_id`
- `source_index`
- `question`
- KQA Pro `kb.json`
- 从训练集或知识库构建的 Schema

严禁读取：

- 验证集 gold KoPL
- SPARQL
- gold answer
- choices

## 3. 实验组

| 组别 | 计划来源 | Schema重排 | 证据状态 | 作用 |
|---|---|---:|---:|---|
| Oracle upper bound | gold KoPL | 否 | 官方语义 | 执行上界 |
| Bart top-1 | 问题文本 | 否 | 基础执行 | 生成器基线 |
| Bart top-5 + Schema | 问题文本 | 是 | 基础执行 | Schema贡献 |
| SCE transfer full | 问题文本 | 是 | 是 | 主迁移结果 |
| Full w/o Schema | 问题文本 | 否 | 是 | Schema消融 |
| Full w/o evidence | 问题文本 | 是 | 否 | 证据消融 |

## 4. 指标

- Answer exact match
- Program executable rate
- Schema-valid program rate
- Empty-answer rate
- Qualifier/evidence subset exact match
- Multihop subset exact match
- Average latency

Oracle数值单列，不与非Oracle结果混写。

## 5. 当前实施状态

- Oracle上界：完成，`11792/11797`。
- 盲输入生成器：完成。
- Bart top-5候选生成器：完成。
- 独立F盘环境安装脚本：完成。
- Schema候选重排器：完成。
- SCE证据执行适配器：完成。
- 隔离评分器：完成，尚未运行正式评分。
- 消融表：待正式评分后生成。
