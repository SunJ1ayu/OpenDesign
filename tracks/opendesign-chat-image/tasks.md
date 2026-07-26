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

- [ ] T1.1 `/api/upload` 响应加 `path`(绝对落盘路径)
- [ ] T1.2 新写针孔⑭ `POST /api/inbox/create`(闸序见 design D3;只建一层固定名)
- [ ] T1.3 `GET /api/intake` 响应加 `path`(收件箱绝对路径,给卡片副标题)
- [ ] T1.4 VERSION → 0.49.0

## T2 前端 — 发图

- [ ] T2.1 `web/src/chat/media.ts`:`pickChatImages`(限额/类型/条数,纯函数)
- [ ] T2.2 `transcript.ts`:`messageEnvelope` 加可选 media(不带时信封逐字节不变)
- [ ] T2.3 `ChatPage.tsx`:`+` 按钮真接文件选择 + 拖拽 + 粘贴;缩略图条 + 单张可撤
- [ ] T2.4 发送时带 media;本地气泡显示缩略图

## T3 前端 — 归档与"东西去哪了"

- [ ] T3.1 气泡「存进收件箱」按钮(复用 `uploadToInbox`,成功回显绝对路径)
- [ ] T3.2 上传提示条改回显完整路径(图墙拖拽那条也一起改)
- [ ] T3.3 `inbox_not_found` → 「帮我建收件箱」按钮(调⑭ + 自动重试)
- [ ] T3.4 收件箱卡片标题副行 = 收件箱绝对路径

## T4 收货(主 agent 亲跑,执行腿自述一概不作数)

- [ ] T4.1 oracle byte-diff vs T0 commit(必须为空)
- [ ] T4.2 亲跑:`pytest tests/` + `node --test tests/*.mjs` + `npm run build` + 全部 e2e
- [ ] T4.3 **亲自截图看**:1 张图 / 4 张图两种输入卡状态 + 气泡按钮 + 提示条路径
- [ ] T4.4 **真 gateway 手工冒烟**:发 1 张小图,确认 mimo 描述得出(协议限额抄对了)
- [ ] T4.5 full 四审(panel-review)+ 主审先行 my-review
