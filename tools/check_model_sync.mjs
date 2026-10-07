/**
 * 开发用工具：校验「schema 里的类型清单」与「models 里的类型常量」是否一致。
 *
 * 背景：``resources.resource_type`` 的 CHECK 约束（SQL）与
 * ``core/models/__init__.py`` 的 ``RESOURCE_TYPES`` 是同一份语义的两个副本。
 * 一旦有人只改一边，就会出现「模型允许写入、数据库拒绝」或反过来的隐蔽 bug。
 *
 * 用法：  node tools/check_model_sync.mjs
 * 退出码：0 = 一致；1 = 不一致（可挂到 CI / 提交前检查）
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");

const schemaSrc = readFileSync(join(root, "core", "database", "schema.py"), "utf8");
const modelsSrc = readFileSync(join(root, "core", "models", "__init__.py"), "utf8");

function section(source, label, opener) {
  const m = source.match(opener);
  if (!m) throw new Error(`未能在源码中找到 ${label}`);
  return m[1];
}

const checkBody = section(
  schemaSrc,
  "resources.resource_type 的 CHECK 约束",
  /resource_type IN \(([\s\S]*?)\)\)/,
);
const sqlTypes = [...checkBody.matchAll(/'([a-z_]+)'/g)].map((x) => x[1]);

const resourceTypesBody = section(
  modelsSrc,
  "RESOURCE_TYPES",
  /RESOURCE_TYPES[^=]*=\s*\(([\s\S]*?)\)/,
);
const modelTypes = [...resourceTypesBody.matchAll(/"([a-z_]+)"/g)].map((x) => x[1]);

const autoBody = section(
  modelsSrc,
  "AUTO_DETECTABLE_TYPES",
  /AUTO_DETECTABLE_TYPES[^=]*=\s*\(([\s\S]*?)\)/,
);
const autoTypes = [...autoBody.matchAll(/"([a-z_]+)"/g)].map((x) => x[1]);

const sameSet = (a, b) =>
  a.length === b.length && [...a].sort().join(",") === [...b].sort().join(",");

const issues = [];

if (!sameSet(sqlTypes, modelTypes)) {
  issues.push("resource_type 的 CHECK 约束与 RESOURCE_TYPES 不一致");
}

const modelTypeSet = new Set(modelTypes);
const stray = autoTypes.filter((t) => !modelTypeSet.has(t));
if (stray.length) {
  issues.push(`AUTO_DETECTABLE_TYPES 含未定义类型：${stray.join(", ")}`);
}

// 自动识别只允许给出「可靠」结论；'mod' 可自动识别（manifest），细分美术类型不行。
const forbiddenAuto = autoTypes.filter((t) => ["skin", "eyes", "hair", "accessory"].includes(t));
if (forbiddenAuto.length) {
  issues.push(`AUTO_DETECTABLE_TYPES 不应包含细分美术类型：${forbiddenAuto.join(", ")}`);
}

console.log(`SQL CHECK 类型（${sqlTypes.length}）：${sqlTypes.join(", ")}`);
console.log(`RESOURCE_TYPES（${modelTypes.length}）：${modelTypes.join(", ")}`);
console.log(`AUTO_DETECTABLE_TYPES（${autoTypes.length}）：${autoTypes.join(", ")}`);

if (issues.length) {
  for (const issue of issues) console.log(`❌ ${issue}`);
  process.exit(1);
}

console.log("✅ schema 与 models 类型清单一致");
process.exit(0);
