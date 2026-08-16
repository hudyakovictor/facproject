#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const srcRoot = path.join(root, "src");
const include = /\.(tsx?|jsx?)$/;
const ignoredDirs = new Set(["test", "design-system"]);
const findings = [];

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return ignoredDirs.has(entry.name) ? [] : walk(full);
    return include.test(entry.name) ? [full] : [];
  });
}

function add(file, line, severity, rule, message, evidence) {
  findings.push({ file: path.relative(root, file), line, severity, rule, message, evidence: evidence.trim().slice(0, 180) });
}

const rules = [
  { re: /(?:MOCK_|mockData|mock_data|demoData|fakeData|from ["'][^"']*(?:fixture|mock)[^"']*["'])/i, severity: "critical", rule: "fixture-symbol", message: "импорт или использование fixture/mock-данных" },
  { re: /(?:\b(?:snr|confidence|albedo|publisher|collector|archive_url)\s*[:=]\s*[-+]?\d|\bsnr\s*=\s*\{|99\/100|100\/100|Arweave|IPFS|ERC-721)/i, severity: "high", rule: "suspicious-domain-value", message: "доменное значение нужно проверить на источник API" },
  { re: /(?:https?:\/\/web\.archive|РИА Новости|Иванов П\.|d1b7\.\.\.a9e4)/i, severity: "critical", rule: "synthetic-provenance", message: "похоже на синтетическую provenance-заглушку" },
  { re: /(?:setTimeout\([^\n]*\d{3,}|faker\.)/, severity: "high", rule: "synthetic-runtime", message: "синтетическая генерация или задержка" },
  { re: /(?:КЛАСТЕР #|clusterId|hardcoded|\bDEMO\b)/i, severity: "high", rule: "demo-copy", message: "текст или поле явно указывает на демонстрационный сценарий" },
];

for (const file of walk(srcRoot)) {
  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
  lines.forEach((line, index) => {
    for (const rule of rules) {
      if (rule.re.test(line)) add(file, index + 1, rule.severity, rule.rule, rule.message, line);
    }
  });
}

const imports = findings.filter((f) => f.rule === "fixture-symbol");
const critical = findings.filter((f) => f.severity === "critical");
const high = findings.filter((f) => f.severity === "high");
const uniqueFiles = [...new Set(findings.map((f) => f.file))];
const report = { generatedAt: new Date().toISOString(), scannedRoot: "src", filesWithFindings: uniqueFiles.length, findings, summary: { critical: critical.length, high: high.length, total: findings.length, fixtureImports: imports.length } };
const output = process.env.MOCK_AUDIT_JSON ?? path.join(root, "mock-audit.json");
fs.writeFileSync(output, JSON.stringify(report, null, 2) + "\n");

console.log(`MOCK AUDIT · ${uniqueFiles.length} файлов с находками · ${findings.length} совпадений`);
for (const file of uniqueFiles) {
  const fileFindings = findings.filter((f) => f.file === file);
  console.log(`\n${file}`);
  for (const finding of fileFindings) console.log(`  ${finding.severity.toUpperCase()} ${finding.line}: ${finding.message} · ${finding.evidence}`);
}
console.log(`\nИтого: critical=${critical.length}, high=${high.length}, total=${findings.length}`);
console.log(`Отчёт: ${path.relative(root, output)}`);
process.exitCode = critical.length ? 2 : 0;
