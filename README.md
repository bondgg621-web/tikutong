# 题库通 TikuTong

**Agent-native Question Bank Compiler**

Turn existing questions from local documents into structured, portable question banks.

把散落在本地 PDF、Word、图片和文本中的已有题目，整理成结构化、可迁移的标准题库。

- Extract existing questions from local materials without inventing missing content.
- Normalize them into canonical QuestionBank JSON.
- Export the Standard Question Bank CSV.
- Preserve source provenance for every question.
- Use Agent-assisted extraction for single-choice, multiple-choice, and true/false material.

[Go to Quick Start](#quick-start)

## What TikuTong is

题库通 TikuTong (QBC) is an agent-native local question-bank compiler for existing questions. It helps a coding Agent extract question content from authorized local material, preserve where each question came from, validate a stable canonical representation, and export a standard CSV.

TikuTong organizes questions that already exist. It provides two routes:

- A deterministic route for one strict single-choice UTF-8 text or Markdown file.
- An assisted route for content that the user's Agent environment can read, including PDF, DOCX, image, irregular text, and mixed supported question types.

The assisted route begins after the Agent has read the source. QBC then validates the content-only handoff, creates local identities, builds QuestionBank v1.0, and reuses the existing CSV exporter.

## What TikuTong is not

TikuTong is not an AI quiz generator. It does not invent questions, fill missing answers, judge medical correctness, or silently repair uncertain extraction. The QBC core has no bundled PDF or DOCX parser, no bundled OCR, and no bundled LLM client.

## Installation

TikuTong is used directly from the repository's Skill package. It requires Python 3.12 or newer, and core processing has no third-party runtime dependencies. This repository does not publish an installable `qbc` package or automatically add its helper modules to Python's import path. Run Agent and Python helper commands from the Skill's scripts directory (or add that directory to the Python module search path):

```text
cd skills/curate-question-bank/scripts
```

## Quick Start

For a strict single-choice `.txt`, `.md`, or `.markdown` file, use the deterministic route:

```text
python -m qbproduction --input <questions.md> --output <question-bank.csv>
```

For PDF, DOCX, image, irregular text, multiple-choice, or true/false material, ask your Agent:

```text
Use TikuTong to read D:\资料\神经病学题库.pdf, extract the existing questions without filling missing answers, and save a canonical QuestionBank JSON plus the Standard Question Bank CSV.
```

The Agent should read [`skills/curate-question-bank/SKILL.md`](skills/curate-question-bank/SKILL.md), choose the assisted route, and use the maintained API recipe in [`assisted-intake-v1.md`](skills/curate-question-bank/references/assisted-intake-v1.md). The user does not need to manually construct QBC's internal objects.

## Supported inputs

The deterministic route reads one regular UTF-8 or UTF-8 BOM `.txt`, `.md`, or `.markdown` file that follows the strict `[single_choice]` grammar.

The assisted route can work with local source content that the user's Agent environment can read. A PDF, DOCX, or image is read by that environment—not by a QBC document reader. Image as an input source does not mean that QuestionBank v1.0 embeds images inside questions.

## Supported question types

The deterministic parser supports `single_choice` only.

The assisted route supports these types end to end:

- `single_choice`
- `multiple_choice`
- `true_false`

Multiple-choice answers remain arrays such as `["A", "C"]`. True/false questions use a boolean or null answer and `options=[]`. A missing answer remains null and is not inferred.

## Outputs

The canonical representation is one deterministic UTF-8 QuestionBank v1.0 JSON file. It preserves question, option, and source identities plus source locators.

The current exporter can also produce the Standard Question Bank CSV with exactly 11 columns:

```text
全局序号,试卷/章节,题型,题干,A,B,C,D,E,正确答案,解析
```

CSV is an export view, not the canonical storage format. Future format support should follow `Importer → QuestionBank → Exporter`, rather than direct conversion between every pair of formats.

## Example

[`examples/basic/`](examples/basic/) contains three small synthetic sources—a Markdown file, a real DOCX, and a real PNG—plus the content-only extraction handoff, canonical JSON, and exact CSV output. No copyrighted question bank or real examination material is included.

## Privacy and local-first boundary

QBC's validation, identity allocation, canonical serialization, and CSV projection are local deterministic code. Core processing requires no network call, cloud account, or bundled provider integration.

QBC does not guarantee that the user's Agent is offline. Network use, model providers, and source-reading behavior depend on the user's own Agent environment and policy.

## Current limitations

- No embedded media or asset contract in QuestionBank v1.0.
- No bundled PDF or DOCX parser.
- No bundled OCR or image-processing engine.
- No quiz UI, exam platform, GUI, or cloud service.
- No automatic medical correctness validation.
- No cross-run identity reconciliation or bank revision history.
- No bundled Moodle, QTI, or Anki adapter.
