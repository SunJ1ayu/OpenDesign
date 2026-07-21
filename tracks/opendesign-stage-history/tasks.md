# Tasks: opendesign-stage-history

- base-ref: 5b7f40a3bc68bdc4b364ebf359b03d054b31a552
- 执行腿:sub Claude worktree(AGENTS.md Tiered execution);oracle 主 agent 亲写并先 commit

## T0 — oracle 先行(主 agent) DONE

- [x] `tests/test_ds_refs_update.py`(新核心 `update_ref`)
- [x] `tests/test_ds_web_stage.py`(针孔 ⑩ + `/api/projects` 的 `stages` 词表)
- [x] `tests/test_ds_web_refs_update.py`(针孔 ⑪ + `/api/refs` 的 `vocab` 词表)
- [x] `tests/test_change_history.mjs`(`history.ts` 纯函数 + `gallery.ts` 透传)
- [x] `tests/e2e/stage_history.e2e.mjs`(#7/#8/#9 的 UI 事实)
- [x] red-check:全部因「未实现」而红,且夹具健康度单独验证过

## T1 — #8 核心 `ds_refs.update_ref`(先做,写工具是地基) DONE

- [x] `bin/ds_refs.py`:`update_ref(ref_id, style=None, space=None, note=None, …)`
      —— 分段重组只动头段与 `备注:` 段,其余段逐字节不变;词表校验不自动建词;
      三字段全 None → `no_fields`;`locked_rw` + `bump_last_updated`
- [x] 同文件注册 MCP `update_ref_tool`(docstring 写清「什么时候用」,同既有工具口径)
- [x] `skills/` 文档同步(照 add_ref / link_ref 的既有写法)
- [x] oracle:`python3 tests/test_ds_refs_update.py` 全绿

## T2 — 两个新写针孔 + 两处词表下发(安全面) DONE

- [x] `bin/ds_web.py`:`POST /api/projects/stage`(键白名单 `{project, stage}`)
- [x] `bin/ds_web.py`:`POST /api/refs/update`(键白名单 `{ref_id, style, space, note}`)
- [x] `GET /api/projects` 加顶层 `stages`;`GET /api/refs/<key>` 加 `vocab`
- [x] 两条路径都**精确匹配**(非前缀)、都继承 Host 闸、GET 该路径仍 405
- [x] oracle:`test_ds_web_stage.py` + `test_ds_web_refs_update.py` 全绿

## T3 — 前端三块 DONE

- [x] `web/src/api.ts`:`Change` 补 `history` / `note`;projects 响应补 `stages`;
      refs 响应补 `vocab`;新增 `setStage()` / `updateRef()` 两个调用
- [x] `web/src/workspace/history.ts`(新,纯函数):历史计数文案 / 日期 / 空态
- [x] `web/src/gallery.ts`:`GalleryItem` 加 `refId?` / `note?`(纯透传)
- [x] `#7` `ChangesColumn.tsx`:stage-chip → 下拉(esc / 外点关闭,保存中禁用,
      失败行内报错,成功后 bump 数据,**不做乐观改写**)
- [x] `#8` `GalleryPage.tsx`:lightbox 里 refs 图给标签/备注编辑区(词表 chip 多选 +
      备注输入 + 保存/取消);ws 图不给入口;**保存后重拉 refs**
- [x] `#9` `ChangesColumn.tsx`:变更行渲染 `note` + 「改过 N 次」展开列
      `<日期> 原:<原文>`
- [x] `bin/ds_web.py` VERSION → `0.33.0`;`npm run build` 重建 dist
- [x] oracle:`node --test tests/test_change_history.mjs` + e2e 全绿

## DOM 契约(e2e oracle 按这些钩子断言,名字必须逐字一致)

| 钩子 | 位置 | 说明 |
|---|---|---|
| `[data-ui="stage-chip"]` | ChangesColumn 标题旁 | 已存在,但**必须变成 `<button>`** |
| `[data-ui="stage-menu"]` | 阶段下拉容器 | 关闭时**从 DOM 移除**(e2e 等 detached) |
| `[data-ui="stage-option"]` | 下拉里每个阶段 | 顺序 = 后端下发顺序,共 11 项 |
| `[data-ui="history-toggle"]` | 变更行内 | 文案「改过 N 次」;无历史时**不渲染** |
| `[data-ui="history-entry"]` | 展开后的每条留痕 | 文案 = `formatHistoryEntry`;收起时移除 |
| `[data-ui="ref-edit"]` | 图墙 lightbox 内 | **只在 refs 来源的图上出现**(ws 图零渲染) |
| `[data-ui="ref-style-option"]` | 编辑区风格选项 | 来自后端 `vocab.style` |
| `[data-ui="ref-note-input"]` | 编辑区备注输入 | 打开时回填当前备注 |
| `[data-ui="ref-save"]` | 编辑区保存 | 保存成功后重拉 refs |

变更行备注(`note`)也要显示出来 —— e2e 断言行内能读到备注文本。

## T4 — 收货(主 agent 亲做,执行腿自述一概不作数) DONE

- [x] 闸①:五份 oracle 对 T0 commit **逐字节 diff 为空**
- [x] 闸②:主 agent 亲跑 oracle + 全量回归(全 py / 全 mjs / build)+ 相邻 e2e +
      `/api/health` 回显 0.33.0
- [x] 闸③:主 agent 亲读 diff(两个新写口逐行)
- [x] verify:**full 四审**(两个新写口,不打折)→ 仲裁 → 修 → merge → 归档

## 执行腿铁律(派活 prompt 必带)

1. 五份 oracle(`tests/test_ds_refs_update.py`、`tests/test_ds_web_stage.py`、
   `tests/test_ds_web_refs_update.py`、`tests/test_change_history.mjs`、
   `tests/e2e/stage_history.e2e.mjs`)**逐字节 off-limits**,一个字符都不许动。
2. 自检清单:五份 oracle + 全量回归 + build 全绿才交。
3. 不 push、不 merge、不归档、不装依赖。
4. **PKB 写操作必须过核心**(ds_tools / ds_refs):针孔是薄壳,不许在 ds_web 里
   自己写名字闸 / 词表校验 / 文件重写。
5. 词表**不许在前端硬编码副本** —— 一律用后端下发的 `stages` / `vocab`。

## 收口记录(2026-07-21)

- 执行腿(Sonnet 5 worktree)三 commit `3d70b6d`/`34e2032`/`8a93a92`;闸① byte-diff 干净。
- 执行腿抓到主 agent oracle 的 2 个真 bug(截断后读取 / 断言算术上不可能),已修且收紧。
- 收货修复轮 `5d66cb1`:主审闸③抓到 M1(核心误改没点名的头段)+ M2(老标签把条目锁死),
  外加 L1/L2/L3/N1 四条小项;oracle 各补 2 / 3 例,先红后绿实测。
- verify:full 四审只到 1.5 腿(subdeepseek max-turns / subglm 无 CodingPlan),
  已如实记为缺口;主裁 **PASS**(见 verify.md)。
- ds-web **0.33.0**,`/api/health` 已回显。
