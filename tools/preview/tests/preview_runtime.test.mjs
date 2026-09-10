import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath } from "node:url";


const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const PREVIEW_PATH = path.resolve(TEST_DIR, "..", "index.html");
const TRIAL_CSV_PATH = path.resolve(
  TEST_DIR,
  "..",
  "..",
  "..",
  "examples",
  "user-trial",
  "expected-standard-question-bank.csv",
);
const STANDARD_HEADERS = [
  "全局序号",
  "试卷/章节",
  "题型",
  "题干",
  "A",
  "B",
  "C",
  "D",
  "E",
  "正确答案",
  "解析",
];

const html = fs.readFileSync(PREVIEW_PATH, "utf8");
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
  .map((match) => match[1])
  .join("\n");
const csvFixture = fs.readFileSync(TRIAL_CSV_PATH, "utf8");

const elements = new Map();
function fakeElement(id = "") {
  return {
    id,
    style: {},
    dataset: {},
    disabled: false,
    innerHTML: "",
    innerText: "",
    textContent: "",
    value: "",
    className: "",
    children: [],
    classList: {
      add() {},
      remove() {},
      toggle() {},
    },
    setAttribute() {},
    addEventListener() {},
    appendChild(child) {
      this.children.push(child);
    },
    removeChild() {},
    click() {},
  };
}

const storage = new Map();
const context = vm.createContext({
  console,
  TextDecoder,
  Uint8Array,
  URL,
  Blob,
  document: {
    body: fakeElement("body"),
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, fakeElement(id));
      return elements.get(id);
    },
    querySelectorAll() {
      return [];
    },
    createElement(tag) {
      return fakeElement(tag);
    },
    createTextNode(text) {
      return { textContent: text };
    },
  },
  localStorage: {
    getItem(key) {
      return storage.has(key) ? storage.get(key) : null;
    },
    setItem(key, value) {
      storage.set(key, value);
    },
    removeItem(key) {
      storage.delete(key);
    },
  },
  confirm() {
    return true;
  },
});

vm.runInContext(script, context);
context.csvFixture = csvFixture;

function evaluate(expression) {
  return vm.runInContext(expression, context);
}

function evaluateJson(expression) {
  return JSON.parse(evaluate(`JSON.stringify(${expression})`));
}

function loadTrial() {
  evaluate("processData(parseCSV(csvFixture)); validateStandardCsvHeaders(parseCSV.lastHeaders);");
}

test("loads the exact UTF-8 11-column Standard CSV contract", () => {
  evaluate("parseCSV(csvFixture)");
  assert.deepEqual(evaluateJson("parseCSV.lastHeaders"), STANDARD_HEADERS);
  assert.doesNotThrow(() => evaluate("validateStandardCsvHeaders(parseCSV.lastHeaders)"));
});

test("loads the 12-question standard trial", () => {
  loadTrial();
  assert.equal(evaluate("allQuestions.length"), 12);
});

test("grades a single-choice answer", () => {
  loadTrial();
  assert.equal(evaluate('recordAnswer(allQuestions[0], "B")'), true);
});

test("grades multiple-choice labels as a set in display order", () => {
  loadTrial();
  assert.equal(evaluate('recordAnswer(allQuestions[5], "EAC")'), true);
  assert.equal(evaluate("allQuestions[5].userAnswer"), "ACE");
});

test("grades a true answer", () => {
  loadTrial();
  assert.equal(evaluate('recordAnswer(allQuestions[8], "A")'), true);
});

test("grades a false answer", () => {
  loadTrial();
  assert.equal(evaluate('recordAnswer(allQuestions[9], "B")'), true);
});

test("does not grade a blank-answer single-choice question", () => {
  loadTrial();
  assert.equal(evaluate('recordAnswer(allQuestions[3], "A")'), null);
  assert.equal(evaluate("allQuestions[3].isCorrect"), null);
});

test("does not grade a blank-answer multiple-choice question", () => {
  loadTrial();
  assert.equal(evaluate('recordAnswer(allQuestions[7], "AC")'), null);
  assert.equal(evaluate("allQuestions[7].isCorrect"), null);
});

