# KQA Pro 对比与消融协议

所有方法共享同一份已冻结的top-5候选及执行结果，不重新生成候选。

## 对比组

- `BART top-1`：只采用生成器排名第一的程序。
- `BART top-5 + Schema`：模型分数加Schema合法性。
- `BART top-5 + execution feedback`：模型分数、可执行性与非空约束。
- `SCE full`：模型分数、Schema、执行反馈、非空约束、问题相关性和事实证据。
- `Oracle upper bound`：gold KoPL，仅作为执行上界，另表报告。

## 消融组

- `SCE w/o Schema`
- `SCE w/o execution feedback`
- `SCE w/o non-empty constraint`
- `SCE w/o question relevance`
- `SCE w/o fact-evidence bonus`

## 公平性

- 各组使用相同模型、相同五个候选、相同知识库和相同执行结果。
- 各组仅改变候选选择分数中的组件。
- 正式留出集不用于重新调节权重。
- 单独Schema结果下降也必须完整报告，不能选择性隐藏。
