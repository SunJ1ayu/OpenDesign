# Verify: opendesign-chat-image

- Date: 2026-07-26
- Verdict: **PASS**(ds-web 0.49.0,含修复轮;Windows 文件系统语义 **UNTESTED on target**)

## Mechanical checks(全部主 agent 亲跑,执行腿自述不作数)

- [x] `pytest tests/` **660 passed / 8 skipped**(本单新增 20:c01–c18 + u19/u20)
- [x] `node --test tests/*.mjs` **228/228**(新增 28 条 media 判据)
- [x] `npm run build` 绿;`npx tsc --noEmit` 无输出
- [x] **首轮 15 条自起 e2e 全绿;修复轮后重跑 6 条关键路径全绿**,含新 `chat_image.e2e.mjs`(无收件箱→点建→两入口进图→
      svg 被拦→发送断 media→存进收件箱→回显绝对路径)与既有 `image_upload.e2e.mjs`
      (证明改提示条没破它的"已存进收件箱"断言 —— 所以提示词保留这个前缀再接路径)
- [x] **真 gateway 冒烟**(e2e 的 stub 证明不了的那一半):按前端同一形状发左紫右橙
      色块 → `mimo-v2.5` 回"左半紫色,右半橙色" ⇒ media 形状与限额抄对了、nanobot 真收下
- [x] **亲眼看 6 张截图**:收件箱缺失卡 / 1 张 / 4 张 + 第 5 张被拒 / 气泡 / 存入提示 /
      收件箱路径行
- [x] 安全面:既有 13 个写针孔一字未动(diff 纯增量);无新依赖;
      `git diff --summary` 无 `mode 120000`(符号链接事故的常规复查)

## Review

- lane: **full 四审**(新输入面 + 本服务第一个"建目录"的写针孔)。
- 主审自评全文(**先于任何 employee 输出写下**):
  `/root/aiwork/tasks/opendesign-chat-image-review-my-review.md`
- 派发带了 `PANEL_ORACLE_CMD`(先跑 oracle 再看任何 verdict)、`PANEL_DIFF_BASE=ecd0a82`
  与 `PANEL_INCLUDE`(把 oracle 文件喂给 chat 腿 —— 它们只看增量 diff,看不见基线
  commit 里的判据)。
- 规格自查(读任何 panel 输出之前答):**oracle 是我写的,可能本身就错**。最可能错的
  两处 ①"落点/节奏"这类规格赌 panel 验不了(只有真机能答);②前端限额常量是我从
  nanobot 源码抄的,抄错的后果不是报错而是**消息静默消失**,而冒烟只证明"1 张小图能通"。

### 主审自己抓到的(无一来自 reviewer)

1. **[已修·并发] 图片名额算在闭包里 → 拖两次能突破 4 张再被静默截断。**
   `addFiles` 读 `attached.length`,而读文件是 async 的:两次拖拽都读到旧值,多出来的
   被 `setAttached` 里的 `.slice(0,4)` 悄悄吃掉。**静默截断正是限额提示要避免的事**。
   改 `reservedRef` 进 await 前同步占位,读失败/不合规还回,撤图 -1,发送归零。
2. **[已修·提示失真] 多张图存收件箱时提示报"最后一张的完整路径"**,其余几张叫什么
   没人知道(撞名会被服务端改名)→ 改成"目录 + 每张真实落盘名"。
3. **[已修·视觉,断言接不住] 气泡内图 180px × 4 张把用户气泡撑到接近满宽**
   (用户消息本是"低对比右对齐"的配角)。同 `columnCount==="3"` 那次的教训:
   e2e 全绿也照样丑 → 缩到 116px。**只有真截图接得住这一类**。
4. **[已修·夹具] 我把 e2e 的 ① 写在 `/` 上,而收件箱卡片只在工作区路由**
   (`App.tsx:443`)。红检时发现并改成先切 `#/workspace` ——
   **第五次"根因在我的规格/夹具自己错"**。

