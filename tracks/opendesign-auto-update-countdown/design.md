# Design: opendesign-auto-update-countdown

- Change: opendesign-auto-update-countdown
- Status: draft
- 规划双出 / panel-explore:**不花**。行为业主 09-15 已在四个选项里选定(proposal 抄了原文),
  实现方向没有几条都站得住的分叉;剩下的是接口细节,由判据钉死。

## 先查清的三件事实(决定了方案形状)

1. **桌面版的网页存储每次关软件都清空。** 外壳 `webview.start()` 没传 `private_mode`,pywebview 6.2.1 默认
   `private_mode=True`,WebView2 走 InPrivate(已发包里 `webview/__init__.py:173`、`platforms/edgechromium.py:81`)。
   ⇒ 「这个版本自动试过」**不能记在 localStorage**,只能后端记在盘上。
2. **接力脚本换回旧版时,界面早就没了。** 回滚发生在外壳收摊之后,由 `%TEMP%` 里的 `.cmd` 做,
   旧版被重新拉起时谁也不知道上次失败过。⇒ 只能**动手前**先记"要自动试 X 了"(预写),
   下次打开"X 试过、我还是旧版" = 没成。
3. **查更新的缓存在进程内存里**(`ds_update._cache`)。每次打开软件是新进程 ⇒ 打开后第一次查一定是真查。
   上一单转来的「启动时绕过 6 小时缓存」已经天然成立,不用做;失败本来就不缓存,没有退避可绕。

## Approach

### 后端

**`GET /api/update/check`** 回包在原有字段之外多一个(**每次请求现算,不进缓存**):

```json
"auto_update": {"eligible": true, "why_not": null, "recent_failure": false}
```

`why_not` 取值(按下面顺序取**第一个**不满足的;`eligible=true` 时为 `null`):

| why_not | 条件 |
|---|---|
| `no_update` | `update_available` 不为真(含查失败) |
| `asset` | 安装包地址缺失,或 digest 不是可信 sha256(`ds_update_apply.parse_digest` 认不出) |
| `no_shell` | 环境变量 `DS_SHELL_LOCK_PORT` 不是纯数字(这个后端不是桌面外壳起的:开发方式、单独跑)。**外壳起的后端,从浏览器标签打开同一个地址也算**(交棒走得通,真会更新);不在查更新时去探端口 |
| `not_installed` | 活树不是安装器装出来的(与 `apply_update` 第 -2 步同一判断:`OpenDesign.exe` + `ds\bin\ds_shell.py`) |
| `path_unsupported` | `relay_path_problem(paths)` 非空(与 `apply_update` 第 -1 步同一判断) |
| `attempted` | `latest` 已在自动更新记账里(**逐个版本精确比**,不许子串 / 前缀 / "试过的最大版本") |
| `disabled` | 环境变量 `OPENDESIGN_AUTO_UPDATE` 为 `off`(不分大小写)。**排在最后**:Windows 真机判据靠「看到 disabled = 前面全成立」。名字不以 `DS_` 开头,因为外壳 `child_env` 会剥掉 `DS_*`。**只给判据用**,不是业主设置 |
| `error` | 算这件事本身抛了 —— **查更新照样 200**,原字段不受影响 |

