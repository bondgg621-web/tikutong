# Milestone 3 本机验证证据

验证日期：2026-08-29

## 文件指纹

失败基线核对通过：

- SHA-256 `07537636afe4acc64089c9d4b0f1cabb148b94bc894c0d1b963e1251d6bb8174`
- 623 行，56,368 bytes
- UTF-8，无 BOM，仅 LF，文件末尾恰好一个 LF

网页候选包内规格完整性核对通过：

- SHA-256 `c6ee8cd11fa6dd47444d901e91c5c9ff42814a6854d4fc9e28e1768e15a83f61`
- 640 行，70,589 bytes
- UTF-8，无 BOM，仅 LF，文件末尾恰好一个 LF

本机实际修订版冻结为：

- SHA-256 `6a076b8090a57d5a36fb4916f4c2f4e49e90687ce639e0636b0895c752e0375d`
- 640 行，71,339 bytes
- UTF-8，无 BOM，仅 LF，文件末尾恰好一个 LF

## 固定向量重算

- compact JSON：21 bytes，SHA-256 `8fe664ef5335c949424a347dd901141cb1a68b0e8db91a318991e26ba8f5dc11`，期望 bytes 与哈希均匹配。
- workspace JSON：39 bytes，SHA-256 `8c64fdc1fd7928af1840909f9afd41a55c9f9746375076129fdaeb8544d7bec9`，期望 bytes 与哈希均匹配。
- 第一次封装命令因 shell 字符编码导致 Python SyntaxError，未进入项目代码；改用纯 ASCII Unicode/hex 输入后独立重算通过。

## 7 个阻断点与 4 项澄清

结构检查全部命中预期闭环，并确认旧的矛盾措辞已删除：

1. prepare/reverify 与 plan.before、精确 operation artifact 白名单闭合。
2. proposal direct/prepare_result 基线贯穿 confirmation 和 transaction。
3. 无 Candidate source-level proposal 有明确 null/empty payload。
4. stable issue key 包含 question_source_id。
5. commit 不存在/损坏、before/after/unknown pointer、complete/aborted 合法跳转已区分。
6. successor manifest 完整吸收 intervening path_history suffix。
7. Candidate/Option identity mismatch 统一为 canonical 不变、脱敏 finding、operation failed。
8. blocking_level 保持冻结 issue-code 映射。
9. nullable 字段使用确定性 type-tag 总序。
10. run_findings 只允许固定结构化脱敏字段。
11. ReviewItem recurrence、resolve、supersession 语义与合法性约束分离。

## 既有测试

从项目根目录使用本机既有 Python 3.12.10 环境运行完整测试：

- 退出码：0
- 661 passed
- 3 skipped
- 用时：41.08s

三个跳过项均是当前 Windows 主机无法创建直接符号链接的既有平台限制。该结果只证明 M0/M1/M2 未因文档修改回归，不是 M3 功能测试。

## 范围核对

- 未创建 M3 实施计划。
- 未创建 M3 Schema、runtime、测试或 fixture。
- 未修改 Skill metadata、M0/M1/M2 冻结契约。
- 未联网、未安装依赖、未初始化 Git、未创建 worktree。
