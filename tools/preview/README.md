# TikuTong Preview

TikuTong Preview 是题库通的本地预览与简单做题工具，用来查看 TikuTong 导出的 Standard Question Bank CSV。

它是一个 optional consumer，不是 TikuTong Core。TikuTong Core 是 question-bank compiler；Preview 不改变 Canonical QuestionBank JSON，也不定义新的 CSV 格式。

## How to use

1. 在本地浏览器打开 [`index.html`](index.html)。
2. 选择 TikuTong 生成的 Standard CSV。
3. 开始预览或练习，检查题目、选项、题型、参考答案和解析。

无需安装 npm package、启动服务器或执行 build step。

## Supported

Preview 直接读取冻结的 11-column Standard Question Bank CSV，支持：

* 单选题
* 多选题
* 判断题
* 空参考答案
* 空解析或已有解析
* CSV 中带引号的逗号和换行

CSV 的 11 列表头必须保持为：

```text
全局序号,试卷/章节,题型,题干,A,B,C,D,E,正确答案,解析
```

A–E 中没有使用的选项可以留空。缺失答案和缺失解析也允许留空，不需要手工修改 TikuTong 的输出。

## Blank-answer behavior

原资料没有参考答案时，Preview 仍允许用户选择答案，但不会显示“正确”或“错误”，不会加入错题统计，也不会把该题计入正确率分母。页面会明确提示：

> 原题未提供参考答案，本题不参与对错统计。

Preview 不猜测、不补写、也不创造标准答案。

## Privacy

题库内容在浏览器本地处理。Preview 不包含远程 API、CDN、analytics、登录、上传服务器或 bundled cloud service。

浏览器本身、扩展程序和用户设备的行为不由 TikuTong 控制；请仍按自己的隐私与数据使用政策处理题库。

## Not TikuTong Core

TikuTong Preview 只是用于检查和练习 Standard CSV 的 optional local tool。它不是 canonical compiler core、在线服务或考试平台，也不会读取 PDF、DOCX 或图片；这些来源应先由用户自己的 Agent 环境读取，再交给 TikuTong 生成标准输出。