`recent_failure`:`why_not == "attempted"` 且这个版本最后一次自动尝试距今 **不到 600 秒**(一律 `time.time()`)⇒ `true`,其余一律 `false`。
用途:接力脚本回滚、旧版被重新拉起之后,页面在横幅上说一次「上次自动更新没成功」(攻题 #1)。
GET 面只读(不许在查更新里记「已提示过」),所以用时间界定:回滚重开发生在几分钟内;过了 10 分钟再打开只在设置里说。

「不是安装包装的 / 没外壳 / 路径不行」放进来,是为了**不做注定失败的倒计时**:不然开发方式、浏览器里打开,
每次都会倒计时 10 秒然后报失败。与 `apply_update` 用**同一个判断**,不抄第二份(实现可以把 -2/-1 两步抽成共用函数)。

**`POST /api/update/apply`**:

- 请求体是 JSON 对象且 `"auto"` **恰为 JSON `true`** ⇒ 自动那条路;其余一切(空体、`{}`、坏 JSON、`"auto": "true"`)
  ⇒ 手动那条路,**行为一字不改**。
- 自动那条路,在现有的锁里、`update_available` 检查之后:
  1. 重算一遍上表(服务端二次把关:界面慢了一拍、两个窗口同时倒计时、或别的页面直接发请求,都绕不过去)。
     不满足 ⇒ `{"ok": false, "stage": "auto_skipped", "error": <why_not>}`,**什么都不准备、不记账**。
  2. 把 `latest` 记进账。记不下 ⇒ `{"ok": false, "stage": "auto_unrecorded", "error": <人话>}`,**什么都不准备**。
     宁可这次不自动,也不许"记不下 ⇒ 下次打开再自动 ⇒ 再失败"无限循环。
  3. 之后与手动完全相同(`apply_update` → `handoff` → 请外壳收摊)。

**记账文件**:`<数据根>\Logs\auto-update-attempts.json`,数据根就是 `paths_for_update` 算出来的那个
(`%LOCALAPPDATA%\OpenDesign`)。放 `Logs\` 是因为 t13 死线:更新前后 `Data\`、`UserData\` 逐字节不变,`Logs\` 豁免。
文件名用 ASCII(Windows e2e 的 pwsh 要按名字清它,runner 代码页对中文不友好)。
- 内容形状实现自定;要求**已记过的版本不丢**(追加,不覆盖)、每个版本带最后一次尝试时刻(`time.time()`)。
- 读:不存在 / 读不了 / 不是 JSON / 形状不对 ⇒ 当作空账(下一次记账会整份写成合法的)。
- 写:同目录临时文件 → 写完 `flush` → 对**这个临时文件**的 fd `os.fsync` → `os.replace` 到记账文件(不留半截文件;换名失败旧账完好)。
  任一步失败 ⇒ `auto_unrecorded`。调用写成模块属性 `os.fsync(...)` / `os.replace(...)`(判据按模块属性注入故障)。
- 每个版本**各自**记最后一次尝试时刻(不许一个全局时刻 —— 撤回刚试的 B 之后会把很久前试的 A 说成「刚失败」)。
- **查更新(GET)不许等更新锁**:真实更新要下载几十 MB,等锁的查更新会一直挂着;GET 也**绝不许自己开始更新**。
- 条件重判、记账、开始准备在**同一个锁**里(锁外先判再进锁,两个窗口会把同一版准备两次 —— 攻题 #4,判据问不到,闸③亲读)。

### 前端

`web/src/update.ts` 新增(纯函数,**永远不抛** —— 它们在渲染体里被叫,抛一次就整页白,0.94/0.98 栽过两次):

- `AUTO_UPDATE_SECONDS = 10`
- `shouldCountdown(info)`:`canApply(info)` 且 `info.auto_update.eligible === true`。
- `countdownText(latest, seconds)`:带版本号、带秒数、带「自动更新」。
- `autoFailureText(result)`:自动那次请求的结果要不要在横幅上说、说什么。
  - `null` / 成功 / `auto_skipped` / `busy` / `no_update` ⇒ `""`(不是失败,或者别处已在更新,安静收起)。
  - `auto_unrecorded`,以及 `stage` 为 `null`(请求没回来 / 非 200 / 回包不是 JSON —— 不知道服务端记没记账)⇒ 非空,**不许说**「不会再自动 / 不再自动」。
  - 其它失败 ⇒ 非空,包含 `applyHint(result)` 那句,并说明**这个版本不会再自动更新**。
- `autoRecentFailureText(info)`:`update_available` 为真、`why_not === "attempted"`、`recent_failure === true` ⇒ 一句非空的话:
  哪一版、上次自动更新没成功、不会再自动试、可以手动更新;否则 `""`。
- `autoWhyNotHint(info)`:`update_available` 为真且 `why_not === "attempted"` ⇒ 一句非空的话,告诉业主可以**手动**点「更新」;否则 `""`。

`App.tsx`:
- **只有页面加载后的第一次自动查、那一次请求自己的回包**可以开倒计时(或出「刚失败」横幅)。手动「检查更新」、中途把「打开时自动检查」打开触发的那次查,都不开。
- 取消是**这次页面生命周期**的:之后任何查更新、网络恢复、窗口切回来都不许再开倒计时。
- 倒计时中业主自己点了「更新」⇒ 倒计时停下,走完不再发。
- `shouldCountdown` 为真 ⇒ 横幅 `[data-ui="auto-update-banner"]`(不在设置弹层里、业主不翻任何菜单就看得见),
  每秒刷新 `countdownText`;里面 `[data-ui="auto-update-cancel"]` 点了 ⇒ 横幅收起、这次打开不再发请求。
- 走完 ⇒ 复用现有的 `applyUpdate`(同一把防重入闸、同一个 apply 状态),请求体 `{"auto":true}`。
- 请求中:横幅显示 `applyLabel`(「正在更新,OpenDesign 会自动关掉再重新打开」)。
- 打开时查到 `autoRecentFailureText` 非空 ⇒ 横幅显示它 + `auto-update-dismiss`,**不倒计时、没有取消按钮**。
- 失败:横幅显示 `autoFailureText`,带 `[data-ui="auto-update-dismiss"]`;`autoFailureText` 为空 ⇒ 横幅收起。
- 设置里「检查更新」下面:`autoWhyNotHint` 非空时显示 `[data-ui="auto-update-why-not"]`。
- 前端产物 `web/dist` 入库,改完要 build(总跑第⑤段查新鲜度)。

### Windows 真机 e2e(`.github/scripts/windows-update-e2e.ps1` + `update_e2e_verdict.py`)

- 🔴 攻题 #16:旧版一被拉起,真页面就会自己查到替身的新版、倒计时、自己发自动更新 —— 和脚本按节奏发 apply、布置注入的 e1~e8 互相撞。
  ⇒ 脚本顶层 `OPENDESIGN_AUTO_UPDATE=off`,e1~e8 行为不变。
- aw1:e1/e6/e8 更新前那次查更新 `why_not` **恰好是 `disabled`**(排最后 ⇒ 真桌面版里其余条件全成立;看到 eligible=true = 关不掉 = 场景被污染)。
- **e9(新)真 WebView 整条链**:复位不拉起 → 布置注入(同 e5,新版认不出 ⇒ 回滚)→ 摘掉开关 → 拉起旧版 → **脚本一次 apply 都不发**,
  等页面自己倒计时发起 → 接力脚本出现、回滚、旧版重新拉起 → 再等 45 秒:整个场景**只下载过一次**、没有第二个接力脚本、窗口在;
  回滚后**旧版一答话立刻**查更新:`attempted + recent_failure=true`,并记离拉起多久(≥570 秒判场景超时,不判产品错);
  观察窗**结束时**窗口与旧版仍在;替身日志时间戳:页面拿到清单 → 下载之间 8.5~20 秒(证明是页面倒计时发起,不是后端自己开装)。
  截图留横幅(不进裁决)。
  这是「装出来的真桌面版里打开软件真会倒计时」与「同一版本失败一次不再自动试」跨真实回滚 + 真页面重开的唯一证据(攻题 #6/#7)。
- 每个场景复位时清掉记账文件。

## Key trade-offs / risks

1. **没有"失败"这个事实,只有"试过"。** 成功之后本机就是新版,`attempted` 不会再被问到;
   所以"试过"与"失败过"在业主可见的行为上等价。代价:一次**成功**更新留下一行账(无害,不清)。
2. **「打开时自动检查」开关在桌面版记不住**(事实 1 的同一原因,既有问题)。业主关掉它想躲开自动更新,
   下次打开又是开的。本单不修(要么把偏好搬到后端,要么改外壳的 WebView2 存储模式,后者牵涉缓存与白屏史),
   记账;横幅上的「取消」覆盖单次需要。
3. **倒计时可能在业主已经开始干活时才出现**:查更新最坏三跳各 10 秒。只在"打开后第一次自动查"开,
   而倒计时本身可取消。不加"正在打字就推迟"之类的逻辑。
3b. **「刚失败」用 10 分钟界定**:10 分钟内关了再开会再说一次;回滚后接力脚本没把旧版拉起来(关了不回来)的那种,界面无从说起 —— 那是既有回滚逻辑的事。
3c. **测试开关 `OPENDESIGN_AUTO_UPDATE`** 进了产品代码。业主机器上没人设它;它只能把自动更新关掉,开不出任何东西。
4. **两个页面同时倒计时**(外壳窗口 + 浏览器标签):现有的锁挡住第二个(`busy`),`autoFailureText` 对 `busy` 安静。
5. **记账写不进去的机器**(Logs 不可写):每次打开都会倒计时一次然后安静地放弃(`auto_unrecorded` 有说明)。
   病态环境,不为它加探测。
6. **坏版本止损**:删掉 GitHub 上那个 release。已经自动试过的机器不会再试;没试过的机器查不到它。
7. **手动那条路不记账**(proposal 有理由)。

## Alternatives considered

- **前端 localStorage 记账**:桌面版每次关都清空(事实 1),等于没记。否决。
- **只记"失败"**:接力脚本回滚那种失败没有任何一方能记(事实 2)。否决。
- **让接力脚本回滚时写一个标记给下次打开读**:要改 GBK `.cmd` 生成器(t25~t38 一串真机栽过的地方),
  而"预写试过"已经能覆盖同一件事。否决。
- **后端自己在启动时直接自动更新**(不经界面):业主看不到、取消不了,违背他选的那一项。否决。
- **倒计时期间"现在更新"按钮**:业主没要。

## Test strategy (oracle)

主 agent 亲写,执行腿逐字节 off-limits。**编号 `au*`(后端)、`ac*`(前端纯函数)、E2E 段名 `AC-*`、Windows `aw*`。**
这张表是唯一权威,tasks.md 只引用。第二版、第三版(09-17)按 GPT-5.6-sol 两轮攻题改过,处置收货后并入 verify.md。

### `tests/test_ds_web_auto_update.py`(真 ds_web、端口 0、网络与安装全替身、`LOCALAPPDATA` 指到临时目录)

夹具:临时目录里摆出"装出来的样子"(`OpenDesign.exe` + `ds/bin/ds_shell.py`),`ds_root` 指 `ds`;
`DS_SHELL_LOCK_PORT` 设成数字;本机版本调旧;`apply_update` / `handoff` / `ds_shell_bridge_update` 用现有替身接缝。

| 编号 | 问什么 |
|---|---|
| au1 | 全部条件满足 ⇒ `auto_update == {"eligible": true, "why_not": null, "recent_failure": false}`,原有字段仍在 |
| au2a~au2f | 各单独破一个条件 ⇒ `why_not` 分别为 `no_update` / `asset` / `no_shell` / `not_installed` / `path_unsupported` / `attempted` |
| au1 补 | 查更新之后 `apply_update` 一次没被调(GET 自己不许开始更新) |
| au3 | 自动请求:**`apply_update` 被调用的那一刻,产品自己的查更新已经说 attempted**(预写;问产品,不读文件找子串;查更新不许等更新锁);顺序 apply → handoff → bridge |
| au4 | 准备失败之后,不带 force 的查更新 attempted;**换一个新 server(新进程)** 仍 attempted |
| au5 | 已试过的版本再发自动请求 ⇒ `auto_skipped`,`apply_update` 没被调 |
| au6 | 已试过的版本发**手动**请求(`{}`)⇒ `apply_update` 照样被调 |
| au7 | 记不下(`Logs` 是文件)⇒ `auto_unrecorded`,什么都不准备 |
| au8 | 记账文件是垃圾 ⇒ 仍 eligible;自动请求之后 attempted |
| au9 | 两个版本先后试 ⇒ 前一个不丢 |
| au9b | 试过 0.98.3 后撤回 ⇒ 从没试过的 0.98.2 仍 eligible(不许"试过的最大版本") |
| au9c | 试过 0.98.1 ⇒ 0.98.10 仍 eligible(不许子串 / 前缀) |
| au10 | 数据根下只写 `Logs/`,记账文件在 `Logs/auto-update-attempts.json` |
| au11 | `"auto": "true"`(字符串)不算自动 |
| au12a~e | 被拒的自动请求(`asset` / `no_shell` / `not_installed` / `path_unsupported` / `disabled`)⇒ `auto_skipped`、不准备、**不记账** |
| au13 | 记账:同目录临时文件,换名前对**同一个文件**(inode)fsync 过、且 fsync 时大小已与换名时相同(先 flush);`os.replace` 失败 ⇒ `auto_unrecorded`、不准备、**旧账完好**、没记上的版本不被当成试过 |
| au14 | `OPENDESIGN_AUTO_UPDATE=off` ⇒ `disabled`;它排在 `not_installed` 与 `attempted` 之后;`OFF` 也认 |
| au15 | 刚自动试过 ⇒ `recent_failure=true`;590 秒仍 true;610 秒 false(`time.time()`) |
| au15b | 时刻按版本各记:t0 试 A、t0+1000 试 B、撤回 B,t0+1010 查 A ⇒ attempted 但 recent_failure=false |

### `tests/test_update_ui.mjs` 追加(node --test)

| 编号 | 问什么 |
|---|---|
| ac1 | `AUTO_UPDATE_SECONDS === 10` |
| ac2 | `shouldCountdown`:可装 + eligible ⇒ 真;其余假 |
| ac3 | `shouldCountdown` 喂垃圾 ⇒ 假且不抛 |
| ac4 | `countdownText` 含版本号、秒数、「自动更新」 |
| ac5 | `autoFailureText`:null / 成功 / `auto_skipped` / `busy` / `no_update` ⇒ `""` |
| ac6 | `autoFailureText`:真失败 ⇒ 含 `applyHint` 那句、说不会再自动;每个失败 stage 都非空 |
| ac7 | `autoFailureText`:`auto_unrecorded` / stage null(请求失败、HTTP 500、非 JSON)⇒ 非空且**不含**「不会再自动」 |
| ac8 | `autoWhyNotHint`:有新版 + attempted ⇒ 含「手动」;其它 ⇒ `""`,垃圾不抛 |
| ac9 | `autoRecentFailureText`:有新版 + attempted + recent_failure ⇒ 含版本号、没成功、不会再自动、手动;其它 ⇒ `""`,垃圾不抛。「没成功」「不会再自动」认一组同义说法(ac6/ac7/AC-C2/AC-D 同一套) |

### `tests/e2e/auto_update_countdown.e2e.mjs`(真 chromium + 真 ds_web;check / apply 用 page.route 拦;视口 = 真窗口 1280×860 / 最小 960×640)

| 段 | 问什么 |
|---|---|
| AC-A | eligible ⇒ 横幅在视口内、没被盖住(命中测试时临时打开 pointer-events)、不在设置里;**页面自己记下**横幅第一次出现的时刻与字(10 秒);**出现到请求到达 8.5~12 秒**;恰好一次 apply,`auto === true`;之后说会关掉重开;打开一次只查一次 |
| AC-B | 960×640 点取消 ⇒ 收起;之后 online / visibilitychange / focus、手动检查、开关关再开 ⇒ 0 次 apply、不再出横幅 |
| AC-C | 早就试过(recent_failure=false)⇒ 不出横幅、0 次 apply;设置里 `auto-update-why-not` 含「手动」;**点设置里「更新」发出的是手动请求**(收货时补:点击事件被当成 auto) |
| AC-C2 | 刚失败(recent_failure=true)⇒ 横幅说版本 + 不会再自动,不倒计时、无取消;0 次 apply;能关掉 |
| AC-D | apply 回 `download` 失败 ⇒ 横幅含「下载」、无内部词、能关掉;apply 请求被掐断 ⇒ 横幅非空、不倒计时、**不说**「不会再自动」 |
| AC-E | 打开时已是最新;手动检查查到 eligible ⇒ 0 横幅、0 apply |
| AC-F | 自动检查关着;中途打开开关、查到 eligible ⇒ 0 横幅、0 apply |
| AC-H | 倒计时中手动点「更新」⇒ 倒计时停;全程只有那一次(非 auto)apply |

### Windows(`tests/test_update_e2e_harness.py`)

| 编号 | 问什么 |
|---|---|
| aw1 | e1/e6/e8 事实里 `check.auto_update.why_not` 不是恰好 `disabled` ⇒ 判红(含 eligible=true、别的原因、缺字段) |
| aw2 | e9 判定器:脚本发过 apply / 拉起时开关没摘 / 没有接力脚本 / 注入没中 / 坏新版没跑过 / 没回滚 / **下载不是恰好一次** / **清单→下载不在 8.5~20 秒** / 回滚后又有接力脚本 / 观察结束时没窗口或旧版不在答 / 回滚后不是 attempted + recent_failure / 离拉起 ≥570 秒(场景超时)⇒ 判红;缺任一事实 ⇒ 判红 |
| aw4 | 脚本静态:开关名与产品一致且**活得过外壳 child_env**(用真 child_env 核);第一次拉起之前已关;复位清账;e9 不发 apply、注入与摘开关在拉起之前、finally 装回;e9 排在带空格目录之前;工作流收据闸点名 e9 |

### 这份判据问不住什么(先写下来)

- 条件重判 / 记账 / 开始准备是否真在同一个锁里(攻题 #4)—— 闸③亲读。
- 横幅"好不好看";真机 WebView2 里横幅可见由 e9 截图人看,不进裁决。
- 回滚后接力脚本没把旧版拉起来(关了不回来)—— 界面无从说起。
- 记账文件被杀软 / 清理工具删掉 ⇒ 多试一次。
