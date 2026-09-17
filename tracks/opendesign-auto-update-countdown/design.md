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
"auto_update": {"eligible": true, "why_not": null}
```

`why_not` 取值(按下面顺序取**第一个**不满足的;`eligible=true` 时为 `null`):

| why_not | 条件 |
|---|---|
| `no_update` | `update_available` 不为真(含查失败) |
| `asset` | 安装包地址缺失,或 digest 不是可信 sha256(`ds_update_apply.parse_digest` 认不出) |
| `no_shell` | 环境变量 `DS_SHELL_LOCK_PORT` 不是纯数字(没有桌面外壳接交棒) |
| `not_installed` | 活树不是安装器装出来的(与 `apply_update` 第 -2 步同一判断:`OpenDesign.exe` + `ds\bin\ds_shell.py`) |
| `path_unsupported` | `relay_path_problem(paths)` 非空(与 `apply_update` 第 -1 步同一判断) |
| `attempted` | `latest` 已在自动更新记账里 |
| `error` | 算这件事本身抛了 —— **查更新照样 200**,原字段不受影响 |

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
- 内容形状实现自定;只要求**已记过的版本不丢**(追加,不覆盖)。
- 读:不存在 / 读不了 / 不是 JSON / 形状不对 ⇒ 当作空账(下一次记账会整份写成合法的)。
- 写:同目录临时文件 + `os.replace`(不留半截文件)。

### 前端

`web/src/update.ts` 新增(纯函数,**永远不抛** —— 它们在渲染体里被叫,抛一次就整页白,0.94/0.98 栽过两次):

- `AUTO_UPDATE_SECONDS = 10`
- `shouldCountdown(info)`:`canApply(info)` 且 `info.auto_update.eligible === true`。
- `countdownText(latest, seconds)`:带版本号、带秒数、带「自动更新」。
- `autoFailureText(result)`:自动那次请求的结果要不要在横幅上说、说什么。
  - `null` / 成功 / `auto_skipped` / `busy` / `no_update` ⇒ `""`(不是失败,或者别处已在更新,安静收起)。
  - `auto_unrecorded` ⇒ 非空,**不许说**「不会再自动」(它没记上,下次还会试)。
  - 其它失败 ⇒ 非空,包含 `applyHint(result)` 那句,并说明**这个版本不会再自动更新**。
- `autoWhyNotHint(info)`:`update_available` 为真且 `why_not === "attempted"` ⇒ 一句非空的话,告诉业主可以**手动**点「更新」;否则 `""`。

`App.tsx`:
- **只有页面加载后的第一次自动查**的结果可以开倒计时。手动「检查更新」、中途把「打开时自动检查」打开触发的那次查,都不开。
- `shouldCountdown` 为真 ⇒ 横幅 `[data-ui="auto-update-banner"]`(不在设置弹层里、业主不翻任何菜单就看得见),
  每秒刷新 `countdownText`;里面 `[data-ui="auto-update-cancel"]` 点了 ⇒ 横幅收起、这次打开不再发请求。
- 走完 ⇒ 复用现有的 `applyUpdate`(同一把防重入闸、同一个 apply 状态),请求体 `{"auto":true}`。
- 请求中:横幅显示 `applyLabel`(「正在更新,OpenDesign 会自动关掉再重新打开」)。
- 失败:横幅显示 `autoFailureText`,带 `[data-ui="auto-update-dismiss"]`;`autoFailureText` 为空 ⇒ 横幅收起。
- 设置里「检查更新」下面:`autoWhyNotHint` 非空时显示 `[data-ui="auto-update-why-not"]`。
- 前端产物 `web/dist` 入库,改完要 build(总跑第⑤段查新鲜度)。

### Windows 真机 e2e(`.github/scripts/windows-update-e2e.ps1` + `update_e2e_verdict.py`)

- `_full_update`(e1/e6/e8):更新前那次查更新的 `auto_update.eligible` 必须为真 ——
  **这是唯一证明"装出来的真桌面版里倒计时条件真的会成立"的地方**;Linux 上的判据全是替身环境,
  `no_shell` / `not_installed` / `path_unsupported` 任何一条在真机上误判成立,倒计时就**永远不出现**,而其余判据全绿。
- e5(新版起得来但认不出 ⇒ 回滚):改用 `{"auto": true}` 发起;换回旧版、旧版起来之后再查一次 + 再自动请求一次:
  必须 `eligible=false, why_not="attempted"`,第二次请求 `stage="auto_skipped"`。
  **这是"同一版本失败一次不再自动试"跨一次真实回滚 + 重新拉起仍然成立的唯一证据。**
- 每个场景复位旧版时清掉记账文件(否则 e5 记下的新版号会让后面 e1/e8/e6 的 eligible 断言红)。

## Key trade-offs / risks

1. **没有"失败"这个事实,只有"试过"。** 成功之后本机就是新版,`attempted` 不会再被问到;
   所以"试过"与"失败过"在业主可见的行为上等价。代价:一次**成功**更新留下一行账(无害,不清)。
2. **「打开时自动检查」开关在桌面版记不住**(事实 1 的同一原因,既有问题)。业主关掉它想躲开自动更新,
   下次打开又是开的。本单不修(要么把偏好搬到后端,要么改外壳的 WebView2 存储模式,后者牵涉缓存与白屏史),
   记账;横幅上的「取消」覆盖单次需要。
3. **倒计时可能在业主已经开始干活时才出现**:查更新最坏三跳各 10 秒。只在"打开后第一次自动查"开,
   而倒计时本身可取消。不加"正在打字就推迟"之类的逻辑。
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

主 agent 亲写,执行腿逐字节 off-limits。**编号 `au*`(后端)、`ac*`(前端纯函数)、E2E 段名 `AC-*`,
Windows 断言挂在已有 e1/e5/e6/e8 上。** 这张表是唯一权威,tasks.md 只引用。

### `tests/test_ds_web_auto_update.py`(真 ds_web、端口 0、网络与安装全替身、`LOCALAPPDATA` 指到临时目录)

夹具:临时目录里摆出"装出来的样子"(`OpenDesign.exe` + `ds/bin/ds_shell.py`),`ds_root` 指 `ds`;
`DS_SHELL_LOCK_PORT` 设成数字;本机版本调旧;`apply_update` / `handoff` / `ds_shell_bridge_update` 用现有替身接缝。

| 编号 | 问什么 |
|---|---|
| au1 | 全部条件满足 ⇒ 查更新回包 `auto_update == {"eligible": true, "why_not": null}`,原有字段仍在 |
| au2a~au2f | 各单独破一个条件 ⇒ `eligible=false` 且 `why_not` 分别为 `no_update` / `asset`(digest 为空)/ `no_shell` / `not_installed` / `path_unsupported`(安装路径带 `%`)/ `attempted` |
| au3 | 自动请求:**`apply_update` 被调用的那一刻,记账文件里已经有这个版本**(预写);顺序仍是 apply → handoff → bridge,回包 `ok=true` |
| au4 | 自动请求且准备失败(替身 `apply_update` 报 verify 失败)⇒ 之后**不带 force** 的查更新 `why_not="attempted"`(不被 6 小时缓存吞掉) |
| au5 | 已试过的版本再发自动请求 ⇒ `stage="auto_skipped"`,`apply_update` 一次没被调 |
| au6 | 已试过的版本发**手动**请求(请求体 `{}`,界面按钮发的就是它)⇒ `apply_update` 照样被调 |
| au7 | 记不下(`Logs` 是个文件不是目录)⇒ 自动请求 `stage="auto_unrecorded"`,`apply_update` 一次没被调 |
| au8 | 记账文件是垃圾 ⇒ 查更新仍 `eligible=true`;自动请求之后 `why_not="attempted"`(被整份写好) |
| au9 | 两个不同版本先后自动试 ⇒ **前一个不丢**(追加不覆盖) |
| au10 | 数据根下自动那条路只写 `Logs/`(不碰 `Data/`、`UserData/`,t13 同一条死线) |
| au11 | `"auto": "true"`(字符串)不算自动 ⇒ 已试过的版本照样调 `apply_update`(手动语义) |
| au12 | 不满足条件的自动请求**不记账**(`no_shell` 下发自动请求 ⇒ 记账文件不存在) |

### `tests/test_update_ui.mjs` 追加(node --test)

| 编号 | 问什么 |
|---|---|
| ac1 | `AUTO_UPDATE_SECONDS === 10` |
| ac2 | `shouldCountdown`:可装 + eligible ⇒ 真;eligible 为假 / 缺 `auto_update` / 不可装(无 digest)⇒ 假 |
| ac3 | `shouldCountdown` 喂 null、字符串、数组、`auto_update: null`、`eligible: "true"` ⇒ 假且**不抛** |
| ac4 | `countdownText("0.98.7", 7)` 含版本号、含 7、含「自动更新」 |
| ac5 | `autoFailureText`:null / 成功 / `auto_skipped` / `busy` / `no_update` ⇒ `""` |
| ac6 | `autoFailureText`:`download` 失败 ⇒ 含 `applyHint` 那句,且说明不会再自动 |
| ac7 | `autoFailureText`:`auto_unrecorded` ⇒ 非空且**不含**「不会再自动」 |
| ac8 | `autoWhyNotHint`:有新版 + `attempted` ⇒ 非空且含「手动」;其它 `why_not` / 无新版 / 垃圾输入 ⇒ `""` 且不抛 |

### `tests/e2e/auto_update_countdown.e2e.mjs`(真 chromium + 真 ds_web;`/api/update/check` 与 `/api/update/apply` 用 page.route 拦)

| 段 | 问什么 |
|---|---|
| AC-A | eligible ⇒ 横幅在视口内可见、含版本号;不翻设置;约 10 秒后恰好一次 apply,请求体 `auto === true`;之后横幅显示「正在更新」 |
| AC-B | 点取消 ⇒ 横幅收起;再等过倒计时 ⇒ 0 次 apply |
| AC-C | `eligible=false, why_not=attempted` ⇒ 不出横幅、0 次 apply;设置里出现 `auto-update-why-not` 且含「手动」 |
| AC-D | apply 回 `download` 失败 ⇒ 横幅上出现含「下载」的说明;点关闭 ⇒ 收起 |
| AC-E | 打开时查到"已是最新";手动点「检查更新」得到 eligible ⇒ 等过倒计时仍 0 横幅、0 次 apply |
| AC-F | 打开时自动检查是关的;中途打开开关、那次查得到 eligible ⇒ 0 横幅、0 次 apply |

### Windows(`tests/test_update_e2e_harness.py` 追加判定器用例)

| 编号 | 问什么 |
|---|---|
| aw1 | e1/e6/e8 事实里更新前 `check.auto_update.eligible` 不为真 ⇒ 判红 |
| aw2 | e5 事实里 `apply_auto_again.stage != "auto_skipped"` 或 `check_after.auto_update` 不是 `{false, "attempted"}` ⇒ 判红;缺这两项 ⇒ 判红(没跑到 ≠ 没问题) |
| aw3 | e5 事实里第一次请求不是自动(`apply_body` 不含 auto)⇒ 判红(场景没摆好) |

### 这份判据问不住什么(先写下来)

- 横幅"好不好看"、业主真机 WebView2 里是否被别的层盖住 —— e2e 只证明 chromium 里可见。
- 真机上从**打开软件**到倒计时走完的整条界面链 —— Windows e2e 走接口层,不点窗口;界面链由 AC-A 在 chromium 里证。
- 记账文件在业主机器被杀软/清理工具删掉 ⇒ 多试一次。不防。
