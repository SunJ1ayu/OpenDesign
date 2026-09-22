# 发版单云端两路(预期**写在看结果之前**,09-22 23:5x;文件名的日期按 UTC 次日误写,内容时间以此为准)

| 分支 | 内容 | run | 预期 |
|---|---|---|---|
| ci-electron/rel-red | `2f9dcd7` 判据(E7 + 点击量具 -Pick),产品未修、workflow 未加 E1r | 35750376646 | **`E7.nopd` 红**(provision 在「所有用户」上下文下写进 C:\ProgramData\OpenDesign);E7 其余(点选 / 过渡 / 资料 / 起得来 / 自启)OK;前面各段与 fix2 同样 OK |
| ci-electron/rel-fix | 修 customInstall 上下文 + workflow 加 E1r 与 artifact `release` | 35750584881 | **FAIL 0**;E1r 各条 OK(更新源 = GitHub、逐文件只差更新源、清单字节一致);artifact `release` 有三样 |

判读:
- rel-red 的 `E7.pick` 若红(「所有用户」没点上 / 要提权卡住)⇒ E7 没问到它该问的,**不许拿 rel-fix 的绿放行**,先修量具或如实告诉业主「这条测不了」。
- rel-red 的 `E7.nopd` 若意外绿 ⇒ 我对 NSIS `$LOCALAPPDATA` 的读法错了(或模板别处已切回 current),先查清再说修没修到。
- rel-fix 任何一条红 ⇒ 先分型(量具 / 产品),不许先怀疑判据。

## 结果(09-23 00:1x 读)—— 两路都照预期

- **rel-red 35750376646 FAIL 1 = `E7.nopd`**:`C:\ProgramData\OpenDesign` 下真写进了 `UserData\.nanobot\config.json` 与 **`UserData\.openDesign\登录口令.txt`**
  (全机可读的位置 ⇒ 这条 bug 另有一层:口令放到了公共目录)。E7 其余全 OK:点选生效、装到 `C:\Program Files\OpenDesign`、卸载项在 HKLM(`/allusers`)、旧版收干净、资料配置不动、软件起得来(用的是当前用户下原有的配置)。
- **rel-fix 35750584881 FAIL 0(137 OK)**:E1r —— 出货版更新源 `https://github.com/SunJ1ayu/OpenDesign/releases/latest/download`;两份各 9850 个文件,**只有 `resources\app-update.yml` 不同**(app.asar 一字不差);
  出货清单与出货安装包逐字节一致。E7 全 OK(`E7.nopd` 转绿)。选「所有用户」时没有弹提权卡住(runner 是管理员)。
- 要告诉业主的事实(E7 记下的):误点「所有用户」⇒ 软件搬到 `C:\Program Files\OpenDesign`、「应用和功能」里记在所有用户下;修复后资料与配置仍在他自己的用户目录、软件照常用。
