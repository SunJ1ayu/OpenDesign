# Verify: opendesign-minimize-animation

- Date: 2026-08-23

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

## Mechanical checks

- [x] build passes(前端未改;python 全量 1291 条)
- [x] tests pass
- [x] no secrets / unsafe ops(本单只加 ctypes 声明与样式位,无新写口/无网络/无凭证)

**机器打印的**(不是我的转述):

```
runlog: python-regression-venv-final rc=0 commit=656e606 dirty=yes final=yes at=2026-08-23T04:09:46Z file=tracks/opendesign-minimize-animation/evidence/20260823T040946Z-01-python-regression-venv-final.txt
runlog: mcp-gate rc=0 commit=656e606 dirty=yes final=yes at=2026-08-23T04:04:24Z file=tracks/opendesign-minimize-animation/evidence/20260823T040424Z-01-mcp-gate.txt
runlog: redcheck-mutation rc=0 commit=656e606 dirty=yes final=yes at=2026-08-23T04:19:17Z file=tracks/opendesign-minimize-animation/evidence/20260823T041917Z-01-redcheck-mutation.txt
```

三份最终收据都在 `656e606`(= 最后一次编辑之后),`source-stable: yes`。
python 全量 `Ran 1291 tests ... OK (skipped=3)` —— 1289 + 2 条新 restype 断言,
数对得上,证明新断言真被跑起来了,不是整块 SKIP。
红检 `咬住 20 条 / 漏网 0 条`,三个被变异文件哈希原样还回。

### 跑红过的那几遍(5b:一份都不许藏)

```
runlog: python-regression rc=1 commit=057439d dirty=yes at=2026-08-23T03:39:36Z file=tracks/opendesign-minimize-animation/evidence/20260823T033936Z-01-python-regression.txt
runlog: python-regression-pytest rc=1 commit=057439d dirty=yes at=2026-08-23T03:40:00Z file=tracks/opendesign-minimize-animation/evidence/20260823T034000Z-01-python-regression-pytest.txt
runlog: python-regression-final rc=1 commit=70a320b dirty=yes final=yes at=2026-08-23T03:47:51Z file=tracks/opendesign-minimize-animation/evidence/20260823T034751Z-01-python-regression-final.txt
runlog: python-regression-venv rc=0 commit=70a320b dirty=yes final=yes at=2026-08-23T03:54:58Z file=tracks/opendesign-minimize-animation/evidence/20260823T035458Z-01-python-regression-venv.txt
runlog: python-regression-venv-final rc=143 commit=656e606 dirty=yes final=yes at=2026-08-23T04:04:17Z file=tracks/opendesign-minimize-animation/evidence/20260823T040417Z-01-python-regression-venv-final.txt
runlog: redcheck-mutation rc=0 commit=70a320b dirty=yes final=yes at=2026-08-23T04:03:42Z file=tracks/opendesign-minimize-animation/evidence/20260823T040342Z-01-redcheck-mutation.txt
```

逐份认账(**不许总结掉红的**):

- `rc=1 @057439d` ×2 —— **判据先行,它们就该是红的**。实现那时还没写。
- `rc=1 @70a320b`(22 failed)—— **不是本单的 bug,是解释器选错**:跑的是系统
  `python3 -m pytest`,日志里 13 处 `ModuleNotFoundError`(12 处 `No module named 'mcp'`、
  1 处 `'anydoc'`)。换 `/root/.venvs/design-studio/bin/python` 同一棵树 rc=0。
  > 这正是 08-05 turn_id 那单的形状(解释器没装 mcp ⇒ 整块闸假绿),
  > 只不过这次它是**红**着现形的。**本单起,最终收据一律用 venv 解释器。**
  > 它的 `source-stable: no` 也说明那 297 秒里我还在改文件 —— 双重不作数。
- `rc=143 @656e606` —— **断线砍的**(143 = 128+15 SIGTERM),`source-stable: no`。
  时间线:收据写在 12:06:03,新会话进程 12:06:14 起来。**半截,一律不当绿用**,
  文件保留不删(它自己写着 rc,不会撒谎),已在 setsid 下重跑 → `04:09:46Z` 那份 rc=0。
- `redcheck-mutation @70a320b` —— 内容是终版(含 N8/N8b、20 条),只是跑在 commit
  落下之前的工作树上。为了不留"说不清"的地方,已在 `656e606` 上原样重跑一遍,
  同样 20/0;两份都留着。

## Review

**规格自查(读 panel 输出之前先答):如果规格本身就是错的,会错成什么样?**

本单规格 = 「补 `WS_MINIMIZEBOX | WS_SYSMENU | WS_MAXIMIZEBOX` 三个不参与绘制的
样式位 ⇒ 拿回最小化动画,且外观零变化」。它有两处**判据结构上问不出**的地方:

1. **「外观零变化」是推的,不是测的。** 依据是"这几位只在有 `WS_CAPTION` 时才画东西"。
   判据能查的只有"我没碰 `WS_THICKFRAME`/`WS_CAPTION` 这类会改非客户区的位"(s3),
   查不了"Windows 实际画出来什么"。
