# Verify: opendesign-stage-history

- Date: 2026-07-21
- Verdict: **PASS**(主裁:主 agent)

## Mechanical checks

全部主 agent 亲跑(执行腿自述一概不作数):

- [x] build passes（`npm run build` 绿）
- [x] tests pass
  - 五份 oracle:`test_ds_refs_update` 27/27(修复轮 +2)、`test_ds_web_stage` 18/18、
    `test_ds_web_refs_update` 21/21、`test_change_history` 17 pass(修复轮 +3)、
    `e2e/stage_history` ALL PASS
  - 回归:22 个 py 套件 rc=0(`test_ws_protocol_smoke` rc=3 = 无 gateway 的既有
    SKIP→rc=3 设计,存量);11 个 mjs fail 0
  - 相邻 e2e:`frontend_p1` / `frontend_p2_polish` / `frontend_p3_polish` / `cockpit` /
    `intake` 全 PASS(`project-thread` 需真 gateway,本单未动聊天链路,略)
- [x] no secrets / unsafe ops;dist 已重建;`/api/health` → 0.33.0
- [x] **`web/node_modules` 事故(自捅,已修复+已加护栏)**:执行腿为跑 tsc 在 worktree
      里建了指向主仓的符号链接,`.gitignore` 的 `/web/node_modules/`(**带尾斜杠只匹配
      目录**)漏掉它 → 被提交 → merge 时 git 用这条链接**覆盖掉主仓真实的 node_modules
      目录**,链接变成自指(`Too many levels of symbolic links`)。
      修:`git rm --cached` 剔除 + `npm install` 重装(168 包)+ **重跑 build 复现出与
      仓内**逐字节相同的 dist 哈希**(证明恢复完整)+ `.gitignore` 去掉尾斜杠并**实测**
      同名符号链接不再出现在 `git status`。

## 收货三硬闸

- **闸① oracle byte-diff**:执行腿三个 commit(`3d70b6d`/`34e2032`/`8a93a92`)对 T0
  oracle commit `f098b69` **零 tests/ 改动**,干净。之后的 oracle 变更全部由主 agent
  在收货轮所写,且都是**收紧**(见下)。
- **闸② 亲跑**:见上。
- **闸③ 亲读 diff**:逐行读完,两个新写口逐行核。**本单的真发现全部出自这一闸**。

## Review

- lane:**full 四审**(两个新写口 = 安全面,不打折)
- 出卷情况(`/root/aiwork/logs/panel-stagehist-20260721*`):
  - **submimo**:完卷,**PASS** + 11 条建议
  - **subkimi**:900s 超时,结构化结论没落地,但 66KB 推理日志可读 —— 无 blocker,
    独立提到「缺 `阶段` 行的项目 UI 藏了入口」(= 我的 L3)与「`_load_styles` 惰性建
    vocab 文件 = 拒绝路径的磁盘副作用」(新,见下)
  - **subdeepseek**:agent 腿撞 `max turns (40)`,无产出
  - **subglm**:agent 腿因火山 **CodingPlan 未订阅** 400 直接死(与记忆一致)→
    **chat 腿补发成功,完卷 PASS + 5 findings**
  - **subdeepseek**:agent 腿撞 max turns → **chat 腿补发成功,完卷 PASS + 6 findings**
  - ⇒ 最终 = **3 完卷(submimo / subglm-chat / subdeepseek-chat)+ 1 半卷(subkimi 超时)**。
    两条 agent 腿的失败已用 chat 腿顶上,四审实质到齐(基础设施缺口另记工具债)。
- oracle 先跑(`PANEL_ORACLE_CMD`):`test_ds_refs_update` rc=0,记录在
  `panel-stagehist-20260721.oracle.log`。

### findings

主审自己抓到、**四腿全没提**的两条真问题(修复轮 `5d66cb1`):

