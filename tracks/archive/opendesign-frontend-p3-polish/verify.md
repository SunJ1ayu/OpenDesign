# Verify: opendesign-frontend-p3-polish

- Date: 2026-07-20 ~ 2026-07-21
- Verdict: **PASS**(主裁:主 agent)

## Mechanical checks

全部由主 agent 亲跑(执行腿自述一概不作数):

- [x] build passes —— `npm run build` 绿,重跑复现同哈希(`index-Cpl5N_59.js` /
      `index-KyV1pg4C.css`),盘上 dist == 源码当前态
- [x] tests pass
  - oracle 三份:`test_ds_web_open` 14/14、`test_project_name` 20/20、
    `tests/e2e/frontend_p3_polish.e2e.mjs` ALL PASS
  - 回归:19 个 py 套件全绿(含 `test_ds_workspace` 46)、`tests/*.mjs` 10 个全绿
    (pass 129 / fail 0)
  - 相邻 e2e:`frontend_p1` / `frontend_p2_polish` / `cockpit` / `intake` 全 PASS
  - 真 gateway e2e:`project-thread` 7 steps ALL PASS(见「已知抖动」)
- [x] no secrets / unsafe ops —— 无新增依赖;执行腿未 push/merge/归档;
      e2e 用的 `~/.nanobot/config.json` 已还原并**逐字段比对一致**
- [x] 部署点回显(AGENTS.md「Verify at the point of use」):
      `GET /api/health` → `{"ok": true, "version": "0.32.0", ...}`

## 收货三硬闸(T4)

- **闸① oracle byte-diff**:执行腿的三个 commit(`2cc85dc` T1 / `136b58c` T2 /
  `4d01f48` T3)对 T0 oracle commit `316580a` **零 tests/ 改动** —— 逐字节干净。
  之后的 oracle 改动均为**主 agent 在收货修复轮自己所写**,且都是**收紧**:
  - `37d8dcf`:I1 夹具补第二个顶层类目 + 断言「子文件夹不得出现在来源里」
    (把执行腿被我的坏夹具逼出来的错误语义钉成回归用例)
  - `f2180db`:补嵌套 rel 三处断言(见 subkimi M1)
  - `4a8ffd2`:注释/黑名单纯度补强(见 submimo nit)
- **闸② 亲跑**:见上 Mechanical checks,全部本机实跑。
- **闸③ 亲读 diff**:逐行读完,I4 安全面逐行核。抓到 2 处并已修(主-1/主-2)。

## Review

- lane: **full 四审**(I4 = 只读墙上的新开口 = 安全面,不打折;07-18 教训)
- 轮次:
  - 轮 a(`/root/aiwork/logs/panel-p3polish-20260720.*`):submimo PASS、
    subdeepseek PASS;subglm / subkimi 首发失败(见 `.err`)
  - 轮 b(`panel-p3polish-20260720b.*`):subglm PASS、**subkimi BLOCK**
  - 修复轮②后补一腿 fast 复核:submimo **PASS**(`p3-fixround2.submimo.log`,
    五条审查点逐条通过,含「能列出=能寻址」不变量独立复核)

### findings(主 agent 先落,再读评审)

主审自己抓到的(评审腿均漏):

- **主-1(真,已修 `37d8dcf`)** I1「来源」语义被改成相册粒度(子文件夹),
  而仓里 `gallery.ts` 对「来源」的定义是**顶层类目**。根因是**我的 e2e 夹具只造了一个
  顶层类目却断言 ≥3 项**,把执行腿往更细粒度上逼 —— 修夹具与语义,不是修实现。
  过程教训:第一次复跑 e2e 时只改源码没重建 dist,打在旧 bundle 上(「盘上的新文件
  ≠ 跑着的目标」又踩一次)。
- **主-2(真,已修)** 收货时 dist 未随修复重建 —— 已重建并复验哈希可复现。

评审腿抓到、主审漏的(本 panel 的核心价值):

- **subkimi M1(BLOCK,成立,已修 `f2180db`)** `overview.recent` 只回
  `name`+`category`,前端拼 `${category}/${name}` 去开文件:嵌套文件
  (`06-效果图/定稿/客厅.png`)必然拼错 → Gate D isfile 404「点了没反应」;
  同名不同子目录(定稿/初稿 各一张 `客厅.png`)会**静默开错文件**。
  e2e 夹具自己就造了两层子目录 —— 是设计师的常态布局。
  **主审 + 另外三腿全漏,三份 oracle 也一起漏 = 规格自身错,不是实现走样**
  (再次实证「oracle 是主 agent 写的、可能本身就错」)。
  修:后端把扫描时本就持有的完整 `rel` 透出到 recent(`_scan` 每段都过 `_SEG_RE`,
  故 rel 恒满足 `relpath_ok`,「能列出 = 能寻址」不变量不破),前端直接用,不再拼。