### employee findings 逐条仲裁(每条给依据)

到齐 **3 腿**:submimo(PASS)、subdeepseek-agent(PASS)、subglm(**chat 腿**,agent 腿 rc=1
自动回落;PASS)。**subkimi 900s 超时 rc=1 没出结论,但它的思考日志(1353 行)里有实货**,
按"孤腿信号最值钱"的经验照样逐条查了 —— 事后看,本轮最有价值的两条都出自它。

**接受并修了(4 条)**

1. **subkimi(未成文,思考日志):前端按扩展名判类型,而 nanobot 按 data URL 的 mime 判。**
   核实成立:`nanobot/channels/websocket.py:614-621` 用 `_extract_data_url_mime` →
   `_UPLOAD_MIME_ALLOWED`。某些环境 `File.type` 为空 → data URL 成 `data:;base64,…` →
   上游认不出 → `_abort("decode")` → **整条消息被拒**,名字再对也没用。
   → 加 `isSendableDataUrl`(照抄上游白名单),判据 m24–m27。
2. **subkimi:`applyEvent` 的 `error` 分支只解锁 busy、什么都不显示。**
   顺着它的线读源码后确认这是**本轮最严重的一条**:nanobot 拒图时明明回
   `{"event":"error","detail":"image_rejected","reason":…}`(websocket.py:724-740),
   而我们一个字都不转达 → 用户看到"自己的气泡在屏上、没有回复、没有解释"。
   **我在 my-review 里把"消息静默消失"写成了限额抄错的风险,其实真正的静默来自我这边。**
   → 加 `chatErrorMsg` + 输入卡上方的错误行,判据 m19–m23;**并用真 gateway 实证**:
   发 5 张图 → 实收 `image_rejected/too_many_images`,映射对得上。
