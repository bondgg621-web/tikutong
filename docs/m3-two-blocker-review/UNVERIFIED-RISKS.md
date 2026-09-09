# Milestone 3 未验证范围与风险

- M3 仍只有设计规格，没有 runtime、Schema、测试、fixture、UI、判分、学习统计或答案生成能力，用户目前不能使用 M3 功能。
- `archive_stale` 是允许的 confirmation 动作，但当前 proposal 没有 stale 分支，导致该路径不可机械实现和验收。
- 完整既有测试只覆盖 M0/M1/M2 回归，不覆盖任何 M3 行为。
- 三个直接符号链接测试因当前 Windows 平台能力跳过；junction 和 hardlink 防护由既有测试覆盖。
- P1/P2 通过本轮规格复核，但 M3 Schema 和实现尚不存在，最终可实现性仍需后续获批的计划和 TDD 验证。
- 未发现被故意隐瞒的其他已知高风险缺陷；未实现和未验证范围不等于已通过。
