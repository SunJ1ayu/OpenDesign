# Design: opendesign-intake-simplify

- Change: opendesign-intake-simplify
- Status: draft

> 不是开放架构分叉:#3 只有一个合理解(核心放宽 + 空值不写链接),#4 的方向由
> Windows 前台权规则唯一决定(尽力提升 + 可退化)。不跑 panel-explore。

## Approach

### #3 建档去掉业主名(`ds_tools.py` + `ChangesColumn.tsx`)

**核心(`create_project`)**:
1. 签名 `client: str = ""`(位置参数保留,默认空;所有既有调用点零改动)。
2. 必填闸 `if not project or not client` → **`if not project`**。
3. 骨架里的业主行改成"有名才写链接":
   `client_link = f"[[{client}]]" if client else ""`,模板 `- 业主: {client_link}`。
   —— 与 `_CLIENT_TEMPLATE` 里 `linked=(f"[[{linked}]]" if linked else "")` 同款,
   不发明第二套写法。**空业主写成 `- 业主: `(字段行在、值为空)**,不是 `[[]]`:
   后者会被 ds_lint 判 broken_link,等于新档案自带一条体检报错。
4. 业主 stub:`if client and not cerr and not os.path.exists(cpath)` —— 空业主不建 stub
   (`_resolve(ds_root,"clients","")` 本来也会 err,但显式短路更诚实,也省一次 IO)。
5. 返回值 `client` 字段照原样回传(空串),前端不消费它,不改契约形状。

**下游确认(读代码逐个核过,不改)**:
- `list_projects`:`_read_header_field(lines,"业主")` 拿到空串 → `_LINK_RE` 不匹配 →
  `client=""`,表里那一格空着。不炸。
- `ds_web` cockpit 速览:`_field(text,"业主")` 同理,空串。
- `ds_lint`:`broken_link` 只扫 `[[X]]`;不写链接 = 没有 X 可断。**这正是不写 `[[]]` 的原因。**
- `rename_project`:改的是 `[[项目名]]` 链接与映射,与业主字段空不空无关。
- MCP `create_project_tool`:`client: str = ""`,docstring 明说
  **"知道就填;不知道**别猜**,留空,之后 `update_client` 补"** —— 弱模型的默认行为
  是"编一个看起来合理的",docstring 必须显式堵这条(PKB 诚实性)。

**前端**:删掉业主名 `<input>` 与 `cpClient` 状态、按钮 disabled 去掉
`!cpClient.trim()`;`createProjectErrMsg("empty_name")` 从"项目名和业主名都要填"改成
"项目名要填。";项目名输入框接管 Enter 提交(原来 Enter 挂在业主名框上)。

### #4「打开文件夹」尽力置顶(`ds_web.py`)

Windows 不让后台进程抢前台(SetForegroundWindow 前台权规则),所以做成
**尽力而为 + 永不阻塞 + 失败静默退化**:

```
_default_open_launcher(path)            # 现状不变的三分支
  └─ os.name == "nt" → _open_windows(path)
       ├─ os.startfile(path)            # 先照旧开(这一步失败 = 整体失败,照旧抛)
       └─ _WIN_FOCUS(path)              # 模块级可注入的"提到前台",daemon 线程,不等
            └─ _win_focus_folder(path, enumerator, activator, attempts, delay)
                 ├─ enumerator() → [(hwnd, cls, title), ...]   # Windows-only glue
                 ├─ _pick_folder_window(windows, path) → hwnd | None   # 纯逻辑
                 └─ activator(hwnd)                            # Windows-only glue
```

- **窗口识别**(`_pick_folder_window`,纯函数):类名 ∈ `{CabinetWClass, ExploreWClass}`
  且标题命中目标文件夹名 —— 优先"标题 == basename"(Windows 默认标题就是文件夹名),
  退而"标题以 basename 结尾 / 含 basename"(用户开了"标题栏显示完整路径"时)。
  多个命中取**最后一个**(EnumWindows 的 z-order 是从上到下,最后一个 = 最近创建的那扇?
  ——不可靠,所以判据只断"命中集合里选一个且必须是命中的",不断"选哪个",见下)。
