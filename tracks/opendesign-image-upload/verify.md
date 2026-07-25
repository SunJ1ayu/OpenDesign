# Verify: opendesign-image-upload

- Date: 2026-07-26
- Verdict: **PASS**(ds-web 0.48.0;Windows 文件名语义 **UNTESTED on target**)

## Mechanical checks(全部主 agent 亲跑)

- [x] `pytest tests/` **640 passed** / 8 skipped(本单 oracle 30 例)
- [x] `node --test tests/*.mjs` 200/200;`npm run build` 绿
- [x] 真 chromium e2e **17/17**,含 `image_upload.e2e.mjs` **走完整条链**:
      真 DataTransfer 拖拽 → 提示回显落盘名 → 收件箱卡片可见 → 扫描整理出方案 →
      确认执行 → 文件真的落到方案说的位置
- [x] 安全面:既有 12 个写针孔的闸一字未动(diff 是纯增量:新 elif 分支、`_send` 加一行
      响应头、Handler 类属性)
- [x] **亲自截图看**:拖拽高亮态、上传后提示条(回显真实落盘名 + 引导指向「扫描整理」)

## Review

- lane: **full 四审,四条腿首次全部到齐**(submimo / subdeepseek-agent /
  subglm-agent(新切 bigmodel+glm-4.6v)/ subkimi)。**四方全 PASS**。
  日志:`/root/aiwork/logs/panel-upload-011615.*.log`
- 规格自查(先于任何 employee 输出写下,全文
  `/root/aiwork/tasks/opendesign-image-upload-my-review.md`):
  1. **落点是收件箱而不是"当前项目"** —— 若设计师的心智是"拖到这个项目的图墙里就该进
     这个项目",这一单做完他会觉得多了两步。这是规格层面的赌,只有真机能答。
  2. 只收图片(dwg/pdf 会被拒);8MB 上限(单反原图会撞)。
  3. 我自己实现中偏离过自己的规格三次(见下 findings 1-3),都是 oracle 抓回来的。

### findings

主审(读 employee 输出前):

1. **[已修·实现偏离规格] `../evil.png` 一度被 basename 洗成 `evil.png` 放行** →
   改成带目录成分**直接拒**(悄悄改写会把"对方想干什么"这条信息抹掉)。
2. **[已修·夹具] 体积超限时客户端 BrokenPipe** → 夹具接受"连接被掐断也算拒绝",
   零写盘断言仍要过。
3. **[已修·我的规格猜错] e2e 断言图落到项目内 `02-参考图`,实测系统归到
   `03-共享资源/参考图库`** → 判据改成**从方案里读目的地再核**。第四次"根因在我的规格"。
4. [核过·无事] 撞名 O_EXCL 占位 + `os.replace`;临时文件点号开头(列举天然跳过)+
   finally 清理;判据 u02/u11 分别锁字节不变与无残留。

employee findings 逐条仲裁(每条给依据):

- **subkimi F1「坏 taxonomy → 崩溃而不是降级」→ 接受,已修。**
  核实:`ds_intake.load_taxonomy` 坏表/缺表返回 `None`(ds_intake.py:85-107),
  `_find_inbox(cfg, None)` 会 `taxonomy["inboxDirs"]` 抛 TypeError → **连响应都不给**,
  浏览器只看到 Failed to fetch;而兄弟路径 `list_inbox`(:161-163)、stage(:209-211)
  一律降级成 `taxonomy_bad` → ds_web 映射 409。**我的新口是这一族里唯一会崩的**。
  已补 `taxonomy is None → 409 taxonomy_bad` + 判据 u14(先红检)。
  这是本轮最有价值的一条:**它打的不是安全面,是"这个仓自己定的诚实降级规矩"**。
