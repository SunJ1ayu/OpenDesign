# Design: opendesign-e2e-no-egress-browser-tmp

- Change: opendesign-e2e-no-egress-browser-tmp
- Status: draft

- 规划双出: 不适用:不是新写面、方向有 aiwork `no-egress-judging`(a6d65f0,已归档、跑了一个月)可照搬;开放点只有"守卫放哪一扇门",下面写了取舍。

## Approach

### ① e2e 无出口守卫(守在每个 e2e 进程自己身上)

- `tests/e2e/helpers.mjs` **模块顶部**(导入即生效,早于任何 e2e 场景代码 —— ESM 先求值被导入模块):
  1. 脚本名(`basename(process.argv[1])`)在 `NEEDS_LIVE_GATEWAY` 里 ⇒ 豁免,直接返回(要连主命名空间里的活网关与 8768)。
  2. `/proc/self/ns/net` 与 `/proc/1/ns/net` 相同(= 还在主网络命名空间)⇒
     - 若环境里已有 `DS_E2E_NOEGRESS_TRIED` ⇒ 拒跑(试过一次仍没隔离);
     - 先探 `unshare -n -- true`,不行 ⇒ 拒跑;
     - `spawnSync("unshare", ["-n","--","bash","-c",'ip link set lo up …; exec "$0" "$@"', node, ...execArgv, ...argv[1:]], stdio 继承, env 加 TRIED)`,
       父进程以子进程的退出码退出(信号 ⇒ 128+n)。场景代码只在子进程里跑一次。
  3. 已隔离 ⇒ 删掉 TRIED(防子进程继承后误判)⇒ 实测一次 `bash -c 'exec 3<>/dev/tcp/1.1.1.1/443'`,连得上 ⇒ 拒跑。
  - 拒跑一律 rc=78 + stderr 一句「🔴 无出口守卫:…」。
- `tests/e2e/_no_egress.py`:同一逻辑的 python 版(照搬 aiwork `tests/_no_egress.py`,环境变量名换成 `DS_E2E_NOEGRESS_TRIED`),
  3 个 `.e2e.py` 在任何本仓模块之前 `import _no_egress`。
- `NEEDS_LIVE_GATEWAY` 只在 helpers 里一份;`tests/e2e/run-all.sh` 的 `NEEDS_GATEWAY` 由判据 `ne5` 钉成与它逐项相同。

### ② 浏览器临时目录归测试自己所有

- `launchBrowser()`:`mkdtempSync(tmpdir()/ds-e2e-browser-)` → `chromium.launch({ …, env: {...process.env, TMPDIR: 它} })`;
  launch 抛异常 ⇒ 当场删目录再抛;launch 成功后注册 `process.on("exit")`:
  目录里还有东西 ⇒ stderr 一句「⚠️ 浏览器没走正常关闭,留下 <名字>(已收掉)」,若设了 `E2E_BROWSER_NOTES` 就追加一行 `<脚本名>: …`;然后删目录。
- 监听在 launch **之后**注册 ⇒ 排在 Playwright 自己的退出清理(杀浏览器)之后执行。
- `tests/e2e/run-all.sh`:`E2E_BROWSER_NOTES` 指到日志目录里的一个文件;汇总时有内容就原样打印(不改判定,只点名)。

## Key trade-offs / risks

1. **守在进程自己身上,不守在总跑入口**:手跑单条 e2e 是日常,只包 run-all 等于守错门(aiwork 同一条取舍)。
   代价:helpers 的导入有副作用(re-exec)。依赖"每个 `.e2e.mjs` 都导入 helpers" ⇒ `ne8` 钉结构。
2. **豁免按脚本名**:改名就能绕过 —— 这道闸本来只挡手滑,不挡蓄意(强度声明写进 helpers 注释)。
3. **re-exec 用 spawnSync**:父 node 被单独 SIGTERM 时子进程不跟着死(Ctrl+C 同进程组会一起收到)。遗孤问题归 `e2e-orphan-generation`,这里不加信号转发。
4. **`ip` 不在 ⇒ lo 起不来 ⇒ 所有本机连接失败**:响亮地红,不静默。
5. **浏览器残留被收掉后泄漏闸再也看不见它** —— 所以必须有 `E2E_BROWSER_NOTES` 那条点名,否则等于把报警器的信号吞了。
6. Chromium 在 `browser.close()` 返回时是否已删完自己的临时目录:探针 close 后立刻 `process.exit` 15 次 0 残留 ⇒ 正常路径不会误报。

## Alternatives considered