- **等窗口出现**:窗口是异步创建的,`attempts × delay`(默认 20 × 0.1s = 2s)轮询,
  一命中就动手;超时就放弃,**不抛异常**(置顶失败绝不能让"打开文件夹"这件事失败)。
- **不阻塞**:整个 focus 流程丢 `threading.Thread(daemon=True)`;HTTP 响应在
  `os.startfile` 返回后立刻回,`_open_folder` 的时序契约不变(ds_web 单线程,阻塞 2s
  = 整个界面卡 2s)。
- **激活动作**:`ShowWindow(hwnd, SW_SHOWNORMAL)` → `SwitchToThisWindow(hwnd, True)`
  → `SetForegroundWindow(hwnd)` 三连,任一成功即可见效;全被系统拒 = 任务栏闪
  (今天的行为),不倒退。
- `DS_OPEN_CMD` 注入分支与非 Windows 分支**一字不动**(e2e/测试照旧不真开窗口)。

## Key trade-offs / risks

- **置顶不能保证**:Windows 前台权规则可能拒绝全部三个调用。这是平台限制,不是
  实现瑕疵;真机若仍不置顶,退路是"点按钮后前端提示一句『已在任务栏打开』"而不是
  更暴力的抢焦点(抢焦点的脏招会被杀毒软件当行为异常)。
- **Windows-only glue 无法在 Linux 真验**:`ctypes.WINFUNCTYPE` 在 Linux 上根本不存在,
  所以枚举/激活两个 glue 函数只能靠"注入假 enumerator/activator"验决策逻辑,
  glue 自身 = **UNTESTED on target**,必须进 verify 的未验清单 + 真机验收。
- **空业主档案的可读性**:`- 业主: ` 空值会在 UI 上留一格空白。可接受(比逼人填假名好),
  且 `update_client` 可后补。**不做**"待补"占位文案 —— 那是编数据。
- 放宽必填后,**注入面**:client 仍先过 `sanitize_field`(折行),再判空;
  非法但非空的业主名(如 `李/四`)行为**保持现状**(项目建、stub 跳过、链接悬空),
  本单不改那条既有语义(test_h1 已锁)。

## Alternatives considered

- **#3 让前端传一个占位业主名(如"待补")**:一行改完,但那是**往 PKB 里写假数据**,
  之后没人分得清"待补"是真业主还是占位。否。
- **#3 把业主字段整行从骨架删掉**:更"干净",但 list_projects/cockpit/ds_lint/
  update_client 全都读这行,删了要动四处读侧 + 老档案与新档案两种形状并存。否。
- **#4 用 PowerShell COM(`Shell.Application.Explore` + `AppActivate`)**:同样受前台权
  限制,还多起一个 powershell 进程(~200ms+)且更难注入测试。否。
- **#4 先 `AllowSetForegroundWindow`**:该 API 只有**当前持前台权的进程**能调,
  ds_web 不持有 → 无效。否。
- **#4 让前端在浏览器里提示"已打开"**:不解决用户的诉求(他要窗口在前面),
  但保留为置顶被系统拒后的**退路**。

## Test strategy (oracle)

主 agent 亲写,先红检,先 commit。

1. **`tests/test_ds_tools.py`(核心)**
   - `create_project("项目", "")` → `ok`,且档案里**有** `- 业主:` 字段行、
     **不含** `[[]]`、`clients/` 下**零落盘**。
   - `create_project("", "")` → 仍 `empty_name`(项目名照旧必填)。
   - 空业主建出的档案:`append_change` 能接上(`## 变更记录` 头在)、
     `list_projects` 返回该项目且 `client == ""`(不炸不漏)。
   - `ds_lint.check` 对空业主项目**零 broken_link**(这条是 `[[]]` 陷阱的判据)。
   - 既有 `test_c10_empty_name` 的"业主空 → empty_name"那一句 = **过时考卷**,
     按新规格改写(主 agent 亲手改,verify 里逐条说明)。
