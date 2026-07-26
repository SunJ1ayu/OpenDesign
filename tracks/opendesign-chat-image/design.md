# Design: opendesign-chat-image

- Change: opendesign-chat-image
- Status: draft

> Panel hook 判断:**不是**开放架构分叉,不跑 panel-explore。通道已由探针实测钉死
> (ws `media`),归档复用既有针孔⑬,唯一的取舍(自动双写 vs 手动按钮)有明确的
> 第一性依据(见 D2)。verify 阶段吃 **full 四审**(新输入面 + 新写针孔)。

## Approach

### D1 发图通道 = nanobot 原生 ws `media`,前端本地先拦限额

`messageEnvelope` 增加可选 `media` 参数,形状照协议:
`media: [{data_url: "data:image/png;base64,…", name: "客厅.png"}]`。

服务端(nanobot)限额:≤4 图/条、单图 8MB、png/jpeg/webp/gif、**svg 排除**、
任一项解码失败 → **整条消息不发布**。所以前端**必须自己先拦**,否则用户会遇到
"消息凭空消失"。本地闸(纯函数 `pickChatImages`,tests 直测):
扩展名 ∈ IMG_EXTS(与 `ds_workspace.IMG_EXTS` 同表,svg 不在内)、单图 ≤8MB、
一条最多 4 张、超出的**明确告知被丢下**而不是静默截断。

不走 ds_web 代理:聊天 ws 是浏览器 → nanobot 直连(既有架构),ds_web 不在这条路上。
= 本单**不给 ds_web 增加任何图片转发面**。

### D2 归档 = 气泡上「存进收件箱」按钮(手动),**不自动双写**

nanobot 把图存进它自己的媒体目录,不是项目工作区 → "看得见但归不了档"。
两种补法:

- (A) 发图时自动同时调针孔⑬存一份进收件箱。
- (B) 图发出去后,气泡上给一个「存进收件箱」按钮,点了才存。

**选 (B)**。理由:
1. 设计师发给模型的图**不都是资产**。"这个报错截图什么意思"这种图自动进收件箱 =
   给他制造垃圾,而收件箱是他要一条条过的地方 —— 污染收件箱比少存一张更贵。
2. (A) 有半成功态:media 发成功、上传失败 → 图在对话里但没归档,得设计一套补偿提示;
   (B) 天然没有这个态(按钮就地失败就地重试)。
3. (B) 与本仓既有规矩同源:**写盘一律人工触发**(整理要点「确认执行」)。

### D3 收件箱缺失:不破"不自造目录"原则,改成**人工点一下**(新写针孔⑭)

0.48.0 的注释写死了:`_upload` **不自己造目录**(网页在用户工作区凭空建文件夹 = 越权),
这条经过四腿评审。用户的新事实是"每个用户不一定都有这个文件夹",但这**不构成**
推翻它的理由 —— 悄悄建目录和用户按下"帮我建"是两件事。所以:

- 新针孔⑭ `POST /api/inbox/create`:**只**在工作区根下建 `taxonomy["inboxDirs"][0]`
  (默认 `00-收件箱`),且**仅当四个候选名全都不存在**时才建。
- 闸序照⑬:CT=application/json → 空 body(键白名单 = 空集)→ workspace 已配置 →
  taxonomy 可用 → `_find_inbox` 已找到则回 `already_exists`(不重建、不报错闹人)→
  目标 realpath + `within(root)` → 已存在同名**文件**(非目录)→ `name_taken` →
  `os.mkdir`(不 `makedirs`:只许一层,父目录必须是 root 本身)。
- 前端:`inbox_not_found` 的提示条旁边长出一个「帮我建收件箱」按钮,点完自动重试上传。

### D4 "东西去哪了" —— 落盘位置必须显示出来

1. `/api/upload` 响应加 `path`(绝对路径)。**不是新的泄漏类**:`/api/health` 早就
   回 `ds_root`,且这是 localhost 单机工具、路径本来就是用户自己填的。
2. 上传提示条从「已存进收件箱:x.png」改成回显完整路径,例
   「已存进 `D:\设计工作区\00-收件箱\客厅.png` —— 去伴随列点「扫描整理」归档」。
3. 收件箱卡片标题加一行灰字副标题 = 收件箱绝对路径(`GET /api/intake` 加 `path`)。
   这样用户**不用问人**也能知道去哪找。
   **只在 ds_web 处理器这一层拼 `path`,不动 `ds_intake.list_inbox`** —— 后者同时是
   MCP 工具(`list_inbox_tool`),往它的返回里塞绝对路径 = 把本机路径喂给 LLM 并上云,
   属于无谓地拓宽模型能看到的内容(`ds_tools.py:542` 的铁律)。网页要显示 ≠ 模型要知道。
