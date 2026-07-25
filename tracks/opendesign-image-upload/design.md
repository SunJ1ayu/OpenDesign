# Design: opendesign-image-upload

- Change: opendesign-image-upload
- Status: draft

> 非开放架构分叉(落点/链路都由现有 posture 唯一决定),不跑 panel-explore。
> 方案经 sub Claude 独立评审(`/root/aiwork/tasks/opendesign-round-plan-20260726.md`),
> 其 P0-1/P0-2/P0-3/P1-1/P1-3 五条我逐条核过代码属实,已并入下面的方向。

## Approach

**端点**:`POST /api/upload`,body 必须 `application/json`:

```json
{"name": "客厅现场.png", "data_url": "data:image/png;base64,…"}
```

**为什么不是 multipart(评审 P0-1,已核实)**:本仓所有写针孔的 CSRF 纵深只靠
"强制 `Content-Type: application/json` → 跨站 fetch 必触发 preflight → 本服务无
`do_OPTIONS` → 浏览器拦"(`ds_web.py:866-872`;`grep -c "def do_OPTIONS"` = 0)。
而 multipart/form-data 是 **simple content-type,不触发 preflight** —— 收 multipart
等于给这个"能往用户硬盘写字节"的新口开一个 CSRF 洞。base64 在前端本来就有(拖拽拿到
的 File 读成 data URL,聊天那单也要用同一形状),零额外成本。

**闸序**(逐条照抄现有针孔 posture,新增四条):

1. `Content-Type == application/json`(CSRF 纵深)
2. `0 < Content-Length <= UPLOAD_BODY_MAX`(**新常量 ~14MB**,不复用
   `OPEN_BODY_MAX=4096`;14MB ≈ 8MB 图 base64 膨胀 4/3 + 信封)
3. JSON 解析 → 必须是 dict → **键白名单 {name, data_url}**,多一个键就 400
4. 类型闸:两者都必须是 str
5. **名字闸 `_safe_upload_name(name)`(纯函数,表驱动 oracle)**:
   - 先 `os.path.basename` 剥掉任何目录成分(纵深;下面的正则也不放行分隔符)
   - 必须过 `ds_workspace.PROJECT_NAME_RE`(= `_SEG_RE`:禁 `/ \ % 控制符`,非 `.`/`..`)
     —— **复用而不是自研黑名单**:收件箱列举/指派/图墙扫描全用它过滤,
     不复用就会造出"落盘了但收件箱里看不见"的黑洞(评审 P0-2,已核实
     `ds_intake.py:177` 就是拿它过滤的)
   - 额外拒:含 `:`(NTFS 备用数据流面)、以 `.` 开头(收件箱列举会跳过 → 同样看不见)、
     尾部 `.` 或空格(Windows 会静默剥掉 → 名字对不上)、
     Windows 保留名(CON/PRN/AUX/NUL/COM1-9/LPT1-9,含带扩展名的形式)
   - 长度:去扩展名后截到 80 字符(Windows 260 全路径预算;不截的话炸点在
     `apply_plan` 移动那一步,用户看到的是"确认执行失败"而不是"名字太长")
6. 扩展名 ∈ `ds_workspace.IMG_EXTS`(png/jpg/jpeg/webp/gif;**svg 排除**=内嵌脚本面)。
   **不从 taxonomy 推导** —— 那是用户可改的数据配置,推导等于让 `taxonomy.json`
   变成安全配置。
7. data URL 头 `data:<mime>;base64,` 的 mime 必须与扩展名同族(`.png`↔`image/png`,
   `.jpg/.jpeg`↔`image/jpeg`,…)—— 防"名叫 .png、内容声明成别的"
8. base64 严格解码(`validate=True`),失败 400;解码后字节数 ≤ `UPLOAD_MAX_BYTES`(8MB)
9. 收件箱定位:`ds_intake._find_inbox`(候选名来自 taxonomy 四选一 + 用户可覆盖,
   自带 islink 拒绝 + within 闸)。**不硬编码 `00-收件箱`**(评审 P0-3,已核实
   `config/taxonomy.default.json` 有 4 个候选)。找不到 → 409 `inbox_not_found`
- 10. 落盘:先写 `.upload-<rand>.tmp`(点号开头 → 收件箱列举天然跳过,
   `ds_intake.py:177`),再 `os.replace` 到最终名;最终名用 `open(final,"xb")` 占位,
   撞名就 `名字 (2).png` 递增重试(**O_EXCL 而不是 exists 后写**,避免 TOCTOU;
   先例 `ds_organize.py:199` 用的就是 `"x"`)
- 11. 任何失败 → `finally` 删掉临时文件(`ENOSPC`/异常都不留半截:半截文件会被
   「扫描整理」当正常文件归档进项目夹)
- 12. 响应 `{"ok":true,"name":"<真正落盘的名字>","inbox":"<收件箱目录名>"}` ——
   **回显真实落盘名**,前端显示"已存为 xxx";名字被截断/改写时用户当场看得见

