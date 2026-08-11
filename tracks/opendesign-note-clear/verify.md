# Verify: opendesign-note-clear

- Date: 2026-08-11
- Verdict: PASS

> Panel hook —— 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(`web` 重 build 后 `git status -- web/dist` 为空 = 入库的 dist 与源码同步)
- [x] tests pass(node 348 / python 1001 跑过 0 跳过 / MCP 契约闸三条 / e2e 34 PASS 0 FAIL)
- [x] no secrets / unsafe ops(本单只改 3 个实现文件,无新依赖、无新端口、无新落盘文件)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,收据行逐字节粘在下面。
**跑过的每一遍都在这儿,红的、断的一遍都不藏**(规矩 5b):

**第①遍 —— 红的**。判据先行的 commit 上跑(工作树里已有实现,还没 commit)。
四段绿、`dist 新鲜度` 红:改了 `web/src/` 却还没 `npm run build` 入库 ——
ds_web 服务的是 `web/dist`,这条红的含义是"真机上还是旧行为":
```
runlog: full-suite rc=1 commit=afcc452 dirty=yes at=2026-08-11T03:12:48Z file=tracks/opendesign-note-clear/evidence/20260811T031248Z-01-full-suite.txt
```

**第②遍 —— 补 dist + 本单 e2e 专跑**,绿:
```
runlog: dist-and-e2e rc=0 commit=1d4e0b4 dirty=yes at=2026-08-11T03:21:12Z file=tracks/opendesign-note-clear/evidence/20260811T032112Z-01-dist-and-e2e.txt
```

**第③遍 —— 红检**(`redcheck`:实现三个文件退回 base `d22f8a2`,判卷留在 HEAD)。
判据在旧实现下确实红,且**红在目标断言上**(`--must-fail 业主还在犹豫|业主微信确认了|note`),
跑完自动恢复、工作树干净由 git 说了算:
```
runlog: redcheck rc=0 commit=f7541e3 dirty=yes at=2026-08-11T04:01:02Z file=tracks/opendesign-note-clear/evidence/20260811T040102Z-01-redcheck.txt
```

**第④遍 —— 残件,不作数**。跑到一半会话断线,进程被杀,收据只写到 python 那段的段头、
**没有末尾收据行**。按规矩 5b 原样留在 evidence 里(`20260811T040151Z-01-full-suite-final.txt`),
**它不能被当成任何结论的依据** —— 断线重连后重跑,就是下面两遍。

**第⑤遍 —— 重跑,五段全 PASS**(工作树带未入库的收据文件,`dirty=yes`):
```
runlog: full-suite-final2 rc=3 commit=f7541e3 dirty=yes at=2026-08-11T04:31:23Z file=tracks/opendesign-note-clear/evidence/20260811T043123Z-01-full-suite-final2.txt
```

**第⑥遍(权威的一遍:收据入库之后跑,工作树干净)** —— 五段全 PASS:
```
runlog: full-suite-clean rc=3 commit=ed6e60f dirty=no at=2026-08-11T04:42:39Z file=tracks/opendesign-note-clear/evidence/20260811T044239Z-01-full-suite-clean.txt
```
> `rc=3` **不是判据红了**。五段全 `PASS`;`3` 来自总跑自己的口径:
> 「没有红的,但有 2 条没跑 —— 不算通过」。那 2 条(`new_chat` / `project-thread`)
> 要起活的 nanobot gateway,`tests/run-all.sh` 默认不跑,**与本单改动无关**
> (本单一行代码都没碰对话面)。**照抄不四舍五入。**

汇总数字(以第⑥遍为准,供人眼核对,**权威仍是收据文件本身**):
node **348** 通过 / 0 跳过 · python **1001 跑过 / 0 跳过**(死断言闸:0 条从未执行)·
MCP 契约闸三条全绿 · dist 与源码同步 · e2e **34 PASS / 0 FAIL / 2 SKIP**。

