// track opendesign-project-thread oracle:项目→会话映射纯逻辑层
// 跑法:node --test tests/test_project_thread.mjs(Node 22+,原生 strip-types)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  loadThreadMap,
  threadFor,
  withThread,
  withoutThread,
  sessionLabels,
  projectPrefix,
  THREADS_STORAGE_KEY,
} from "../web/src/chat/projectThread.ts";

test("loadThreadMap:null/坏 JSON/非对象 → 空表,不炸", () => {
  assert.deepEqual(loadThreadMap(null), {});
  assert.deepEqual(loadThreadMap("not json"), {});
  assert.deepEqual(loadThreadMap('"字符串"'), {});
  assert.deepEqual(loadThreadMap("[1,2]"), {});
});

test("loadThreadMap:合法映射通过;非 string 值被剔除", () => {
  const raw = JSON.stringify({ 甲: "c1", 乙: 42, 丙: null, 丁: "c2" });
  assert.deepEqual(loadThreadMap(raw), { 甲: "c1", 丁: "c2" });
});

test("threadFor:命中给 chatId,未命中 null", () => {
  const m = { 甲: "c1" };
  assert.equal(threadFor(m, "甲"), "c1");
  assert.equal(threadFor(m, "乙"), null);
});

test("withThread/withoutThread:immutable,原表不动", () => {
  const m = { 甲: "c1" };
  const m2 = withThread(m, "乙", "c2");
  assert.deepEqual(m, { 甲: "c1" });
  assert.deepEqual(m2, { 甲: "c1", 乙: "c2" });
  const m3 = withoutThread(m2, "甲");
  assert.deepEqual(m2, { 甲: "c1", 乙: "c2" });
  assert.deepEqual(m3, { 乙: "c2" });
  // 幂等:删不存在的 key 返回等值表
  assert.deepEqual(withoutThread(m3, "不存在"), { 乙: "c2" });
});

test("withThread:同 key 覆盖(重开新对话后指向新会话)", () => {
  assert.deepEqual(withThread({ 甲: "c1" }, "甲", "c9"), { 甲: "c9" });
});

test("sessionLabels:sessionKey(websocket:<chatId>)反查项目显示名", () => {
  const m = { "翡翠湾-1801": "c1", "2026:云山": "c2" };
  const projects = [
    { key: "翡翠湾-1801", name: "翡翠湾-1801" },
    { key: "2026:云山", name: "云山" },
  ];
  const labels = sessionLabels(m, projects);
  assert.equal(labels["websocket:c1"], "翡翠湾-1801");
  assert.equal(labels["websocket:c2"], "云山"); // 显示名优先于 key
  assert.equal(labels["websocket:别的"], undefined);
});

test("sessionLabels:映射项目已不在列表(被删/改名)→ 回落 key 本身", () => {
  const labels = sessionLabels({ 老项目: "c1" }, []);
  assert.equal(labels["websocket:c1"], "老项目");
});

test("projectPrefix:与 AGENTS.md 规则同源的固定格式", () => {
  assert.equal(projectPrefix("翡翠湾-1801"), "【当前项目:翡翠湾-1801】");
});

test("THREADS_STORAGE_KEY:稳定命名(改名=用户丢映射,锁死)", () => {
  assert.equal(THREADS_STORAGE_KEY, "odw.projectThreads");
});