- **M1(真,已修)** `ds_refs.update_ref` **无条件重建头段** `- [rN] 风格|空间`:
  手写老条目的头段若少了 `|`,一次**只改备注**的调用会把它重建成 `- [r1] |`,
  **静默抹掉标签**;良构行里人手写的 `奶油风, 客厅`(逗号后空格)也会被顺手归一化。
  与本函数唯一的存在理由(「未点名的段一个字节都不许动」)直接矛盾。
  修:头段只在点名了 style/space 时才重建;头段缺 `|` 并入 `malformed_entry`。
  oracle 补 2 例并**先红后绿实测**(撤掉修复即红)。
- **M2(真,已修)** 前端保存恒发 style+space+note:老索引里若有**不在词表里**的手写
  标签(词表可扩也可删),预填后原样回发 → 核心判 `style_unknown` → 用户**连备注都
  改不了**,而提示是「刷新页面重试」—— 刷新根本没用,死循环。
  修:新增纯函数 `gallery.sameTags`(顺序无关集合比较),**只发真改过的字段**;
  一个字段都没改就不发请求。oracle 补 3 例。

同轮收的小项:L1 针孔⑪ 成功回显原样返回核心的整行(含读口**刻意不外泄**的
`来源:`/`用于:`)→ 改为只回 `{ok, ref_id}`;L2 保存成功零反馈 → 加「已保存」/
「没有改动」轻提示;L3(subkimi 独立提到)缺 `- 阶段:` 行的项目不渲染 chip → 恒渲染,
无阶段显「未设阶段」;N1 lightbox「取消」实为关闭 → 文案改「关闭」。

**执行腿抓到我 oracle 的两个真 bug(均成立,已修且收紧)**:
`test_r1_anchor_does_not_hit_r12` 在 `open(...,"w")` 截断之后才读取目标行(TypeError);
`test_parse_roundtrip_after_update` 断言「命中 1 条」在夹具里**算术上不可能**(r2 天生
同标签)—— 改用夹具没人用过的风格,并补一条反向断言。

**submimo 的建议逐条裁定**:

- 「stage-menu-backdrop 只覆盖 stage-cell,外点不关菜单」→ **拒,已实测证伪**:
  backdrop 是 `position:fixed; inset:0`,实测 boundingBox = 1600×900(整视口),
  在离 chip 最远的角落点击后菜单 count=0(确实关了)。
- 「e2e 风格断言用 `||` 允许两种结果 = 弱断言」→ **部分收**:`||` 是我为「UI 到底是
  多选 toggle 还是单选覆盖」留的口子;执行腿选了 toggle(合「词表 chip 多选」)。
  语义既已定,**这条弱断言应收紧**,记入下一轮 oracle 债(本轮不动 e2e,避免在
  评审结论未齐时改判据)。
- 「缺并发压测」→ 拒(本轮):`locked_rw` 是既有件、既有 `test_ds_lock` 与 07-13 的
  ds_organize 并发压测覆盖过;新函数没引入第二把锁。
- 「`cnDate` 不校验语义非法日期(2026-13-01 → 13月1日)」→ 拒:`cnDate` 是既有件,
  日期来自本仓自己写的留痕,不是用户输入面;要改也该单独一单。
- 「`srv.kill()` 未等进程退出可能 EADDRINUSE」→ 记债(全仓 e2e 的既有写法,不在本单修)。
- 「bump 断言用子串、缺 style 多值部分未知/全角逗号/空白 note/stage 前后空白/
  delivered flag 等用例」→ 记债,择机补(都不改变本单结论)。

**subglm(chat 腿)findings 裁定**:

- 「头段缺 `|` 时只改备注会重建成 `- [rN] |` 静默抹掉风格」→ **真,与我闸③的 M1 同一条**
  (它评的是修复前的 diff)。**它还补了我漏的子情形:头段多一个 `|`
  (`奶油风|客厅|多余`)时按前两段重建会静默丢尾巴** → 已收:`malformed_entry` 改判
  「`tag_part` 必须**恰好**一个 `|`」,oracle 补 1 例。
- 「`ChangeHistoryEntry.date` 标成 `string` 但运行时按 null 处理」→ 收,改 `string | null`。
- 「`updateRef` 成功但 `reloadRefs()` 失败会被同一个 catch 报成『保存失败』」→ **真,已修**:
  两者拆开,写成功先落「已保存」,重拉失败只提示「列表没刷新上」。