oracle-first commit:`afcc452`(判据先行,`--stat` 只有 tests/,零实现文件);
四审之后补的判据同样先行单独入库:`8399017`(⑤i/⑤j/⑤k),修复在 `f7541e3`
—— **判据都在修复之前,git 里查得到**。

## Review

- lane: full —— 这不是纯前端小修:核心写口 `edit_change` 的语义扩张了(`note=""`
  从"没给"变成"从业主档案里删掉一行"),写口第一次获得**删除既有内容**的能力。
  按硬规矩「数据一致性面 → full,针孔再薄也不打折」,不在这里降档。
- 派给: `submimo fix`(微档)—— **实际执行:一轮绿,返工 0 轮**
  (日志 `/root/aiwork/logs/note-clear-fix.log` 末行 `submimo fix: oracle GREEN on attempt 1`)。
  形状确实是微档:3 个文件、每处 1–5 行、方向在 design 里定死;判卷文件全 `--protect`,
  它的循环里只有 pytest + `node --test`(零端口),要起 ds_web + chromium 的 e2e
  由主 agent 在闸② 亲跑(第②遍收据)。
  > 四审之后的 LOW-1 修复(`f7541e3`)是**主 agent 亲改**:那处要判断"什么算真改动"
  > 与页脚 bump 的耦合,不是填空题。
- 规格自查(读任何 panel 输出之前先答):

  这一单的核心赌注是:**把 `note=""` 复用成"删除",而不是新加一个 `clear_note` 参数。**
  如果这条赌错了,最可能错成这样 —— 某个调用方把"我这次不改备注"表达成空串,
  于是**一次无关的编辑顺手删掉了业主的备注**,而且不留痕、找不回来。

  我怎么发现:去数**谁能调到这个写口**。查完了 —— `edit_change` 只在
  `bin/ds_web.py:1572`(工作台的 PUT 针孔)有一个调用方;`bin/ds_tools_server.py`
  的 MCP 工具表里**没有它**,即**助手根本调不到**(它只有 `set_change_status` /
  `set_due_date` / `delete_change` 那几个)。所以"助手手滑传空串删掉业主备注"
  这条我最担心的形状不存在,写口只对人手点的 UI 开放;而 UI 两侧的预填都 == 原值,
  用户不动手就不发请求(`buildEditRequest` 相等即 `null`)。
  **这也是"删除不留痕"能被接受的前提**:动手的是业主本人,删的是他自己刚打的字。

  第二条赌注:**归一(同一 cnum 的重复备注行只留一条)是对的修法**,而不是让读侧
  改成"第一条获胜"。理由:写侧只认第一条、读侧最后一条获胜,这个缝本身就是业主
  报的"改了还是旧的";把两侧对齐到"盘上只可能有一条",缝就不存在了,而不是换个
  方向再留一条缝。这条赌注 panel 两条腿都独立复核过定位正则的边界(C1 不误伤 C12)。

- 腿的花名册:
```
submimo=PASS subdeepseek=PASS subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=FAIL(rc=1)
```
  > `PASS` 只是进程 rc=0。**实际给出裁决的是 2 条腿**(submimo / subdeepseek,均判 PASS);
  > subglm 是智谱**欠费**(`{"error":{"code":"1113","message":"余额不足或无可用资源包"}}`),
  > subkimi 是**额度**挂掉 —— 与 08-11 上一单同因,**不许读成"四审过了"**。

