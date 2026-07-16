# Design: opendesign-bind-project

- Change: opendesign-bind-project
- Status: final(封闭修复,模式=set_workspace 先例,无开放分叉)

## Approach

`bind_project(project: str, folder: str, ds_root) -> dict`

写侧四闸,全部复用既有单一真相源:
1. **project 必须是已建档项目**:`_resolve(ds_root, "projects", project)`(within+
   PROJECT_NAME_RE,H1 咽喉)+ 文件存在 → 否则 project_not_found / bad_name /
   path_escape。绑不存在的档案=白写,助手打错字必须被拦。
2. **workspace 必须已配置**:`ds_workspace.load_config` None → workspace_not_configured。
3. **folder 只认已发现的文件夹 key**(`project_folders(cfg)` 精确匹配,含 depth2
   的 `组:名`)→ 否则 folder_not_found。不收任意 rel 路径:已发现 = 已过两级
   PROJECT_NAME_RE + no-symlink + realpath,复用其保证,不开第二条解析面。
4. **写**:读原 JSON(整 dict 原样保留,只动 projects[project]=rel),rel =
   relpath(folder realpath, root) 用 "/" 分隔;原子写(tmp+os.replace)提取
   `_write_workspace_json` 公共 helper,set_workspace 改用同一只——不复制第二份。

重绑=覆盖(显式映射本就是纠偏机制)。返回 {ok, project, folder, rel}。
生效:workspace.json 每请求现读,聊完 turn_end 的 dataEpoch 刷新(M5)自动合并
列表,零前端改动。

配套:AGENTS.md 工具行+触发话术(用户说"这文件夹就是 X"/看到重复条目);
CompanionColumn「此项目还没关联文件夹」文案 改 JSON→改对话(断层#4 的文案半);
VERSION 0.16.0。

## Key trade-offs / risks

- folder 只认发现 key:代价=没被扫出的文件夹(字符集被拒/深度不符)不能绑。
  正确取舍——列不出的文件夹绑上了 web 侧也寻址不到(列出=可寻址的既有不变量)。
- 两个 PKB key 绑同一文件夹:允许(显式映射人工驱动,消费集 realpath 去重无恙),
  不加唯一性约束(过度工程)。
- 写侧动 workspace.json 与 set_workspace 并发:同为整读整写原子替换,末写者胜,
  单用户桌面场景可接受(与 set_workspace 既有语义一致)。

## Test strategy (oracle)

BindProjectOracle(test_ds_tools):happy(映射落盘+project_dir 即解析)/重绑覆盖/
project 不存在/坏字符/未配置/folder 非发现 key(均不落盘)/depth2 keyed folder
→ rel 带组/原子无 .tmp/其余字段与映射原样保留。red-check:注释 folder 成员闸→
folder_not_found 用例红;注释项目存在闸→project_not_found 用例红。
py 全量回归 + build 绿(前端仅文案)。verify lane=**full panel**(新写面,
Track B 先例;subsense/subglm 缺席则记录)。