- 「四份 oracle 不在 diff 里所以无法评」→ 非 finding,是 chat 腿的可见性限制(它们在
  基线 commit `f098b69` 里,`PANEL_DIFF_BASE` 只喂增量)。记工具债:chat 腿应把
  oracle 一并 INCLUDE。
- 「`historySummary(c)` 一次渲染调两遍」→ 拒:纯函数、每行一次、列表规模是几十条量级。

**subdeepseek(chat 腿)findings 裁定**:

- 「`style`/`space` 没有 `|` 防护,而 note 有」→ **收(纵深防御)**。词表本身经
  `add_style` 已禁 `|`,但 `refs-vocab.md` 是**人可手改的纯文本**,手写一条 `- 奶油|风`
  就能借词表校验把分隔符送进头段。已加:最终标签含 `|` 一律拒;oracle 补 1 例(实测
  手写词条确实能进词表,拒后索引逐字节不变)。
- 「`style_unknown` 的提示『刷新页面重试』是死循环」→ **收**,改成「换一个,或先让助手
  把它加进风格词表」。
- 「`pickStage` 把裸错误码怼给用户」→ 收,加 `stageErrMsg` 映射(同 `createProjectErrMsg`
  先例)。
- 「`.ts` 扩展名导入不标准」→ 拒:全仓既有约定(tsconfig `allowImportingTsExtensions`
  + `node --test` 原生 strip-types 两头兼容),注释已写明理由。

**subkimi 的「`_load_styles` 惰性建 vocab 文件」**(subdeepseek 独立复述同一条)
→ **收为已知取舍**:`add_ref` 早有同样
行为(词表文件缺失时按默认词表创建),拒绝路径不写**索引**这条不变量没破;oracle 的
「零落盘」断言口径是索引文件,这一点在本 verify 里显式记下。

### arbitrated verdict(主裁)

**PASS**。三腿完卷全 PASS + 一腿半卷无 blocker,但**通行证不是它们发的**:本单两条
必修(M1/M2)都是我自己闸③逐行读出来的;评审腿的贡献是**在我的修复之外又补了三条我
漏掉的真东西** —— subglm 的「头段多一个 `|` 也会静默丢数据」(M1 的子情形)、
subdeepseek 的「标签侧缺 `|` 防护而 vocab 文件人可手改」(纵深防御真缺口)、
以及两条错误文案确实会把人引到死路。这正是 panel 的正确用法:补盲点,不发通行证。

安全面我独立认可(修复轮之后)

安全面我独立认可:两个针孔 posture 逐条对齐 `_edit_change`(CT json / 尺寸闸 / dict /
**键白名单**挡掉 `ds_root`·`today`·`file`·`source`·`used` / 类型闸 / 路径精确匹配 /
Host 闸继承 / GET 无内容面),薄壳没破(ds_web 零文件写),注入面由构造消灭(阶段只能
是词表字面量;备注禁 `|` 与换行;标签必须是词表字面量),锁与拒绝路径零落盘。

## Accepted deviations

- **两条 agent 腿失败,由 chat 腿顶上**(subdeepseek 撞 max turns 40;subglm 火山
  CodingPlan 未订阅)。结论有效,但**工具债三条**:①DeepSeek agent 腿的 max-turns 要调;
  ②GLM 的 CodingPlan 是账号侧问题(与记忆一致);③**chat 腿只喂增量 diff,看不到基线里的
  oracle 文件** —— 两家都因此说「测试文件不在 diff 里无法评」,应让 chat 腿把 oracle
  一并 INCLUDE。
- **e2e 的风格断言仍是 `||` 弱断言**(见上,记债下一轮收紧)。
- **`_load_styles` 在拒绝路径可能惰性创建 `refs-vocab.md`**:既有 `add_ref` 同行为,
  「拒绝路径零落盘」的口径限定在**索引文件**。
- 参考图**删除**、`来源/文件/用于` 三段的编辑仍不做(proposal 的 non-goals)。
- `project-thread` e2e 未跑(需真 gateway;本单零聊天链路改动)。