- **subkimi F4「错误码翻不成人话」→ 接受,已修(两处)。**
  ①体积超限走通用 `bad request`,前端显示"上传失败(bad request)" → 改 **413 `too_large`**,
  人话"这张图太大了(单张上限 8MB)"(判据 u15;顺带修掉我夹具的空跑 —— 真发 20MB 会被
  掐断导致断言根本没跑,改成"声称 20MB 只发几字节"才真测到体积闸)。
  ②svg 的 mime 也是 `image/…`,能过前端过滤,到服务端被判 `bad_name` → 提示"改个名再试"
  = 错药方 → 服务端分出 **`bad_type`**,前端同时按**扩展名**过滤(判据 u16/u17)。
- **subkimi F2「verify.md 还是模板」→ 接受**:本文件即为兑现(当时确实没填)。
- **subkimi F3 + subdeepseek 的注释失真 → 接受,已修**:design.md 的
  "先 basename 剥目录成分" 与实现不符(实现更严);design.md/tasks.md 写"收件箱卡片也做
  投放区"而实现只在图墙 —— **不是漏做,是有意**:InboxCard 在"空箱且无待确认"时整卡不渲染,
  而"第一次拖图进来"恰恰是空箱那一刻,拖无可拖。已把这条理由写进 design。
  `test_n12` 的注释"只取末段"也与实现相反,已改名+改注释。
- **subkimi F5「nosniff 无判据」→ 接受,已补**判据 u18(GET /api/health 断响应头)。
  `Handler.timeout` 不加判据:计时类断言在 CI/负载下天然不稳,且 subkimi 已独立核过
  socketserver/http.server 的调用链与"无 SSE/长连接"这一前提。
- **subkimi F6/F7/F8(INFO)→ 接受不动作**:①占位文件与 os.replace 之间的毫秒窗口
  被并发扫描看到 → 自愈(下一轮扫描归档真文件),不覆盖不损坏;②Windows 特有非法字符
  `<>"|?*` 会在 `open(...,"xb")` 干净失败 → 500 + 清理;③4 字节字符 × 80 超 ext4 单段
  255 字节 → 干净 ENAMETOOLONG。三者都是"干净报错"而非静默损坏,与既有 UNTESTED 取舍一致。
- **subdeepseek / submimo / subglm:PASS 零阻塞**。subdeepseek 给了逐道闸的核对表
  (含"粗筛阈值 11184816 > 精确 11184812 ✓"这类真算过的细节),与主审自查一致;
  subglm 这条腿(新后端首战)给的是概括性确认,**深度明显低于另外三条,不足以当证据**,
  只作"没提出反对"记录。

### arbitrated verdict(主裁)

**PASS**。四方一致通过,但真正有价值的两条 finding 都来自 subkimi,且都不在安全面上 ——
一条是"违反了本仓自己的降级规矩",一条是"错误码翻不成人话"。**四腿齐 PASS 没有降低本单
的标准:主审自己在实现过程中抓到的三条(basename 洗白 / 夹具空跑 / 规格猜错落点)
无一被任何一条腿提出**,这正是"panel 是盲点网,不是判决"的又一次实证。

## UNTESTED on target(deployment-target 铁律)

- **Windows 文件名真实语义**:冒号 → NTFS 备用数据流、保留名(CON/NUL)→ 写到设备、
  尾点/尾空格被静默剥、大小写不敏感(`客厅.PNG` 与 `客厅.png` 同名)、260 全路径上限。
  开发机是 Linux,判据断的只是"闸拒不拒"(与平台无关,真绿);**Windows 上究竟怎样
  证明不了**。真机验收要实际拖一张**中文名带空格**的图。
- **真机验收要问的规格问题**:拖图进图墙 → 落收件箱 → 还要点两下才归档,
  这个节奏能不能接受?若期望"拖进哪个项目就进哪个项目",那是另一条路(需要新的写口设计)。

## Accepted deviations

- 收件箱卡片不做投放区(空箱时整卡不渲染,拖无可拖)。
- 只收图片、单张 ≤8MB、不做服务端压缩(压缩=改用户原始素材,不可逆)。
- 不做魔数校验(Windows 上能否执行由扩展名决定;读出面按扩展名发类型,且已加 nosniff)。
- `Handler.timeout` 无自动判据(理由见上)。