**前端**:**图墙整页**为投放区(dragover 高亮、drop 读 File → data URL → 调针孔)。
收件箱卡片**不做**投放区 —— 它在"空箱且无待确认"时整卡不渲染(InboxCard 的既有语义),
而"第一次拖图进来"恰恰就是空箱那一刻,拖无可拖。
上传成功后提示"已存进收件箱,点「扫描整理」归档" —— **引导指向卡片按钮,不是聊天**
(评审 P1-3,已核实:网页的 scan/approve 两条针孔自带 `allowed_roots=[cfg["root"]]`
(`ds_web.py:1075`/`:1119`),不看 `DS_ORGANIZE_ROOTS`;而聊天那条路吃那个白名单,
没配过的机器会回 `root_not_allowed`)。

## Key trade-offs / risks

- **只允许图片**:设计师也会想传 dwg/pdf。本单故意不做 —— 先把最窄的面跑通,
  扩类型是加一行白名单的事,但每加一类都要重想"读出面会不会被当 HTML 跑"。
- **8MB 上限**:手机直出照片常见 3-6MB,单反原图会超。超了给人话提示"图太大,
  先压一下或直接拷进文件夹",不做服务端压缩(压缩=改用户的原始素材,不可逆)。
- **不做魔数校验**(评审建议,我同意):Windows 上能否执行由扩展名决定,`.png` 伪装的
  exe 双击不会执行;读出面按扩展名发 Content-Type,浏览器不会把 `image/png` 当 HTML 跑。
  加魔数只会误杀真图(渐进 jpeg/带前缀 EXIF)。**但顺手补 `X-Content-Type-Options: nosniff`**
  (现在 `_send` 没有,一行的事)。
- **大小写重名**:Windows 上 `客厅.PNG` 与 `客厅.png` 是同一个文件,Linux 上是两个 →
  "传两次得到两个文件"的断言在开发机必绿、真机必红。判据只断"撞名不覆盖",
  真机差异进 UNTESTED。

## Alternatives considered

- **直接传到指定项目/类目**:少两步点击,但等于新开"网页可任意写工作区"的路,
  与 deploy-security 的暂存+人工确认相抵。否。
- **multipart 上传**:见上,打穿 CSRF 纵深。否。
- **上传后自动触发扫描整理**:省一次点击,但"自动"会让文件在用户没看的情况下移动,
  与整条链路"人工确认才动"的语义打架。否。

## Test strategy (oracle)

1. **`tests/test_ds_web_upload.py`(新增)**
   - `_safe_upload_name` **表驱动**:合法名通过;`%`、`:`、`/`、`\`、`..`、控制符、
     `.` 开头、尾点/尾空格、CON/NUL/COM1(含 `CON.png`)、超长名 → 各自拒或改写。
     **这些用例在 Linux 上跑的是"闸有没有拒",与平台无关 → 真绿。**
   - 端点:happy path 200 + **`GET /api/intake` 的 entries 里出现该文件**
     (⚠️ 判据不是 `os.listdir` —— 只断 listdir 就接不住 `%` 那类"落盘了但全链路看不见";
     这是本 oracle 最关键的一条)
   - 拒绝路径:CT 非 json / 超体积 / 多余键 / 非 str / svg / 扩展名不在白名单 /
     mime 与扩展名不符 / base64 非法 / 解码后超 8MB —— 每条都断 **零写盘**
     (收件箱目录文件数不变)
   - 撞名:同名传两次 → 第二次落 `名字 (2).png`,两个文件都在,**原文件字节不变**
   - 无收件箱:409 `inbox_not_found`,零写盘
   - 临时文件:失败路径后目录里没有 `.upload-*.tmp` 残留
2. **e2e 真 chromium(`tests/e2e/image_upload.e2e.mjs`)**:用 `DataTransfer` 真拖一张
   PNG 进图墙 → 收件箱卡片出现该文件 → 点「扫描整理」→ 出现方案 → 点「确认执行」→
   文件出现在目标类目下。**这条走完整条链,才叫"上传能用"**。
3. 回归:`pytest tests/`、`node --test tests/*.mjs`、`npm run build`、e2e 全套。

**这个 oracle 能被什么骗过?**

- **最危险的假绿:只断"文件落盘了"**。`%` 那个坑就是落盘成功但收件箱列举过滤掉 →
  用户永远看不见。所以主判据必须是"**在 /api/intake 里看得见**",而不是 listdir。
- **平台假绿**:冒号→ADS、保留名→设备、尾点被剥、大小写不敏感、260 长路径 ——
  这些在 Linux 上**闸拒了就绿**,但"Windows 上真会怎样"证明不了。
  → 全部列进 verify 的 UNTESTED,并在真机验收清单里让用户实际传一张中文名+空格的图。
- **e2e 假绿**:如果 e2e 只断"接口返回 200",那前端拖拽根本没接上也能绿 →
  必须断到"收件箱卡片里出现这个文件名"这一步(真 DOM)。
- **我的规格可能本身就错**:若设计师其实想"拖进去直接进当前项目的参考图",
  那这一单做完他会觉得多了两步。已在 proposal 记为翻译点,真机验收要问一句。
