# 探针:e2e 夹具自造(继承的账 B) —— 2026-09-08

场景 = **模拟换台机器新克隆**:全新空 DS_ROOT,ds_web 起在 8769。

## 造夹具前
```
$ curl -s http://127.0.0.1:8769/api/projects
{"projects": [], "stages": [...], "excludedStructural": []}
```

## 跑 e2e(它第一件事就是 ensureFixtures)
```
step1 home 登录已连接
TimeoutError: locator.click: Timeout 30000ms exceeded.
  - waiting for locator('.proj-row').filter({ hasText: '翡翠湾-1801' }).first()
    - locator resolved to <button class="proj-row" title="翡翠湾-1801 · 阶段:洽谈">…</button>
    - <div class="connect-modal-mask">…</div> intercepts pointer events
```

## 造夹具后
```
['星河名邸-2302', '翡翠湾-1801']
```

## 判读

- ✅ **夹具确实被自己造出来了**(空目录 → 两个项目都在)。
- ✅ **失败点变了**:以前是"干等 `.proj-row` 出现"(报错里一个字不提夹具);
  现在那一行 **resolved 到了**,卡在 `connect-modal-mask` 挡住点击 ——
  那是**没有活 gateway** 该有的样子,不是夹具问题。
- ⚠️ **这一趟没有验完整条 e2e**:它要活 gateway(8765),本机这轮没起。
  验到的只有 ensureFixtures 那一段。**不假装验过了后面。**