- **subkimi #2(Medium,成立,已修 `f2180db`)** I3 把伴随列 290→400、助手列
  340→300 后,`.workspace` 的 `min-width` 仍是 1150,窄窗下中央列(命根子·变更记录)
  被挤到 ~210px。改 1260 = 240+400+300 固定列 + 320 中央列地板。
- **submimo 两条 nit(收,`4a8ffd2`)**:①`test_ds_web_open.py` 头注释写闸序
  A→B→C→D,实现是 A→B→D→C —— 修注释并写明 **D 先于 C 是有意的**(只有确定是真文件
  才谈得上「扩展名被拒」415,否则目录会拿到自相矛盾的 415;安全性与顺序无关,两闸
  都必须过才调 launcher);②mjs 白名单纯度测试的 forbidden 列表补 Windows 特有可执行
  载体 `.hta .chm .wsh .msc .cpl .inf .vbe .pif .gadget`。

拒的(附证伪依据):

- submimo「I3 列宽容差 ±2px 偏紧」—— 拒:列宽是固定 px 非响应式计算,实跑
  400/300 精确命中;放宽容差等于放弃这条断言的意义。
- subdeepseek「py oracle `BAD_EXT_FILES` 只有 9 个扩展名,建议扩充」—— 部分拒:
  白名单机制**不依赖**黑名单枚举(默认拒),黑名单只是回归灵敏度;已在成本更低的
  mjs 纯度测试里扩到 33 项,后端不重复堆同一集合。
- subdeepseek/submimo 关于 I6 括号启发式误伤(`(Before) xxx` 会丢前缀)—— 拒:
  设计上接受的取舍,`title` 兜全名,修改单原文即如此要求。

### arbitrated verdict(主裁)

**PASS**。I4 这道新开口的安全性我逐行核过并独立认可:Gate A 复用 `relpath_ok`
单一真相源(禁 `..`/`\`/`%`/控制符),Gate B `realpath` + `within` 是逃逸权威闸
(符号链接指夹外 → realpath 后 within 拒;夹内符号链接指向 `.bat` → realpath 后
扩展名闸拒,方向正确),Gate D 早于 Gate C 属有意,白名单内**零可执行/脚本/快捷方式**,
任何拒绝路径 `OPEN_LAUNCHER` 调用数为 0(oracle 断言)。CSRF 姿态沿用 p5 既有硬化
(强制 `Content-Type: application/json` → 跨站必 preflight,本服务无 OPTIONS 面)。

一致 PASS 没有降低我自己的判据:本单里三腿 PASS 而 subkimi 单腿 BLOCK 且**成立**,
正是「共享假阴性是 panel 也接不住的失败模式」的现场证据。

## Accepted deviations

- **I5 不在 e2e 里**:助手头部只在已连接态渲染,无 gateway 的 e2e 覆盖不到。
  改以**真 gateway 手工核验 8 点**替代并全过(头部 10.5px 降噪 /「退出登录」不再常驻 /
  `…` 按钮存在 / 菜单含退出登录 / esc 关 / 外点关 / 菜单里登出真的登出)。
  核验脚本是一次性的,未入仓 —— I5 后续再改就补进 `project-thread` 那条真 gateway 线。
- **白名单外文件退化为开「类目」文件夹**,不下钻到它所在的子目录
  (`03-CAD/旧版/跑批.bat` → 开 `03-CAD`)。理由:退化路径本就是「给个去处」而非精确
  定位,沿用既有 `sub` 单段闸可不碰第二条路径闸。已钉成 oracle 用例。
- **纯样式项(颜色/圆角/两行截断的视觉)不做自动断言**,归闸③亲读 diff + 用户真机验收。
- **`project-thread` e2e 有已知抖动**:首跑挂在「B 项目映射独立于 A」(切项目后
  localStorage 映射是连接后异步写入,断言紧跟 `.chat-meta` 出现),复跑 ALL PASS。
  与本 track 的 diff 无关(`.chat-meta` 渲染时机未变),记为既有 e2e 债,不在本单修。
- 真 gateway e2e 需要 gitignored 的样例数据(`projects/*.md` 等),本次从主仓临时拷入
  worktree,跑完即删;worktree 现状干净。
