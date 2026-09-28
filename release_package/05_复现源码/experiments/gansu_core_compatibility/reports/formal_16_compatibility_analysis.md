# Gansu V8 与统一 Core 正式 16 题兼容性实验分析

实验日期：2026-06-10  
协议：`gansu_v8_shared_core_compatibility_v1`  
样本：16 道冻结真实图谱问题，四条公共路径各 4 道  
参考答案：统一 Core `RouteSpec` 在同一只读 Neo4j 图谱上的类型化路径执行结果

## 1. 总体结果

| 指标 | 结果 |
|---|---:|
| Core 路径非空率 | 100.0% |
| V8 答案非空率 | 93.75% |
| V8 相对 Core Answer Exact Match | 75.0% |
| V8 相对 Core Precision | 75.0% |
| V8 相对 Core Recall | 75.0% |
| V8 相对 Core F1 | 75.0% |
| V8 专用/允许路由一致率 | 50.0% |

该实验不是“全对”的演示。结果清楚证明：

1. 统一 Core 的四条公共类型化路径可以直接作用于真实甘肃产业图谱，16/16 均获得非空答案。
2. 生产 V8 在 12/16 道题上与 Core canonical path reference 完全一致。
3. 生产 V8 的主要问题集中在政策主体的路由冲突，而不是图谱缺少答案。

## 2. 分路径结果

| Core 路径 | 题数 | Answer Exact / F1 | 路由一致率 | 结论 |
|---|---:|---:|---:|---|
| `institution_products` | 4 | 100.0% | 100.0% | 答案完全兼容；V8 实际依赖通用关系 fallback |
| `product_provider` | 4 | 100.0% | 0.0% | 答案完全兼容，但专用反向路径均被通用关系 fallback 代替 |
| `policy_products` | 4 | 50.0% | 50.0% | 两题正确，两题发生错误多跳路由 |
| `policy_region_overview` | 4 | 50.0% | 50.0% | 两题正确，两题错误返回企业集合 |

## 3. 失败分析

### 3.1 政策到产品误路由

`GCC_POLP_001`：

- 问题：甘肃省科技型企业成长金融护航计划实施方案支持什么科技金融产品？
- Core 路径：`Policy -supports-> FinancialProduct`
- Core 返回：7 个产品
- V8 错误路由：`multi_hop_agency_policy_enterprise`
- V8 返回：1298 个企业

这是典型的目标类型错判：问题明确询问金融产品，但 V8 将其路由为企业多跳查询。

`GCC_POLP_002`：

- 问题：银行业保险业科技金融高质量发展实施方案支持什么科技金融产品？
- Core 返回：6 个产品
- V8 错误路由：`multi_hop_policy_to_industry_overview_3hop`
- V8 结果：拒答，0 个答案

这是另一个目标类型错判：金融产品被错误解释为行业目标。

### 3.2 政策到地区误路由

`GCC_POLR_003` 与 `GCC_POLR_004`：

- 问题明确指定“政策支持的产品再到企业服务链”，目标为地区。
- Core 正确执行 `Policy -> FinancialProduct -> Enterprise -> Region`，各返回 15 个地区。
- V8 均错误路由为 `multi_hop_agency_policy_enterprise`。
- V8 分别返回 1298 和 1174 个企业，目标类型与问题不符。

这说明生产 V8 中存在更高优先级的“机构/政策到企业”显式多跳规则，抢占了 Schema 驱动的地区目标路径。

## 4. 路由一致率为何只有 50%

8 道机构/产品题均获得完全正确答案，但它们实际都走了：

```text
generic_relation_graph
-> relation_json_generic_fallback
```

其中：

- 4 道 `institution_products` 在冻结协议中允许通用关系路由，所以计为路由一致。
- 4 道 `product_provider` 期望专用反向关系路由 `product_provider`，但实际走通用关系路由，所以路由一致率为 0%，尽管答案全部正确。

因此，50% 路由一致率不能解释为“只有一半问题答对”。更准确的解释是：

> V8 有 75% 的答案与统一 Core 完全兼容，但只有 50% 的问题稳定进入预期专用/允许路径；部分正确答案依赖通用 fallback。

## 5. 性能观察

| 系统 | 平均耗时 |
|---|---:|
| 统一 Core 类型化路径查询 | 6.84 ms |
| 生产 V8 端到端 | 5411.17 ms |
| 生产 V8 端到端中位数 | 1225.94 ms |

两者不是完全等价的性能比较：生产 V8 包含路由、门控、fallback、证据与多跳规划，统一 Core 只执行已知 RouteSpec。但结果说明，确定性类型化路径可以作为低成本、低延迟的路由执行层。

## 6. 对论文主张的意义

当前证据支持：

> 从真实甘肃科技金融 KGQA 抽取的统一 Core，可以在不修改共享 Core 的前提下，对真实产业图谱执行四类公共类型化路径；其 canonical path reference 对生产 V8 具有诊断作用，并发现政策目标类型与多跳路由冲突。

这比只在 MetaQA 上报告结果更有说服力，因为统一 Core 不仅迁移到了公开数据集，还反过来诊断了来源真实系统。

当前仍不应声称：

- 生产 V8 已完全采用统一 Core；
- 统一 Core 覆盖生产 V8 的全部能力；
- 16 题小样本可以替代完整真实产业评测。

## 7. 下一步

下一阶段应保持冻结集不变，做一个明确的路由消融/修复对照：

1. `V8-original`：当前结果，Answer Exact/F1 75%。
2. `V8 + Core route guard`：在不改变图谱答案的情况下，用 Core 的主体类型、目标类型和 RouteSpec 约束政策题路由。
3. 对比四道失败政策题是否从错误企业/行业路径恢复到产品或地区路径。
4. 同时检查原有生产评测，确保 route guard 不损伤其他问题类型。

该对照可以直接形成论文中的真实系统消融实验：

> 移除或加入类型化 Core route guard 对真实产业 KGQA 路由稳定性的影响。
