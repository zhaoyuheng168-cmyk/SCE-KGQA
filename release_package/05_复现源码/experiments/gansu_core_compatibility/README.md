# Gansu V8 与统一 Core 小样本兼容性实验

该实验在同一份只读甘肃 Neo4j 图谱上比较：

- 生产 Gansu V8 的端到端路由与答案；
- 统一 Core 的 `GansuFinanceAdapter + RouteSpec + build_match_cypher` 确定性路径答案。

冻结集包含 16 道问题，每条公共路径各 4 道：

- `institution_products`
- `product_provider`
- `policy_products`
- `policy_region_overview`

## 协议边界

统一 Core 的类型化路径结果是本兼容性实验的 canonical path reference。实验衡量生产 V8 在公共路径上的兼容程度，不是对完整生产 V8 能力的总体评测。

由于 Core reference 来自同一图谱上的声明路径，Core 自身的答案不应被报告为独立准确率；应报告 V8 相对 canonical path reference 的 Route Agreement、Exact Match、Precision、Recall 和 F1。

## 结构验证

只运行 Core，不调用生产 V8：

```bash
cd /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME
source /home/vipuser/miniconda3/etc/profile.d/conda.sh
conda activate base
source scripts/加载运行环境变量.sh

cd deliverables/paper_submission_system_20260522_114215
python experiments/gansu_core_compatibility/scripts/run_gansu_v8_core_compatibility.py \
  --mode core \
  --out-dir experiments/gansu_core_compatibility/results/core_path_validation
```

## 正式 16 题对照

该命令会真实调用生产 V8 16 次：

```bash
cd /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME
source /home/vipuser/miniconda3/etc/profile.d/conda.sh
conda activate base
source scripts/加载运行环境变量.sh

cd deliverables/paper_submission_system_20260522_114215
nice -n 19 ionice -c 3 python \
  experiments/gansu_core_compatibility/scripts/run_gansu_v8_core_compatibility.py \
  --mode both \
  --out-dir experiments/gansu_core_compatibility/results/formal_16 \
  --confirm RUN_GANSU_V8_CORE_COMPATIBILITY_16 \
  2>&1 | tee experiments/gansu_core_compatibility/formal_16.log
```

输出：

- `results.jsonl`：逐题路径、答案与运行信息；
- `metrics.csv`：逐题兼容性指标；
- `summary.json`：总体和分路径汇总。

## 离线 Core Route Guard 消融

该实验读取已经完成的 `V8-original` 结果，不再次调用 V8，也不修改生产主脚本。
Guard 决策只使用问题文本、V8 主体、V8 路由与答案、Core Schema 和只读节点类型。

```bash
cd /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME
source /home/vipuser/miniconda3/etc/profile.d/conda.sh
conda activate base
source scripts/加载运行环境变量.sh

cd deliverables/paper_submission_system_20260522_114215
python experiments/gansu_core_compatibility/scripts/run_offline_core_route_guard_ablation.py \
  --out-dir experiments/gansu_core_compatibility/results/offline_core_route_guard_16
```

## 独立 80 题回归

该实验从既有正式 1300 题结果中分层抽取与冻结 16 题零重叠的独立样本，
使用正式 task-aware gold 检查 Guard 是否引入回归。

```bash
cd /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME
source /home/vipuser/miniconda3/etc/profile.d/conda.sh
conda activate base
source scripts/加载运行环境变量.sh

cd deliverables/paper_submission_system_20260522_114215
python experiments/gansu_core_compatibility/scripts/run_guard_independent_regression.py \
  --candidate-count 40 \
  --bypass-count 40 \
  --out-dir experiments/gansu_core_compatibility/results/guard_independent_regression_80
```