3. **subdeepseek F3:连点两次「帮我建收件箱」,第二次回 409 `name_taken`("根目录下有个
   同名文件")= 对用户撒谎。** 核实成立(竞态输了走 FileExistsError 分支)。
   → 抽出 `_ensure_inbox_dir`,EEXIST 后复查:真是目录 → `already_exists`;
   判据 c15/c16/c17(顺带修正:助手单独用时"已是目录"也不该报 name_taken)。
4. **subdeepseek F1 + subglm MEDIUM(两家独立提出):⑭ 缺 Windows 保留名检查。**
   我原本想按"名字来自机主自己的配置、不是网线上的输入"拒掉;但复用现成的
   `_WIN_RESERVED`(上传口早有)只要一行,且把一个含糊的 500/`name_taken` 变成明确的
   `bad_inbox_name` → 接受,判据 c14。
5. **subkimi:建成后整卡消失(空箱=隐身),没有任何确认。** 核实成立,且这一刻恰恰是
   最该把路径给用户看一次的时候(他的原话就是"收件箱在我电脑哪个文件夹")→ 加
   `[data-ui="inbox-created"]` 确认行 + e2e 判据。
6. **subkimi:`uploadErrMsg("inbox_not_found")` 仍写"先建一个"**,不指向新按钮 →
   接受,改成"去工作区页的收件箱卡片点「帮我建收件箱」",判据 m28。

**证伪 / 拒绝(3 条)**

- **submimo 唯一 finding:"islink→lexists→mkdir 之间有 TOCTOU,mkdir 会跟随 symlink"**
  → **拒,已实测证伪**:`os.mkdir` 对最终路径段永不跟随符号链接,名字存在即 `EEXIST`
  (我用真链接 + 悬空链接各跑了一次,外部目录始终为空)。它把"能在外面建目录"这个结论
  凭直觉给了,而事实相反。
- **subkimi:"8MB 到底按解码后字节还是按 data URL 长度算?抄错就静默丢消息"**
  → **拒(问得好但答案是对的)**:`nanobot/utils/media_decode.py:62-66` 是
  `len(base64.b64decode(payload)) > limit`,即**解码后字节**,与我的 `dataUrlBytes` 同单位。
- **subkimi:"只发图不写字(content:"")可能被上游拒 → 静默丢消息"**
  → **拒,双重证伪**:源码 `websocket.py:741-743` 明写 "Allow image-only turns";
  真 gateway 实发 content:"" + 1 图 → mimo 回"收到一张绿色的图…",没有 error 事件。
- **subglm LOW:"reservedRef 并发仍可能不准"** → **拒**:`pickChatImages(…, reservedRef.current)`
  与 `reservedRef.current += …` 之间没有 await,JS 单线程下第二次调用必然读到已加过的值。
- **subglm LOW:"多图提示只显示最后一张路径"** → 有效,但**这条是我自己先抓到并已修的**
  (见上"主审自己抓到的"第 2 条);且它是**读了我的 verify.md** 才写出来的(见下"过程问题")。
- **subdeepseek F2:`dataUrlBytes` 正则回溯爆炸** → **拒**:正则两端锚定、输入来自
  `FileReader` 而非网线,且 `[^,;]*` 与 `(?:;[^,;]+)*` 无嵌套量词重叠。

### 过程问题(必须记下来,比上面任何一条 finding 都值钱)

**我违反了自己的反锚定规矩:先写了 `verify.md`(含我的 findings)再派发 panel。**
证据:subglm 的 LOW#3 原文写着"(已在 verify.md 中标记为已修复)"—— 它读到了我的自评,
那条腿的"独立"作废。AGENTS.md 明写"正确节奏是先派发、后写 verify.md"(07-21 同款事故),
我今天又踩了一次。`panel-review` 的 anchor-leak 报警没响,因为 verify.md 是**已跟踪文件的
未提交修改**,而报警只看未跟踪文件 —— 工具债一条,记进 review-tooling 队列。

### arbitrated verdict(主裁)

**PASS**(修复轮后)。

三腿 PASS 里只有 subdeepseek 的 F3 是真 bug;**本轮最有价值的两条(mime 单位错位、
上游错误不转达)来自那条超时没出结论的 subkimi**,又一次印证"孤腿/失败腿的信号最值钱,
一致 PASS 最没信息量"。同时,submimo 唯一那条 finding 是**凭直觉给的错结论**,
被一次 30 秒的实测证伪 —— 再次说明 reviewer 的话必须逐条落到代码/实测上。

修复轮后亲跑:`pytest` **660 passed / 8 skipped**、`node --test` **228/228**、
`npm run build` 绿、6 条关键 e2e 全绿(chat_image / image_upload / intake /
intake_simplify / frontend_p1 / gallery_order)。

## Accepted deviations

- **⑭ 没做"建完自动重试上传"**:建收件箱与上传是两个动作,串起来会让人搞不清刚才
  到底发生了什么。(修复轮补上了建成确认行 —— 原来"卡片消失即回执"的说法站不住,
  见仲裁第 5 条。)
- **不自动双写**(design D2):发给模型的图不都是资产。这是规格赌,只有真机能答。

## UNTESTED on target(Windows 真机)

- ⑭ 的 `os.mkdir` 遇 Windows 保留名 / 大小写不敏感文件系统(判据全是 Linux 语义)。
- 粘贴截图在 Windows 上统一叫 `image.png`,连发多张走撞名改名路径(`image (2).png`)。
- 中文名 + 空格的截图文件名(与 0.48.0 遗留的同一条未验项)。
- ~~前端限额只验了"1 张小图能通"~~ **已在修复轮消掉**:第 5 张实发真网关 →
  `image_rejected/too_many_images`;8MB 的单位基准直接读了 nanobot 源码(解码后字节);
  只发图不写字实发真网关 → 正常回复。**这条不再是残余风险。**
- 仍未验:8MB 边界值(8MB+1 的真网关行为)—— 单位既已从源码确认,风险从"静默丢消息"
  降为"提示措辞是否精确",且现在上游拒了也会显示出来。
