# Milestone 3 规格修订清单

本轮只修改 M3 规格和必要的审查/交接文档，没有实现 M3 功能。

## 基线与候选

- 本机失败基线：`07537636afe4acc64089c9d4b0f1cabb148b94bc894c0d1b963e1251d6bb8174`
- 网页候选：`c6ee8cd11fa6dd47444d901e91c5c9ff42814a6854d4fc9e28e1768e15a83f61`
- 本机实际修订版：`6a076b8090a57d5a36fb4916f4c2f4e49e90687ce639e0636b0895c752e0375d`

## 已完成的原记录修订

- 收紧 prepare/reverify/confirmation 的 before state、不可变 operation artifact 和 transaction 绑定。
- 贯通 proposal base lineage，阻止旧 proposal 跨状态或跨 transaction 重放。
- 定义无 Candidate 的 source-level payload，并给 stable issue key 加入 question source 命名空间。
- 消除 commit 不存在与损坏、pointer before/after/unknown、complete/aborted 的原有歧义。
- 完整吸收两次 M3 snapshot 之间的全部 registry path history。
- 身份不一致统一为 canonical 不变、脱敏 run-level finding、operation failed。
- 冻结 blocking level 映射、nullable 总序、run finding 形状和 ReviewItem recurrence/resolve/supersession 约束。

## 本机额外最小收口

网页候选仍保留两处原阻断歧义，本机只做了对应的必要修订：

- operation artifact 从开放的“至少绑定”收紧为按 operation 的互斥精确白名单，并阻止 operation relabel。
- transaction 状态明确正常 `1 -> 2 -> 3 complete` 与唯一合法的 pre-commit `1 -> 3 aborted` 分支。

## 未继续修改

新的独立复审发现两个此前未列入本轮授权修订范围的 blocker。本轮按要求停止，没有继续自由设计或修改规格。