- findings:
  - **F1(subdeepseek,LOW → 已修 `f7541e3`)**:`note` 非空分支**无条件** `changed = True`
    ⇒ 写一条和现在逐字节相同的备注也会重写文件 + bump「最后更新」。而页脚是项目活跃度/
    超期排序的输入,假 bump 会污染排序;也与同函数"改成同样的正文不留痕"的 no-op 口径
    自相矛盾。修法:`_upsert_note` 改成返回"是否真的动了内容",归一掉重复行仍算真改动。
    判据 ⑤i(红过)+ ⑤j/⑤k(锚)先行入库。
  - **F2(submimo,非阻塞建议 → 已补)**:`_upsert_note` 的插入路径(段在、但该 cnum
    没有备注行、且段里没有留痕行 ⇒ `last=hidx`)没有用例。已补 ⑤k(`8399017`),
    并顺带断言"删到最后不许把 `## 变更历史` 段本身删掉"。
  - **F3(subdeepseek,LOW → 不修,记账)**:手写的**前导零**备注行(`- C03 备注:x`)
    读侧 `int("03")` 认成 cnum 3、写侧 `^- C3 备注` 匹配不到 ⇒ 归一/清空都漏得掉,
    症状与本单要修的 bug 同型。判定不修的理由见 Accepted deviations。
  - **F4(subdeepseek,process → 已补)**:evidence 里当时只有全绿收据,"判据先行"的
    红跑没留机器证据。已补第③遍 `redcheck` 收据(机器打印,不是我的转述)。
  - **F5(subdeepseek,残余风险 → 已在 backlog + 验收清单)**:三层判据全绿、**业主眼里
    仍可能错**的唯一现实形状 —— 待办页的备注来自会话级 `noted` 映射,`/api/todos`
    载荷里没有 `note`;**他这次开的是新会话/刷新过页面**,待办页编辑框预填空串,
    不输入直接保存 ⇒ 请求里没有 `note` 字段 ⇒ 盘上旧备注原样存活。
    这不是本 diff 的回归,是既有形状,已进 `docs/backlog.md`(要单独一单),
    并已如实写进 `docs/accept-0.81.0.md` H 组,免得业主把它当新 bug 报回来。
  - **M1(我这一遍的孤发现,两条腿都没提)**:`edit_change` **不在 MCP 工具表里**
    —— 这是"删除不留痕可接受"和"空串复用成删除"两条判断的**共同承重点**,
    而 design.md 只写了"web 层 `body.get()` 分得开",没写"助手压根调不到"。
    已补进上面的规格自查;**这条一旦哪天不成立(有人把 edit_change 开成 MCP 工具),
    本单的取舍就要重议** —— 写在这里当墓碑。
  - **M2(过程,记给我自己)**:本单第一遍独立审是在**断线前那个会话**做的,
    **没有留下工件**。断线后我重读了三个实现文件的完整 diff(闸③)才写这一页,
    M1 就是这一遍读出来的。但"panel 之前我确实独立审过"这件事,**这一单查不到工件**
    —— 记账,不粉饰。

- arbitrated verdict (主裁): **PASS**。

  两条给了裁决的腿都判 PASS,我逐条对代码验过,不是采信自述:F1 我改了并补了红过的判据;
  F2 已补用例;F4 已补收据;F3 记账不修(理由在下);F5 是既有形状、已进 backlog 与验收清单。
  机械面第⑥遍权威收据五段全 PASS(唯一的 `rc=3` 已说明来源)。
  **全票不降标准**:两条腿都没看出 M1 这条承重点,而它比它们提的任何一条 LOW 都更承重
  —— 这次孤发现在我这边,不在腿上。

  **仍然只有真机能答的那一格**:业主原话是"修改删掉原来的备注但还是之前的备注",
  他到底点的是哪个框、走的哪条路(工作区 / 待办页 / 参考图备注),判据接不住 ——
  交付时请他**按原动作复验一次**(`docs/accept-0.81.0.md` H 组)。

## Accepted deviations

- **前导零备注行不修(F3)**。`- C03 备注:x` 只可能来自**手改档案**(工具从不写前导零),
  且真要修就得动读/写两侧那对正则 —— 而"把读写两侧对齐"正是本单刚做完的事,
  再动它值一次独立的红检,不该当收尾时的搭车改动。已记进 `docs/backlog.md`。
- **`note: null` 不单独判 400**(与"没给"合并)。双出方案提过;没有任何调用方发 null,
  为它扩写口类型闸换不来安全收益。
- **命名与 design 有出入**:design/tasks 里写的是 `_remove_note`,实现叫 `_delete_note`
  —— 纯命名漂移,判据咬的是行为,不返工。