4. `configured:false` + `reason:inbox_not_found` 时,顺带回**将要建在哪**
   (`root/inboxDirs[0]`),这样「帮我建收件箱」按钮能在点之前就把路径写在提示里
   —— 用户按下去之前就知道会发生什么。

## Key trade-offs / risks

- **发图靠模型认不认**:mimo-v2.5 实测能看见,但机主换别家模型(向导那单的事)
  可能看不见图 → 本单不做能力探测,提示语不承诺"它一定看得懂"。
- **base64 膨胀**:8MB 图 → data URL ≈ 10.7MB,4 张 ≈ 43MB 一条 ws 消息。
  nanobot 侧限额自己会拒,但浏览器内存和 ws 帧大小是真风险 → 本地闸把"4 张"和
  "单张 8MB"都拦在发送前,且**先读文件算真实字节**再决定,不靠 File.size 猜。
- **`path` 回显是本机绝对路径**:见 D4-1,判定为可接受;但**不回给聊天模型**
  (不进 media/content),只在网页 UI 显示。
- **针孔⑭ 是本服务第一个"建目录"的口**:虽然只建一层固定名,仍是写面扩张 →
  full 四审必须专门看它。

## Alternatives considered

- **上传走 multipart** —— 拒。⑬ 的注释已论证:multipart 是 simple content-type、
  不触发 preflight,收它等于给写口开 CSRF 洞。⑭ 同理保持 JSON。
- **发图自动双写收件箱** —— 见 D2,拒(污染 + 半成功态)。
- **让网页能整理桌面 / 传到桌面** —— 拒。桌面已在 `DS_ORGANIZE_ROOTS` 默认白名单,
  对话里"整理桌面"已能走完;为它放宽网页的 `within(root)` 闸,风险收益不成比例。
- **`makedirs` 允许建多层收件箱路径** —— 拒。只许 root 下一层,越少越好。

## Test strategy (oracle)

主 agent 亲自写、先红检、先 commit 再动实现。

1. `tests/test_ds_web_inbox_create.py`(针孔⑭,新文件):CT 闸 / 键白名单 /
   未配置工作区 409 / 坏 taxonomy 409 / 四候选全无 → 建出 `00-收件箱` 且 `mkdir` 只一层 /
   已存在 → `already_exists` 且**不重建**(mtime 不变)/ root 下同名文件占位 → `name_taken` /
   建完 `ds_intake.list_inbox` 立刻认得 / 用户 taxonomy 覆盖首候选 → 建的是覆盖后的名字 /
   root 是 symlink 指向外部 → within 闸拒。
2. `tests/test_ds_web_upload.py`(追加):响应带 `path`,且 `within(inbox, path)`、
   与 `name` 一致。
3. `tests/test_chat_media.mjs`(新):`messageEnvelope` 带/不带 media 两形状
   (不带时**不出现** `media` 键 —— 老信封逐字节不变);`pickChatImages` 的
   svg 拒 / 第 5 张被丢下并给话 / 超 8MB 被丢下并给话 / 大小写扩展名。
4. `tests/e2e/chat_image.e2e.mjs`(真 chromium + **假 ws 服务端**):粘贴一张真 PNG →
   缩略图出现 → 点发送 → 断言假服务端**真的收到**带 `media` 的 message 信封 →
   点气泡的「存进收件箱」→ 断言文件真的落到收件箱、提示条显示绝对路径。
   (发真图给真 gateway 烧 token 且答案不确定,不进 e2e;协议已由 07-26 探针钉死。)
5. 回归:`pytest tests/`、`node --test tests/*.mjs`、`npm run build`、既有 17 条 e2e。

**这个 oracle 能被什么骗过?**

- **最可能的假绿**:上面每条都在"信封形状/文件落地"这一层,而用户眼里的成功是
  **"我拖进去看到了缩略图、发出去模型答得上"**。缩略图渲染错位、按钮被输入卡挡住、
  4 张图把输入框顶出屏幕 —— 断言全绿也照样丢人。→ 接住它的只有**真截图**:
  1 张 / 4 张两种状态各截一张亲眼看(史料:07-24 `columnCount==="3"` 全绿而正文竖排)。
- **第二个假绿**:假 ws 服务端能证明"我按协议发了",但**不能**证明 nanobot 真收下。
  协议限额(4 张/8MB/svg)是我从源码抄的,抄错了就整条消息静默不发布。
  → 收尾必须对**真 gateway** 跑一次手工冒烟(发 1 张小图,看 mimo 是否描述得出),
  这条写进 verify 的 mechanical checks,不靠 e2e。
- **第三个假绿**:`already_exists` 用"不重建"断言,但我若拿 mtime 判,ext4 秒级精度
  可能让"重建了但同秒"也过 → 改用 **inode 号**(`st_ino`)判同一目录,而非 mtime。