test("does not grade a blank-answer true/false question", () => {
  loadTrial();
  assert.equal(evaluate('recordAnswer(allQuestions[10], "B")'), null);
  assert.equal(evaluate("allQuestions[10].isCorrect"), null);
});

test("does not put a blank-answer question in the wrong list", () => {
  loadTrial();
  evaluate('recordAnswer(allQuestions[3], "A")');
  evaluate('recordAnswer(allQuestions[0], "A")');
  assert.equal(evaluate("getMistakes().length"), 1);
  assert.equal(evaluate("getMistakes()[0].id"), "1");
});

test("does not include blank-answer questions in the score denominator", () => {
  loadTrial();
  evaluate('recordAnswer(allQuestions[0], "B")');
  evaluate('recordAnswer(allQuestions[3], "A")');
  evaluate('recordAnswer(allQuestions[4], "ABE")');
  assert.deepEqual(evaluateJson("getScoreStats(allQuestions)"), {
    graded: 2,
    correct: 2,
    wrong: 0,
    accuracy: 100,
  });
});

test("preserves explanations including a quoted newline", () => {
  loadTrial();
  assert.match(evaluate("allQuestions[2].explanation"), /O7-A/);
  assert.match(evaluate("allQuestions[11].explanation"), /\n/);
});

test("accepts an empty explanation and exposes a clear display fallback", () => {
  loadTrial();
  assert.equal(evaluate("allQuestions[0].explanation"), "");
  assert.equal(evaluate('formatExplanation("")'), "原题未提供解析。");
});

test("accepts quoted commas and quoted newlines", () => {
  context.edgeCsv = [
    STANDARD_HEADERS.join(","),
    '13,边界测试,单选题,"第一行,含逗号\\n第二行",甲,乙,,,,A,"解析第一行,含逗号\\n解析第二行"',
  ].join("\n").replaceAll("\\n", "\n");
  evaluate("const parsedEdge = parseCSV(edgeCsv); validateStandardCsvHeaders(parseCSV.lastHeaders); processData(parsedEdge);");
  assert.equal(evaluate("allQuestions.length"), 1);
  assert.equal(evaluate("allQuestions[0].text"), "第一行,含逗号\n第二行");
  assert.equal(evaluate("allQuestions[0].explanation"), "解析第一行,含逗号\n解析第二行");
});

test("accepts empty D and E cells", () => {
  loadTrial();
  assert.equal(evaluate("allQuestions[2].options.E"), "");
});

test("is branded as the optional TikuTong Preview consumer", () => {
  assert.match(html, /<title>TikuTong Preview<\/title>/);
  assert.match(html, /<h3 class="product-title">题库通<\/h3>/);
  assert.match(html, /<div class="product-cn-subtitle">本地预览与做题工具<\/div>/);
  assert.match(html, /<div class="product-en-title">TikuTong Preview<\/div>/);
  assert.match(html, /\.product-title\s*\{[^}]*font-size:\s*24px/s);
  assert.match(html, /\.product-en-title\s*\{[^}]*font-size:\s*12px/s);
  assert.match(html, /Optional local preview &amp; practice tool for TikuTong Standard CSV\./);
  assert.match(html, /not part of the canonical compiler core/i);
});

test("contains no remote dependency or network request", () => {
  assert.doesNotMatch(html, /<script[^>]+src=/i);
  assert.doesNotMatch(html, /<link[^>]+href=/i);
  assert.doesNotMatch(html, /https?:\/\//i);
  assert.doesNotMatch(html, /\bfetch\s*\(/i);
  assert.doesNotMatch(html, /XMLHttpRequest|WebSocket|analytics/i);
});

test("contains no absolute developer path or legacy product name", () => {
  assert.doesNotMatch(html, /[A-Za-z]:\\|\/Users\/|\/home\//);
  assert.doesNotMatch(html, /quiz_tool|离线题库答题器|AI 出题|自动补答案/i);
});
