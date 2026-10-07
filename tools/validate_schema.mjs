/**
 * 开发用工具：在没有 Python 的环境下校验 SQLite schema 是否合法。
 *
 * 它直接从 core/database/schema.py 抽取 DDL，在内存库里执行，然后打印表清单。
 * Python 装好后（Phase 1）优先使用 `python -m pytest tests/ -q`。
 *
 * 用法：  node tools/validate_schema.mjs
 */

import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const schemaPath = join(here, "..", "core", "database", "schema.py");
const source = readFileSync(schemaPath, "utf8");

function extract(name) {
  const re = new RegExp(`^${name}\\s*=\\s*"""([\\s\\S]*?)"""`, "m");
  const m = source.match(re);
  if (!m) throw new Error(`未能在 schema.py 中找到 ${name}`);
  return m[1];
}

const tableList = (name) => {
  const m = source.match(new RegExp(`^${name}[^=]*=\\s*\\(([\\s\\S]*?)\\)`, "m"));
  if (!m) throw new Error(`未能在 schema.py 中找到 ${name}`);
  return [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]);
};

const v1Tables = tableList("V1_TABLES");
const v2Tables = tableList("V2_TABLES");
const expected = [...v1Tables, ...v2Tables];

const db = new DatabaseSync(":memory:");
db.exec("PRAGMA foreign_keys = ON");

const ddl = extract("_V1_SQL");
db.exec(ddl);

// --- v2 迁移：顺序必须与 db.initialize() 一致（先幂等加列，再跑 DDL）---
const resourceColumns = db
  .prepare("PRAGMA table_info(resources)")
  .all()
  .map((r) => r.name);
if (!resourceColumns.includes("card_marker")) {
  db.exec("ALTER TABLE resources ADD COLUMN card_marker TEXT");
}
db.exec(extract("_V2_SQL"));

let ftsEnabled = true;
let ftsError = "";
try {
  db.exec(extract("_V1_FTS_SQL"));
} catch (err) {
  ftsEnabled = false;
  ftsError = err.message;
}

// 业务表（排除 FTS 影子表）
const tables = db
  .prepare(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
  )
  .all()
  .map((r) => r.name)
  .filter((n) => !n.includes("resources_fts"));

const missing = expected.filter((t) => !tables.includes(t));
const extra = tables.filter((t) => !expected.includes(t));

console.log(`DDL 执行：OK`);
console.log(`业务表数量：${tables.length}（期望 ${expected.length}）`);
console.log(`FTS5/trigram：${ftsEnabled ? "已启用" : "不可用（回退 LIKE 搜索）"}`);
if (!ftsEnabled) console.log(`  └ ${ftsError}`);

// 幂等性：Phase 0 的 initialize() 允许重复调用，DDL 必须全部 IF NOT EXISTS。
try {
  db.exec(ddl);
  db.exec(extract("_V2_SQL"));
  console.log(`DDL 重复执行（幂等，v1+v2）：OK`);
} catch (err) {
  console.log(`DDL 重复执行（幂等）：失败（${err.message}）`);
  process.exitCode = 1;
}

// 冒烟：插入一条资源 + 一条未安装 MOD 依赖，并作一次 FTS 查询
db.exec(
  "INSERT INTO resources(file_path, file_path_key, resource_type, display_name, name) " +
    "VALUES ('D:/c.png', 'd:/c.png', 'character_card', '白峰 一乃', '白峰一乃')",
);
db.exec(
  "INSERT INTO resource_mods(resource_id, mod_guid, mod_id) " +
    "VALUES ((SELECT id FROM resources WHERE file_path_key='d:/c.png'), 'com.example.missing', NULL)",
);
const dep = db
  .prepare("SELECT mod_guid, mod_id FROM resource_mods")
  .all();
console.log(`未安装 MOD 依赖可记录：${dep.length === 1 && dep[0].mod_id === null ? "OK" : "失败"}`);

// ---- v2 冒烟：插件 / 逐槽位依赖 / 多作者 / card_marker ----
const rid = db.prepare("SELECT id FROM resources WHERE file_path_key='d:/c.png'").get().id;

db.exec(
  "UPDATE resources SET card_marker = 'KoiKatuCharaSun' WHERE id = " + rid,
);
const marker = db.prepare("SELECT card_marker FROM resources WHERE id = ?").get(rid).card_marker;
console.log(`card_marker 可写入：${marker === "KoiKatuCharaSun" ? "OK" : "失败"}`);

for (const guid of ["moreAccessories", "KSOX"]) {
  db.prepare("INSERT INTO resource_plugins(resource_id, plugin_guid) VALUES (?, ?)").run(rid, guid);
}
const pluginCount = db.prepare("SELECT count(*) AS c FROM resource_plugins WHERE resource_id = ?").get(rid).c;
const modCount = db.prepare("SELECT count(*) AS c FROM mods").get().c;
console.log(`插件与 MOD 分离：${pluginCount === 2 && modCount === 0 ? "OK" : "失败"}`);