2. **`tests/test_ds_web_api.py`(端点)**
   - `POST /api/projects/create {"project":"X"}`(不带 client)→ 200 ok。
   - `{"project":"X","client":""}` → 200 ok(原来这里断 `empty_name` = 过时考卷)。
   - `{"project":""}` → 400 `bad request`(读门 `_valid_proj_key` 先拦,不变)。
   - 键白名单/CT/体积三闸行为**一字不变**(回归)。
3. **`tests/test_ds_web_open_front.py`(新增,#4 的纯逻辑判据)**
   - `_pick_folder_window`:类名不对 → None;类名对但标题不含目标名 → None;
     标题 == basename → 命中;标题 = `C:\...\<basename>`(完整路径模式)→ 命中;
     多窗口混杂 → 返回的 hwnd **必须来自命中集合**。
   - `_win_focus_folder`:①窗口第 3 次轮询才出现 → 仍命中且 activator 只调一次;
     ②始终不出现 → 返回 False、**不抛**、activator 零调用;③enumerator 抛异常 →
     吞掉返回 False(置顶失败不能连带"打开"失败)。
   - `_open_windows`:先 `os.startfile`(monkeypatch,`raising=False`)再触发 `_WIN_FOCUS`;
     `os.startfile` 抛 → 异常照旧向上(打开本身失败要让前端看见)、`_WIN_FOCUS` 不被调用。
   - `_spawn_win_focus` **不阻塞**:注入一个 sleep 0.5s 的假 focus,调用点必须在
     ≪0.5s 内返回(判据取 <0.2s),且线程是 daemon。
4. **`tests/e2e/intake.e2e.mjs`(真 chromium,#3 的用户面判据)**
   - 未建档文件夹的建档表单:**只有一个输入框**、页面上**不出现"业主名"**字样;
     只填项目名 → 建档按钮可点 → 建档成功(列表里该项目不再是"未建档")。
   - 项目名框里按 Enter 直接提交(原来 Enter 挂在业主名框)。
5. 回归:`node --test tests/*.mjs`、`python -m pytest tests/`、`npm run build`、
   真 chromium e2e 全套。

**这个 oracle 能被什么骗过?**

- **#4 最危险,且骗术就在明面上**:上面所有断言都是"我的假 user32 被正确调用了",
  **没有一条能证明真 Windows 会把窗口提到前面**。前台权规则、杀毒软件拦、
  Explorer 复用已有窗口(标题命中但那扇窗不是刚开的)——三种失败模式全在断言之外。
  接得住的只有**用户在真机上点一次**。所以本单的完成定义里,#4 只能算"已实现、待真机确认",
  verify 必须写明 UNTESTED on target,绝不能因为 pytest 全绿就报"置顶做好了"。
  (同一坑史料:0.34 那批"版本号回显"——盘上是新的、跑的是旧的,只有真机接得住。)
- **#3 的假绿**:e2e 若只断"页面没有『业主名』字样",那把整个建档表单删了也能绿。
  所以判据必须是**建档真的成功**(建完那个项目不再 unregistered),而不是文案消失。
- **#3 的另一半假绿**:pytest 若只断 `ok`,写出 `- 业主: [[]]` 也照样 ok。
  所以必须直接断档案正文**不含 `[[]]`** + `ds_lint` 零 broken_link。
- **空业主档案的下游**:list_projects / cockpit / 待办 / ds_lint 四个读侧我只在
  oracle 里覆盖了前两个 + lint;cockpit 那格空白长什么样,**截图看一眼**再说完成。
