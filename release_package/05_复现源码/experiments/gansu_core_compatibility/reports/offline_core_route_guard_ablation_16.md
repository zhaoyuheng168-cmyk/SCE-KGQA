# Core Route Guard 离线消融实验报告

实验日期：2026-06-10  
协议：`gansu_offline_core_route_guard_ablation_v1`  
输入：冻结 16 题的既有 `V8-original` 输出  
生产影响：未修改或重新运行生产 V8 主脚本，未修改 Neo4j 或数据

## 1. Guard 决策边界

Guard 决策使用：

- 问题文本；
- V8 已识别主体、qtype 与答案；
- 统一 Core Schema；
- 只读图谱节点类型。

Guard 决策不使用：

- 冻结集 expected route；
- gold/reference answer；
- 生产 V8 源码修改。

Guard 从问题中最靠后的 Schema 类型表达推断目标类型，再结合主体图谱类型选择唯一合法 `RouteSpec`。仅当 V8 答案为空，或答案节点类型与目标类型冲突时，才使用 Core 类型化路径替换结果。

## 2. 总体结果

| 指标 | V8-original | V8 + Core Route Guard |
|---|---:|---:|
| Answer Exact Match | 75.0% | 100.0% |
| Macro F1 | 75.0% | 100.0% |
| Guard 触发率 | - | 25.0% |
| 纠正错误 | - | 4/16 |
| 引入错误 | - | 0/16 |
| Guard 路径选择准确率 | - | 100.0% |

## 3. 分路径结果

| 路径 | Original F1 | Guarded F1 | Guard 触发 | 引入错误 |
|---|---:|---:|---:|---:|
| `institution_products` | 100.0% | 100.0% | 0/4 | 0 |
| `product_provider` | 100.0% | 100.0% | 0/4 | 0 |
| `policy_products` | 50.0% | 100.0% | 2/4 | 0 |
| `policy_region_overview` | 50.0% | 100.0% | 2/4 | 0 |

Guard 保留了所有原本正确的通用 fallback 答案，包括 4 道 `product_provider`。它只纠正了答案为空或答案目标类型错误的 4 道政策题。

## 4. 纠正机制示例

问题：

```text

甘肃省科技型企业成长金融护航计划实施方案支持什么科技金融产品？
```

Guard 推断：

```text
主体图谱类型：Policy
问题目标类型：FinancialProduct
唯一合法 Core 路径：Policy -supports-> FinancialProduct
V8 实际答案类型：Enterprise
决策：replace_with_core
```

原始 V8 错误返回 1298 个企业；Guard 改用类型化路径后返回 7 个金融产品，与 canonical path reference 完全一致。

## 5. 实验意义

该结果证明统一 Core 不只是公开数据集适配层，还能作为真实产业 KGQA 的轻量路由约束与诊断组件：

- 无需重写生产 V8；
- 对正确答案保持旁路通过；
- 对目标类型冲突进行可解释纠正；
- 在冻结公共路径小样本上显著提升兼容性。

## 6. 证据限制

当前结果必须限定为：

> 在冻结的 16 道公共路径兼容性题上，离线 Core Route Guard 将 V8 相对 canonical path reference 的 Exact/F1 从 75% 提升至 100%，纠正 4 题且未引入错误。

当前不能直接声称：

- Guard 可在完整生产问题分布上达到 100%；
- Guard 不会损伤 Core 未覆盖的问题类型；
- 16 题结果可替代完整生产回归评测。

## 7. 下一步

下一步应构建独立回归集，不再使用这 16 道开发/消融题：

1. 从已有正式真实系统结果中抽取 40 至 80 道问题。
2. 覆盖 Core 公共路径、V8 扩展路径、通用关系、规则推理与拒答。
3. Guard 只允许在能够选择唯一 Core 路径且答案目标类型冲突时触发。
4. 报告触发数、纠正数、引入错误数与未覆盖问题旁路率。

只有独立回归集也保持低错误引入率后，才能把 Guard 作为稳定的真实系统增强证据写入论文主实验。
