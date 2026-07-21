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
- [x] `web/node_modules` 符号链接**误入过一次 commit,已 `git rm --cached` + amend 剔除**
      (`git ls-files | grep node_modules` 为空)

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
  - **subglm**:火山 **CodingPlan 未订阅** → agent 腿 400 直接死(与记忆一致);
    chat 腿补发中/未回
  - ⇒ 实际有效 = 1 完卷 + 1 半卷。**这不是四审,记为本单的执行缺口**(不掩饰)。
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

**subkimi 的「`_load_styles` 惰性建 vocab 文件」** → **收为已知取舍**:`add_ref` 早有同样
行为(词表文件缺失时按默认词表创建),拒绝路径不写**索引**这条不变量没破;oracle 的
「零落盘」断言口径是索引文件,这一点在本 verify 里显式记下。

### arbitrated verdict(主裁)

**PASS**,但附一条执行缺口:**本单没能真正凑齐四审**(两腿基础设施失败)。我不拿
「submimo PASS」当通行证 —— 本单两条真问题都是我自己闸③读出来的,与 07-21 上一单
(subkimi 单腿 BLOCK 成立)恰好互为镜像:**评审腿的价值是补盲点,不是发通行证;
主审自己的逐行读永远不能省**。

安全面我独立认可:两个针孔 posture 逐条对齐 `_edit_change`(CT json / 尺寸闸 / dict /
**键白名单**挡掉 `ds_root`·`today`·`file`·`source`·`used` / 类型闸 / 路径精确匹配 /
Host 闸继承 / GET 无内容面),薄壳没破(ds_web 零文件写),注入面由构造消灭(阶段只能
是词表字面量;备注禁 `|` 与换行;标签必须是词表字面量),锁与拒绝路径零落盘。

## Accepted deviations

- **四审只到 1.5 腿**(subdeepseek max-turns / subglm 无 CodingPlan 订阅 → chat 腿补发)。
  记为缺口,不假装齐。GLM 的 CodingPlan 是账号侧问题,已在记忆里;DeepSeek agent 腿
  的 max-turns 需要调参,记入工具债。
- **e2e 的风格断言仍是 `||` 弱断言**(见上,记债下一轮收紧)。
- **`_load_styles` 在拒绝路径可能惰性创建 `refs-vocab.md`**:既有 `add_ref` 同行为,
  「拒绝路径零落盘」的口径限定在**索引文件**。
- 参考图**删除**、`来源/文件/用于` 三段的编辑仍不做(proposal 的 non-goals)。
- `project-thread` e2e 未跑(需真 gateway;本单零聊天链路改动)。
