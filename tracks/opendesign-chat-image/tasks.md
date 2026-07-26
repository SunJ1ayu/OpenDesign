# Tasks: opendesign-chat-image

- base-ref: c1e4a8bc6528ecb616606abcc3cfde615e3a6399

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## T0 oracle 先行(主 agent 亲写,先红检,先 commit)

- [x] T0.1 `tests/test_ds_web_inbox_create.py` — 针孔⑭ 判据 c01–c10(design §oracle 1)
- [x] T0.2 `tests/test_ds_web_upload.py` 追加 `path` 判据 u19–u20
- [x] T0.3 `tests/test_chat_media.mjs` — 信封 + `pickChatImages` 纯逻辑
- [x] T0.4 `tests/e2e/chat_image.e2e.mjs` — 真 chromium + 真 ds_web,ws/bootstrap 走
      页面内 stub(自建假 gateway 占 8765 的做法已试并弃:浏览器侧端口写死,开发机
      常年有真 gateway 在跑 → 端口冲突)
- [x] T0.5 红检:全部先红 —— py 13/13 红(端点不存在)+ u19/u20 红(无 path 字段)
      + mjs 整文件红(media.ts 不存在)+ e2e 红(`[data-ui="inbox-create"]` 找不到)。
      **夹具自检另跑过**(scratchpad 探针):stub ws/bootstrap 能把 ChatPage 带到已连接、
      能截到信封、假回复能渲染 → 排除"红检其实是夹具坏了"。

## T1 服务端(bin/ds_web.py)

- [x] T1.1 `/api/upload` 响应加 `path`(绝对落盘路径)
- [x] T1.2 新写针孔⑭ `POST /api/inbox/create`(闸序见 design D3;只建一层固定名)
- [x] T1.3 `GET /api/intake` 响应加 `path`(收件箱绝对路径,给卡片副标题)
- [x] T1.4 VERSION → 0.49.0

## T2 前端 — 发图

- [x] T2.1 `web/src/chat/media.ts`:`pickChatImages`(限额/类型/条数,纯函数)
- [x] T2.2 `transcript.ts`:`messageEnvelope` 加可选 media(不带时信封逐字节不变)
- [x] T2.3 `ChatPage.tsx`:`+` 按钮真接文件选择 + 拖拽 + 粘贴;缩略图条 + 单张可撤
- [x] T2.4 发送时带 media;本地气泡显示缩略图

## T3 前端 — 归档与"东西去哪了"

- [x] T3.1 气泡「存进收件箱」按钮(复用 `uploadToInbox`,成功回显绝对路径)
- [x] T3.2 上传提示条改回显完整路径(图墙拖拽那条也一起改)
- [x] T3.3 `inbox_not_found` → 「帮我建收件箱」按钮(调⑭;建成后刷新即回正常态,
      **没做"自动重试上传"** —— 建收件箱与上传是两个动作,串起来会让人搞不清刚才
      到底发生了什么;卡片切正常态本身就是回执)
- [x] T3.4 收件箱卡片标题副行 = 收件箱绝对路径

## T4 收货(主 agent 亲跑,执行腿自述一概不作数)

- [x] T4.1 oracle byte-diff vs T0 commit:**本单实现由主 agent 亲自写(未派执行腿)**,
      故无"改考卷"风险面;唯一改过的 oracle 文件是 `chat_image.e2e.mjs`,改动是
      **我自己红检时发现的路由错**(收件箱卡片只在工作区路由),已在 verify 记明
- [x] T4.2 亲跑:`pytest tests/` + `node --test tests/*.mjs` + `npm run build` + 全部 e2e
- [x] T4.3 **亲自截图看**:1 张图 / 4 张图两种输入卡状态 + 气泡按钮 + 提示条路径
- [x] T4.4 **真 gateway 手工冒烟**:发 1 张小图,确认 mimo 描述得出(协议限额抄对了)
- [x] T4.5 full 四审(panel-review)+ 主审先行 my-review → **修复轮 6 改**
      (mime 单位对齐 / 上游错误转达 / 连点两次不撒谎 / Win 保留名 / 建成确认 / 提示指向按钮)
      + 判据 c14–c18、m19–m28 与 e2e 一条;仲裁全文见 verify.md
- [x] T4.6 修复轮后亲跑:pytest 660、mjs 228、build 绿、6 条关键 e2e 全绿;
      真 gateway 二次冒烟(只发图不写字 / 发 5 张)把两个"上游未知"打成已知
