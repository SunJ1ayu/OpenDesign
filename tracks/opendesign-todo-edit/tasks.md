# Tasks: opendesign-todo-edit

- base-ref: 0c8b6dd803d76b655337bd5b9db932550cfeff63

> 先红后绿:每条先写失败 oracle 再窄实现转绿。主 agent 拥有 oracle。
> v2 采纳 sub-Claude 评审:独立 `## 变更历史` 段(消 BLOCK-1)+ 保前缀字节(BLOCK-2)+
> cnum 键隔离(BLOCK-3)+ 不 ban 竖线(NIT)。

- [ ] T1 后端 edit_change 核心(ds_tools):按 cnum 定位主变更行;改状态(复用 set_change_status
      口径);改正文=前缀捕获正则只替尾段(BLOCK-2 前缀字节不变)+ 向 `## 变更历史` 段写
      `- C{n} 改于{today}｜原:<旧>`(段缺则建,置于变更记录段后);加/改备注=按 cnum 键
      追加/替换 `- C{n} 备注:<内容>`;sanitize 折换行不 ban 竖线;全程 locked_rw。
      oracle:design test 1–5、10、11。
- [ ] T2 不干扰既有写/读路径(回归锁):append_change 对含 `## 变更历史` 段的项目逐字节不变
      (BLOCK-1 反向锁,test 8);set_change_status 不动历史段(test 9);collect/parse_change
      对含历史段的 .md 待办数不变(test 6);多变更 cnum 隔离(BLOCK-3,test 7)。
- [ ] T3 ds_web 读端点扩展:/api/projects/<key>/changes 解析 `## 变更记录`+`## 变更历史`
      按 cnum join,回 {…, note?, history:[]}。oracle:端点带回历史/备注 + 隔离。
- [ ] T4 ds_web 写针孔:POST `/api/changes/edit` 精确匹配 + CT json 闸 + body 键白名单 → edit_change;
      Host 闸继承;其余未白名单 POST 仍 405。oracle:design test 12(CT/超限/缺cnum/精确匹配/405 不变量)。
- [ ] T5 真 ds_web roundtrip(test 13):起真服务器 POST 编辑 → GET changes/todos 见新值+历史。
- [ ] T6 前端 TodoPage:行内改状态/改正文/加备注 + "改过·看原文" + 成功 bump dataEpoch;
      todo.ts 纯函数(编辑态/请求装配)mjs oracle(test 14);dist 重建。
- [ ] T7 agent 契约:workspace/AGENTS.md + 相关 SKILL 说明 `## 变更历史` 段语义(read_project 当上下文;
      不手写、经工具改);不改 append/set_status 行为。
- [ ] T8 收口:全套件 py+mjs 绿;VERSION bump;verify full lane 三审(写+数据一致性触发)。
