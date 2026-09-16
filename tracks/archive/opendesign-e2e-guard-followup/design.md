# Design: opendesign-e2e-guard-followup

- Change: opendesign-e2e-guard-followup
- Status: draft

- 规划双出: 不适用:只动判据侧工具(两个 run-all 的汇总与 e2e 守卫),不是新写面、方向不开放 ——
  每条改法都由上一单第 2 轮的复现收据直接定形。

## 先答 proposal 里挂着的那个翻译问题

「说得出是哪一条」是不是非得把**名字**塞进汇总行?**是。** 量过的理由:

- 浏览器没关干净**不改判定**,e2e 段照样绿 ⇒ 外层走的是绿路径。
- 外层默认跑法(不带 `--with-gateway`)**必有 2 条 SKIP** ⇒ 走 `n_skip>0` 那支 ⇒ `rm -rf "$log_dir"`。
  也就是说**默认跑法下日志一定被删**,「红了日志会留着」这条退路在这件事上永远走不到。
- 这类泄漏是**偶发**的(09-15 e2e 单跑 4 遍 0 残留)⇒ 只报次数、让人重跑去找是谁,大概率复现不出来。
⇒ 在默认跑法里唯一留得下来的是终端上那张汇总表(以及 runlog 收据)。名字必须在那一行里。

## Approach

**① 点名簿归外层,外层读数据、不数打印出来的字(F1+F2+F3)**

- `tests/run-all.sh` 在 ⑥ e2e 段之前 `export E2E_BROWSER_NOTES="$log_dir/e2e-browser-notes.txt"`;
  段跑完直接读这份文件:行数 = 次数,每行冒号前 = 脚本名(按名合并,重复的记 `×N`),
  拼成 `⚠️ 浏览器收容 N 次(已自动收掉):a.e2e.mjs×2 b.e2e.mjs` 挂进 `note_last`。然后 `unset`。
  - 为什么不再 grep 日志:grep 的是**给人看的打印**,内层表头也含同一句话 ⇒ 多数 1(F3);
    点名簿本来就是结构化数据(`<脚本名>: …`,格式由 bt1 钉),读它就没有「两处文案逐字相同」这种约束要守。
  - 为什么放外层的 `$log_dir`:外层日志目录在跑 e2e 之前就存在 ⇒ 不是泄漏闸眼里的新条目;绿了随目录一起收。
  - 为什么 export 放在 ⑥ 前而不是文件头:② node 单测段里的判据会起自己的场景,
    文件头 export 会让它们往外层点名簿里写,汇总行就会报出判据自己造的「收容」。
- `tests/e2e/run-all.sh` 改成**尊重外面给的路径**:`${E2E_BROWSER_NOTES:-$log_dir/browser-notes.txt}`。
  单独跑内层时行为不变(照旧打印点名块)。

**② 回环判定读 errno(F4)**:`helpers.mjs` 用 `spawnSync(process.execPath, ["-e", <net.connect 127.0.0.1:1>])`
取 `err.code`,`ENETUNREACH`/`EHOSTUNREACH` ⇒ 拒跑。与 python 版同一判法,不看任何文案、不经过 bash。
实测:lo 没起 `ENETUNREACH`、起了 `ECONNREFUSED`,38ms。

**③ python 回环补判据(F6)**:代码不动(`_no_egress.py` 的 errno 判法本来就对),只补判据。

