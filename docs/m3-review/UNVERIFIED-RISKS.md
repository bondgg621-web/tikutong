# Milestone 3 未验证范围与风险

- M3 只有设计规格，没有 runtime、Schema、测试、fixture、UI、判分、学习统计或答案生成能力，用户目前不能使用 M3 功能。
- 已人工裁决且证据未变化的冲突，在 prepare 与 reverify 路径下仍缺少唯一一致结果。
- run.json 在 transaction complete/aborted 附近崩溃时仍缺少确定性发布与恢复合同。
- 完整既有测试只覆盖 M0/M1/M2 回归，不覆盖任何 M3 行为。
- 三个直接符号链接测试因当前 Windows 平台能力跳过；junction 和 hardlink 防护由既有测试覆盖。
- M3 Schema 和实现尚未存在，因此规格的最终可实现性仍需在后续获批的计划和 TDD 阶段验证。
- 未发现被故意隐瞒的其他已知高风险缺陷；未实现和未验证范围不等于已通过。