2. **「补上 WS_MINIMIZEBOX 就有动画」这条因果链是外部来源给的**(微软 Q&A 1182399 +
   pywebview #1749),不是我实测的。Linux 上没有一条判据能证伪它。

⇒ **七条判据全绿,只证明"手段做对了",不证明"业主按下去有动画"。**
规格错的话,最可能的错法是:位补上了、动画仍然没有(因为真因是 WinForms 更上层的
某个行为),而所有判据照样全绿。**只有真机能定案 —— 这就是 0.92.0 清单 B1/B2 存在的理由;
   而清单把 A2「拿记事本对照一次」摆在最前面,正是为了先证伪第 2 条那个前提。**

**腿的花名册**(`panel-minanim-r3.roster` 原样粘):

```
# panel-review 花名册(2026-08-23 12:02:17)task=opendesign-minimize-animation
# PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
# impact-risk=standard requested-budget=1 selected-count=1
# selected=submimo(xiaomi/submimo)
# escalation=none
# snapshot=head:70a320b
# 日志:/root/aiwork/logs/panel-minanim-r3.*.log
submimo=PASS(verdict=UNKNOWN) subdeepseek=SKIP(rotation) subglm=SKIP(rotation) subkimi=SKIP(health:auth)
```

前两轮都没出结论,**也记在这儿**(失败腿不许静默):

```
r1 panel-minanim-20260823T034908Z: subglm —— .err 只有 "Terminated",且**根本没写出花名册**
                                   ⇒ 整轮 panel 被砍,不是这条腿自己判的
r2 panel-minanim-r2:               subkimi=FAIL(rc=1) —— .err "kimi exited rc=1",
                                   日志里只有 oracle 输出 + 一行标题,没有任何评审内容
                                   (r3 花名册把它标成 health:auth ⇒ 与既有的额度/鉴权账一致)
```

> r1「跑了却没写花名册」和记忆里 08-19 那两轮是同一个形状,**原因至今没定案**,
> 是一笔仍然敞着的账,不属于本单。

standard 档预算 = 1 条成功的腿,submimo 这一条给了实打实的评审内容,预算满足。

**findings**

- **F-A(我自审)** —— `window_api` 没在 `__init__` 里初始化,靠后面某条路径顺手赋值。
  → 挪进 `__init__`,`70a320b`。
- **F-G(我自审)** —— 补样式位那段如果抛异常,会把 `minimize()` **本身**一起带塌:
  业主按最小化 = 什么都不发生,比"没动画"严重得多。
  → 拆两层兜异常,并**补了一条判据 s7**(入口函数体只能是一个 `try`、except 接
  `Exception` 或更宽),`2359fae`。红检 N7/N7b 验证"删 try"和"收窄 except"都咬得住。
- **F-P1(submimo,standard 档唯一那条腿)—— 成立,是本轮最值钱的一条。**
  `test_win_ctypes_decls.py` 从建成起**只查 `argtypes`,没查过 `restype`**。
  ctypes 默认 restype 是 `c_int`(32 位有符号),而 `GetWindowLongPtrW` 的返回值
  就是窗口现有的样式 ⇒ 截断 = **读错**;读错的样式再或上新位写回去 = **窗口变形**。
  那正是 s2 拼命想防的后果,**它从返回那一路溜进来,s2 拦不着**。
  → 补两条断言(声明了 argtypes 就必须声明 restype;`...LongPtrW` 一族必须是
  指针宽度)+ 变异 N8/N8b,`656e606`。
  > 🔴 **自己记一笔:这条我在 design.md 里写到过**(「返回值和参数**必须**声明,
  > 不然 64 位值被截成 32 位,而且不报错」),**却只把参数那半边写进了判据。**
  > 「把该问的写进了规格却没写进判据」——同一种自伤又来了一次。

**接受但不修**(理由 + 影响范围):

- s3 的 `_code_identifiers` 会把**同名函数参数**当成越界标识符误报。误报方向是"更严",
  不会放过真越界;真撞上再改。
- s3 只查单个字面量,`0x00040000 | 0x00010000` 这种**组合写法**查不到。
  本仓所有样式位都以具名常量单独出现,现在够用;哪天有人写组合值,这条要补。

**arbitrated verdict(主裁)—— 代码面 PASS,产品面悬着。**

代码面:三份最终收据齐在 `656e606` 全绿、红检 20/0 无漏网、panel 唯一那条腿的发现
已收下并落地、我自审两条也修完。边界("不许碰非客户区")有 s3 机械守着。**PASS。**

产品面:**不给结论。** 见上面规格自查——本单全部证据都是"手段对不对",
"按下最小化到底有没有动画"这件事,**Linux 上没有任何一条判据答得了**。
这不是保守,是证据边界:业主真机走完 0.92.0 清单之前,这一单的产品结论是空的。

## Accepted deviations

- 方案 B 那一族(拖边缘分屏 B3 / Win11 Snap Layouts B4 / 假最大化 C1~C3)**明确不做**,
  它们要改非客户区(`WS_THICKFRAME`、`WM_NCCALCSIZE`、`WM_NCHITTEST`),
  是新写面,单独一单且必须规划双出。
- design.md 里那笔**自己的账**(「吸附也在」这句话没有证据却被抄进三处代码/文档,
  连上次真机清单 F1 都建立在它上面)**本单没修**。它靠业主真机拖一次边缘就能定案,
  已进 0.92.0 清单;定案之后再回头清那三处措辞。