**④ README(第 1 轮 #8)**:`tests/e2e/README.md` 补一节「无出口守卫」:导入即生效、要 root + `unshare -n`、
拒跑码 78 长什么样、豁免两条、`E2E_BROWSER_NOTES` 是什么。

**⑤ 中途发现(外层真跑撞出来的,09-16 17:45):TMPDIR 一深,浏览器一启动就崩,而且报错不说为什么**

- 外层总跑(注入探针那次,收据 `outer-run-injected-leak-probe`)里 **node 单测段红 3 条:bt1 / bt2 / bt4**,
  报错都是 `browserType.launch: Target page, context or browser has been closed`。单跑全绿。
- 根因(确定性实验,只改 TMPDIR 长度):Chromium 在它的 TMPDIR 里建 `org.chromium.Chromium.XXXXXX/SingletonSocket`,
  Unix socket 路径上限 **107 字符**;实测 107 过、108 崩。`launchBrowser` 再套一层 `ds-e2e-browser-XXXXXX`
  ⇒ 外层 TMPDIR 超过 40 字符就崩。外层总跑里泄漏闸把 TMPDIR 设成 `/tmp/ds-leakprobe-XXXXXX`(24)(这是泄漏闸临时目录的命名样式,不是证据地址 [仓外不承重]),
  判据再套一层 `ds-guardtest-bt1-tmp-XXXXXX` ⇒ 24+28+22+45 = **119**。真 e2e 段只有 24+22+45 = 91,所以没事。
- ⇒ **bt1/bt2 自上一单起在全量总跑里一直是红的**;上一单从没真跑过外层,所以没人看见。
- 红了先问是不是真 bug:**一半是**。
  - 真 bug:`launchBrowser` 把「路径超长」崩成一句毫无线索的话。任何人 TMPDIR 深一点(比如会话临时目录)跑 e2e,
    会看到全部场景秒挂,和「前端崩了」长得一样。⇒ 起浏览器之前先算路径,超了就抛一句点明 TMPDIR 与上限的错,并收掉临时目录。
  - 判据自己的毛病:bt1/bt2/bt3 与造点名的 helper 用的夹具目录名太长,在外层总跑里**结构上问不到**它们要问的事
    (浏览器根本没起来)。⇒ 夹具目录改成短前缀(`gt1-` 等),断言一个字不动。
  - 改考卷的理由写在这里,并补一条**更强、会先红**的判据 bt6(下表),不是只把名字改短了事。

## Key trade-offs / risks

1. **bt4/bt5 是「抽出真脚本的一段来跑」**,不是跑整个外层(6 分钟 + 真 chromium)。抽取锚点是注释标题行;
   锚点改名 ⇒ 抽出来是空的 ⇒ 判据**响亮地红**并说「抽不到」,不会静默绿。代价是改标题要连判据一起改。
2. **bt4 用假内层**:它问的是「外层有没有把路径交给子进程、有没有读对、有没有挂进汇总」,
   「真内层有没有用那个路径」由 bt5 问,「helpers 写不写」由 bt1 问。三截各有判据,**合起来**的那一次由
   「外层真跑 + 临时注入一条会泄漏的 e2e」一次性收据回答(不进仓:永久留着会让每次总跑都报一次收容)。
3. **F4 的判据靠假 bash 模拟翻译后的报错**(本机没有 libc.mo,造不出真的非英文 locale)。
   新实现根本不调 bash,所以这条对新实现是「不受干扰」,对旧实现是「被骗过」—— 方向正确,实测旧实现下场景照跑 rc=0。
4. ne12 钉的 python 代码**已经存在**,判据写下去当场就是绿的 ⇒ 它的红靠**变异**证明(删掉 python 回环块 ⇒ 必须红),
   收据单独跑,不混进「判据先行 N 红」的数里。

## Alternatives considered

- **外层继续 grep 日志,只把 `-c` 改成数缩进行**:还是在解析给人看的文字,下次内层改一下排版又漂;不选。
- **绿路径也留日志目录**:违背外层「没红就收」的卫生约定(08-18 为它修过一次),且名字仍不在人眼前;不选。
- **把两个 run-all 的公共逻辑抽成一个 source 的 shell 库**:只有外层一处需要汇总,抽库是为不存在的第二个用户;不选。
- **node 回环检查改成模块顶层 `await`**:会把同步的守卫改成异步,`process.exit` 的时序要重想;
  `spawnSync` 起一个 38ms 的 node 更小;不选。

## Test strategy (oracle)

主 agent 拥有,先行落盘、单独 commit。全部在 `tests/test_e2e_harness_guard.mjs`。

| id | 断言 |
|---|---|
| `bt4`(重写) | 抽出 `tests/run-all.sh` 的 ⑥ 段,桩掉 `run_seg`/`note_last`,假内层**原样**写入 3 行由**真 helpers** 产出的点名(a 两次、b 一次)并照内层格式打印点名块 ⇒ 汇总含 `浏览器收容 3 次`、`a.e2e.mjs×2`、`b.e2e.mjs`;假内层不写点名 ⇒ 汇总里没有「浏览器收容」;抽不到这一段 ⇒ 红并说明 |
| `bt5` | 抽出 `tests/e2e/run-all.sh` 里建日志目录到设点名簿那一截执行:外面给了 `E2E_BROWSER_NOTES` ⇒ 原样沿用;没给 ⇒ 落在内层自己的 `ds-e2e-log-*` 里 |
| `ne11` | 假 `ip` 让 lo 起不来 + 假 `bash` 把 `unreachable` 翻成别的语言 ⇒ 仍然 rc=78、横幅含「回环」、场景没跑 |
| `ne12` | python 版:假 `ip` 让 lo 起不来 ⇒ rc=78、横幅含「无出口守卫」与「回环」、脚本体没跑 |
| `bt6` | TMPDIR 深到 Chromium 的 socket 路径超 107 ⇒ `launchBrowser` 抛出含「TMPDIR 太深」与「107」的错(不是 Chromium 崩成 browser has been closed),且不留 `ds-e2e-browser-*` |

旧 bt4(文本里有那句话且排在 `note_last` 之前)删掉 —— 它被注释满足,留着只会继续假绿。

**这个 oracle 能被什么骗过?**

1. **三截各自绿、接缝处断了**:比如外层 export 了,内层也尊重了,但 run_seg 实际调用的命令不经过 env
   (某天改成 `env -i`)。单测问不到 ⇒ 由「外层真跑 + 注入泄漏 e2e」那份一次性收据回答,
   **没有那份收据不许判 PASS**。
2. **bt4 的假内层格式和真内层漂开**:假内层的点名行来自真 helpers(不是字面量),打印块照抄内层那 3 行;
   若内层打印块改了排版,bt4 不会红 —— 但新实现根本不读打印块,漂了也不影响汇总,所以这个洞不承重。
3. **ne11 的假 bash 漏拦**:它只改写 `/dev/tcp/127.0.0.1/` 那一种调用;若旧实现换成别的 bash 写法,假 bash 骗不到它。
   这里要的只是「证明新实现不看文案」,对新实现不构成放水。
4. **用户眼里的成功**(这里的「用户」是下一个看总跑汇总的我):默认跑法下,某条 e2e 没关浏览器,
   汇总表那一行**直接写着它的名字和次数**,不用翻任何日志。只有注入那份收据能直接看到这一行长什么样。
