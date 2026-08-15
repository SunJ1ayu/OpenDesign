# Design: opendesign-data-outside-install

- Change: opendesign-data-outside-install
- Status: draft(A 卷 = 我的方向,落盘于读任何第二意见之前)

- 规划双出: **要做**(待跑)。触发条件命中:这是**写面语义的改动**(所有数据写口换落点),
  且 verify 那边会填 `lane: full`,且这单我自己干。
  做法:本文件先落盘 → 让 `gpt-5.6-sol` 对**同一份需求**独立出一版(明令不许读本 track 工件)
  → 对差异。抓的是"我以为理所当然"的地方。

## Approach

### 一句话

**安装目录在运行时是只读的。** 业主的东西一律落在**数据根**下,数据根默认等于 `ds_root`
(现有安装零变化),Windows 包把它指到 `%LOCALAPPDATA%\OpenDesign\UserData`。

### 1. 数据根怎么解析(唯一真相源)

`bin/ds_common.py` 加一个函数,全仓只有它一处决定这件事:

```python
def data_root(ds_root: str) -> str:
    """业主的东西落在哪。默认 = ds_root(git-pull 安装保持原样);
    Windows 包由外壳设 DS_DATA 指到安装目录之外。"""
```

- 默认值 = `ds_root` ⇒ **本机开发仓、公司机、家里机全部零变化**,1136 条判据不用改题面。
- Windows 包:`ds_shell_core` 造子进程环境时加 `DS_DATA=<UserData>`,
  与已经在传的 `DS_ROOT` 并列(三个 MCP + ds-web 都吃这份 env)。
- **为什么不是"把 ds_root 整个挪出去"**:`ds_root` 里装的是**代码**(bin/web/assets/
  workspace 契约),更新时要整棵换掉;数据必须活过那次换。两者混在一个根下正是本单要拆的。

### 2. 哪些东西跟着搬(读写口清单)

| 名字 | 现在 | 之后 |
|---|---|---|
| `projects/`(含 `.trash`) | `ds_root/` | `data_root/` |
| `clients/` | `ds_root/` | `data_root/` |
| `index.md` | `ds_root/` | `data_root/` |
| `refs/` + `refs-index.md` + `refs-vocab.md` | `ds_root/` | `data_root/` |
| `organize/`(plans、audit.log、.apply.lock) | `ds_root/` | `data_root/` |
| `config/workspace.json`、consent、user taxonomy | `ds_root/config/` | `data_root/config/` |
| `bin/ web/ assets/ workspace/ 版本号.txt` `config/nanobot.config.windows.jsonc` | `ds_root/` | **不动(代码)** |

⚠️ `config/` 是**混的**:模板是代码、workspace.json 与 consent 是数据 ⇒ 按文件分,不按目录分。

### 3. 那道拦截(业主追问逼出来的)

`set_workspace` / `bind_project` 的根:**不许落在安装目录里面,也不许落在数据根里面**。
理由是"删得掉的地方不能放他的原件"。拒绝时说人话并把路径念给他听。
—— 现在只校验"绝对路径 + 目录存在"(`ds_tools.py:905-913`),这道拦截**从来没有过**。

### 4. 文案跟着改

卸载确认页那句、可选框的描述,改成与实现一致(现在写的是假话)。

## Key trade-offs / risks

- **`DS_DATA` 没设 = 老行为**:这是最大的安全垫(现有两台机器不受影响),
  也是最大的坑 —— **Windows 包忘了设 env,就静默退回把数据写进安装目录**,
  而且一切看起来正常。⇒ 判据必须有一条专门问"包里那条 env 真的传到了三个 MCP 与 ds-web"。
- 一次性改 ~25 个调用点,漏一个就是"大部分搬了、有一个还在老地方",
  而那一个照样会被卸载删掉。⇒ **不能靠人眼数**,见下面的 oracle。
- 不做迁移:如果将来有人在 Windows 包里已经产生过档案,升级后会"看起来数据没了"
  (其实还在老目录)。本单业主机器上不存在这种情况,**但这条要写进真机清单让他确认**。

## Alternatives considered

- **让卸载器"跳过"那几个子目录**:白名单藏在一棵正被 `RMDir /r` 删的树里,
  且更新换整棵树时照样丢。治标,否。
- **软链接/junction 把数据目录接进安装树**:Windows 上要权限、备份工具语义混乱,
  且 `RMDir /r` 对 junction 的行为是我在 Linux 上验不了的那一类。否。
- **把 `ds_root` 整个搬到 LOCALAPPDATA、安装目录只放启动器**:更新时要替换代码,
  等于把"可换的"和"不可换的"继续绑在一起,问题原样还在。否。

## Test strategy (oracle)

主 agent 写,不外包。三层:

1. **不变量闸(本单最重的一条,动态)**:设 `DS_DATA=<临时目录>`,
   把**所有写口**跑一遍(建项目 / 写档案 / 加参考图 / set_workspace / bind_project /
   整理计划落盘与执行 / consent 落盘),然后断言:**`ds_root` 那棵树前后哈希一致**
   (逐文件 sha256,忽略 `__pycache__`)。
   - 这比"列一份数据清单"强在:**它不需要我列全** —— 将来谁再加一种数据文件,
     只要写进安装目录就当场红。我这次栽的正是"我把位置做成了闸、没把清单做成闸"。
2. **env 真的传到了**(防上面那个坑):断言外壳造出来的子进程环境里
   `DS_DATA` 存在且指向 UserData —— 三个 MCP 与 ds-web 四份 env 都要问到。
3. **拦截闸**:`set_workspace` 给安装目录里/数据根里的路径 ⇒ 拒绝 + 人话 + 不落盘;
   给正常路径 ⇒ 照常成功(**双向验**,别造一个"永远拒绝"的闸)。
4. **老行为零变化**:不设 `DS_DATA` 时,现有 1136 条判据 + 36 条 e2e 全绿。

**这个 oracle 能被什么骗过?**

- **骗法一:写口没跑到。** 闸①是"跑一遍写口再比哈希",如果某个写口我没在判据里调用,
  它就永远不会暴露。⇒ 写口清单必须**从代码里机械抽**(grep 出所有 `join(ds_root, …)`
  的数据名),不是我凭记忆列。**这条是本 oracle 最脆的地方,先写在这儿。**
- **骗法二:哈希比的是空树。** 如果测试里 `ds_root` 用的是个空的临时目录,
  "前后一致"毫无意义 ⇒ 必须拿**真的仓库树**(或至少含 projects/refs/config 的仿真树)当基线,
  且断言基线**非空**。
- **骗法三:`DS_DATA` 在测试进程里被别的判据串味**(08-15 刚栽过一次同款:
  模块级改 `os.environ` 把另一份判据整块变成 SKIP)⇒ 设/还原都在 setUp/tearDown 里。
- **骗法四:闸②问的是我自己造的 env,不是真的那份。** 必须调 `ds_shell_core` 真的那个
  造环境函数,而不是在判据里重写一遍期望(同 08-14「两张考卷对同一前提做了相反假设」)。
- **它问不出的**:Windows 上 `RMDir /r` 到底删了什么 —— 那只有业主真机能答,
  已写进真机清单(装 → 建一个项目 → 卸载 → 档案还在不在)。