// 同一个 MOD 用在 3 个槽位 → 3 行记录、1 个唯一 MOD
const usageInsert = db.prepare(
  "INSERT INTO resource_mod_usages(resource_id, mod_guid, property, slot) VALUES (?, ?, ?, ?)",
);
for (const [prop, slot] of [
  ["outfit6.accessory10.ChaFileAccessory.PartsInfo.id", 10],
  ["outfit6.accessory11.ChaFileAccessory.PartsInfo.id", 11],
  ["outfit2.accessory1.ChaFileAccessory.PartsInfo.id", 1],
]) {
  usageInsert.run(rid, "com.Quokka.sisterveilb", prop, slot);
}
const usageRows = db.prepare("SELECT count(*) AS c FROM resource_mod_usages").get().c;
const uniqueMods = db
  .prepare("SELECT count(DISTINCT mod_guid) AS c FROM resource_mod_usages")
  .get().c;
console.log(
  `逐槽位依赖（3 记录 / 1 唯一 MOD）：${usageRows === 3 && uniqueMods === 1 ? "OK" : "失败"}`,
);

db.exec("INSERT INTO authors(name, name_key) VALUES ('Evaan','evaan')");
db.exec(
  "INSERT INTO resource_authors(resource_id, author_id, ordinal, raw_name) " +
    `VALUES (${rid}, (SELECT id FROM authors WHERE name_key='evaan'), 0, 'Evaan')`,
);
const authorLinks = db.prepare("SELECT count(*) AS c FROM resource_authors").get().c;
console.log(`多作者关联可写入：${authorLinks === 1 ? "OK" : "失败"}`);

// card_marker 不是唯一键：同一角色两个版本可以共存
db.exec(
  "INSERT INTO resources(file_path, file_path_key, resource_type, card_marker) " +
    "VALUES ('D:/old.png','d:/old.png','character_card','KoiKatuChara')",
);
const markers = db
  .prepare("SELECT count(*) AS c FROM resources WHERE card_marker IS NOT NULL")
  .get().c;
console.log(`KK/KKS 两种 marker 可共存：${markers === 2 ? "OK" : "失败"}`);

// ---- 约束实测 ----
const expectThrow = (label, sql) => {
  try {
    db.exec(sql);
    console.log(`${label}：失败（本应被拒绝却成功）`);
    return false;
  } catch {
    console.log(`${label}：OK`);
    return true;
  }
};

expectThrow(
  "外键约束（孤儿 resource_tags）",
  "INSERT INTO resource_tags(resource_id, tag_id) VALUES (99999, 99999)",
);
expectThrow(
  "CHECK 约束（非法 resource_type）",
  "INSERT INTO resources(file_path, file_path_key, resource_type) VALUES ('D:/bad.png','d:/bad.png','bogus')",
);
expectThrow(
  "路径唯一约束（大小写归一后重复）",
  "INSERT INTO resources(file_path, file_path_key) VALUES ('D:/C.PNG','d:/c.png')",
);
expectThrow(
  "逐槽位依赖主键（同 MOD 同 property 重复）",
  "INSERT INTO resource_mod_usages(resource_id, mod_guid, property) " +
    `VALUES (${rid}, 'com.Quokka.sisterveilb', 'outfit6.accessory10.ChaFileAccessory.PartsInfo.id')`,
);

// WAL 不适用于 :memory:，这里只确认 journal_mode 可设置
db.exec("PRAGMA journal_mode = WAL");
console.log(`PRAGMA 可设置：OK`);

if (ftsEnabled) {
  const match = (q) =>
    db
      .prepare(
        "SELECT r.display_name AS n FROM resources_fts f JOIN resources r ON r.id = f.rowid " +
          "WHERE resources_fts MATCH ?",
      )
      .all(q).length;
  // FTS5 trigram 只索引长度 >= 3 的子串；1~2 字查询必须走 LIKE 回退。
  const long = match("白峰一");
  const short = match("一乃");
  const like = db
    .prepare(
      "SELECT count(*) AS c FROM resources WHERE display_name LIKE ? OR name LIKE ?",
    )
    .get("%一乃%", "%一乃%").c;
  console.log(`FTS 中文子串（3 字 "白峰一"）：${long === 1 ? "OK" : "失败"}`);
  console.log(`FTS 中文子串（2 字 "一乃"）：${short === 1 ? "命中" : "不命中（符合预期，需 LIKE 回退）"}`);
  console.log(`LIKE 回退（2 字 "一乃"）：${like === 1 ? "OK" : "失败"}`);
}

// 级联删除放在最后：会删除上面的样本行
db.exec("DELETE FROM resources WHERE file_path_key = 'd:/c.png'");
const leftover = db.prepare("SELECT count(*) AS c FROM resource_mods").get().c;
console.log(`级联删除（resource_mods）：${leftover === 0 ? "OK" : "失败（残留 " + leftover + "）"}`);
const v2Leftover =
  db.prepare("SELECT count(*) AS c FROM resource_plugins").get().c +
  db.prepare("SELECT count(*) AS c FROM resource_mod_usages").get().c +
  db.prepare("SELECT count(*) AS c FROM resource_authors").get().c;
console.log(
  `级联删除（v2 插件/依赖/作者）：${v2Leftover === 0 ? "OK" : "失败（残留 " + v2Leftover + "）"}`,
);

if (missing.length) console.log(`缺少表：${missing.join(", ")}`);
if (extra.length) console.log(`多余表：${extra.join(", ")}`);

process.exit(missing.length || process.exitCode ? 1 : 0);
