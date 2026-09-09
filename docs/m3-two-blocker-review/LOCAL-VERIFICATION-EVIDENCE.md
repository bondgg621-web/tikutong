# Milestone 3 本机验证证据

验证日期：2026-08-29

## 文件指纹

进入本轮的正式基线核对通过：

- SHA-256 `6a076b8090a57d5a36fb4916f4c2f4e49e90687ce639e0636b0895c752e0375d`
- 640 行，71,339 bytes
- UTF-8，无 BOM，仅 LF，文件末尾恰好一个 LF

本机实际修订版冻结为：

- SHA-256 `84c4fbe8a02346df4b05761ca8345199c88ffb033c4fd9e7d9a42e7b643a4374`
- 680 行，82,953 bytes
- UTF-8，无 BOM，仅 LF，文件末尾恰好一个 LF

## 固定向量重算

- compact JSON：21 bytes，SHA-256 `8fe664ef5335c949424a347dd901141cb1a68b0e8db91a318991e26ba8f5dc11`，期望 bytes 与哈希均匹配。
- workspace JSON：39 bytes，SHA-256 `8c64fdc1fd7928af1840909f9afd41a55c9f9746375076129fdaeb8544d7bec9`，期望 bytes 与哈希均匹配。

## 静态闭环检查

- P1 共用裁决谓词、身份前置门禁、selected/rejected/considered 边界、无 recurrence、同一失败矩阵和 audit-only payload 全部通过。
- P2 canonical truth、run 单向依赖、成功终态顺序、aborted 失败终态、atomic run update、矛盾权威关系和 A–E crash points 全部通过。
- 原 7 个 blocker 与 4 项澄清保持闭合，旧矛盾措辞未回归。
- 未创建 M3 实施计划、Schema、runtime、测试或 fixture。

## 既有测试

从项目根目录使用本机既有 Python 3.12.10 环境运行一次完整测试：

- 退出码：0
- 661 passed
- 3 skipped
- 用时：39.28s

三个跳过项均是当前 Windows 主机无法创建直接符号链接的既有平台限制。该结果只证明 M0/M1/M2 未因文档修改回归，不是 M3 功能测试。

## 独立审查

独立审查核对冻结属性一致，并接受 P1/P2 闭环；但因 `archive_stale` 缺少合法 proposal payload 和 lineage binding，最终结果为 FAIL。