- **只在 `tests/e2e/run-all.sh` 里对每条套 `unshare -n`**:守错门(单跑不受保护),且与豁免名单要两处维护。不选。
- **给 ds_web 加环境变量关掉查更新**:只堵这一个口,下一个联网请求照样漏;还往产品里加一个判据专用的后门。不选。
- **代理黑洞(`HTTPS_PROXY=127.0.0.1:1`)**:不认代理的客户端直接绕过;不是"没有出口",是"约定别出去"。不选。
- **把 `org.chromium.Chromium.` 加进泄漏闸放行清单**:那是把报警器调钝,run-all.sh 里明文禁止。不选。

## Test strategy (oracle)

主 agent 拥有,先行落盘、单独 commit。全部在 `tests/test_e2e_harness_guard.mjs`(node 单测段,真 unshare / 真 chromium,不连外网 —— 唯一的外连是 `ne0` 的前提探测,它只 TCP 握手不发数据)。

| id | 断言 |
|---|---|
| `ne0` | 前提:本测试进程(主命名空间)能连上 1.1.1.1:443。连不上 ⇒ **判红并说明**(问不出"守卫切断了出口"),不许跳过 |
| `ne1` | 导入 helpers.mjs 的普通 e2e 形状脚本:跑起来时自己的 net ns ≠ 1 号进程的,且连不上 1.1.1.1:443;场景代码只执行一次 |
| `ne2` | `unshare` 用不了(PATH 前面放一个 exit 1 的假 unshare)⇒ rc=78、stderr 含「无出口守卫」、场景代码**一行没跑**(标记文件不存在) |
| `ne3` | 透传:场景 `process.exit(7)` ⇒ 外面 rc=7;额外命令行参数原样到达场景 |
| `ne4` | 豁免:脚本名为 `project-thread.e2e.mjs` / `new_chat.e2e.mjs` ⇒ 留在主命名空间(net ns == 1 号进程的) |
| `ne5` | 豁免名单单一来源:helpers 导出的 `NEEDS_LIVE_GATEWAY` 与 `tests/e2e/run-all.sh` 的 `NEEDS_GATEWAY` 逐项相同 |
| `ne6` | 环境变量不是身份牌:主命名空间里预先设 `DS_E2E_NOEGRESS_TRIED=1` ⇒ 拒跑 rc=78、场景没跑(不许当成"已隔离"放行) |
| `ne7` | python 版:导入 `tests/e2e/_no_egress.py` 的脚本在独立 ns 里、连不上外网;假 unshare ⇒ rc=78 且脚本体没跑 |
| `ne8` | 结构:每个 `tests/e2e/*.e2e.mjs` 都导入 `./helpers.mjs`;每个 `tests/e2e/*.e2e.py` 都 `import _no_egress`,且在 `import ds_` 之前 |
| `bt1` | 浏览器被 SIGKILL 后场景退出:外层 TMPDIR 里除 `node-compile-` 外剩 0 个;stderr 含「浏览器没走正常关闭」;设了 `E2E_BROWSER_NOTES` ⇒ 文件里有一行以脚本名开头 |
| `bt2` | 正常 `browser.close()` 后退出:外层 TMPDIR 剩 0 个;stderr 不含那句;notes 文件不存在或为空 |
| `bt3` | launch 失败(`executablePath` 指向不存在的文件):抛错,且外层 TMPDIR 里不留 `ds-e2e-browser-*` |

**这个 oracle 能被什么骗过?**

1. **"在独立 ns 里"≠"没有出口"**:ne1 同时问 ns 与真连一次,两样都要。
2. **exempt 名单写宽**(比如写成 `includes("e2e")`)⇒ 所有脚本都豁免、ne1 红;写窄 ⇒ ne4 红。两边都钉。
3. **守卫在场景代码之后才生效**(场景先 spawn 了 ds_web 再 re-exec)⇒ ne1 的"只执行一次"与 ne2 的"一行没跑"接住。
4. **run-all.sh 打印 notes 那一段没有行为判据**(要在仓里塞假 e2e 才问得到):只由阅读核对 + 红检声明为未判。
   它只影响"点名",不影响泄漏本身被收掉(bt1 钉)。
5. **真 e2e 在隔离里是否都还跑得通**:单测问不到 ⇒ 由 e2e 总跑(40 条)与全量总跑回答。
6. **bt1 的"浏览器没正常关"是我用 SIGKILL 造的**;真实泄漏是不是同一条路径没钉死(探针只证明 SIGKILL 会留同形目录)。
   上线后若总跑再出现泄漏闸红,说明还有别的路径 —— 那时 notes 应当已经点名,没点名就说明本单的假设错了。
