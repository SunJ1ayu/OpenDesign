# 发版单云端两路(预期**写在看结果之前**,00:25)

| 分支 | 内容 | run | 预期 |
|---|---|---|---|
| ci-electron/rel-red | `2f9dcd7` 判据(E7 + 点击量具 -Pick),产品未修、workflow 未加 E1r | 35750376646 | **`E7.nopd` 红**(provision 在「所有用户」上下文下写进 C:\ProgramData\OpenDesign);E7 其余(点选 / 过渡 / 资料 / 起得来 / 自启)OK;前面各段与 fix2 同样 OK |
| ci-electron/rel-fix | 修 customInstall 上下文 + workflow 加 E1r 与 artifact `release` | (下一行填) | **FAIL 0**;E1r 各条 OK(更新源 = GitHub、逐文件只差更新源、清单字节一致);artifact `release` 有三样 |

判读:
- rel-red 的 `E7.pick` 若红(「所有用户」没点上 / 要提权卡住)⇒ E7 没问到它该问的,**不许拿 rel-fix 的绿放行**,先修量具或如实告诉业主「这条测不了」。
- rel-red 的 `E7.nopd` 若意外绿 ⇒ 我对 NSIS `$LOCALAPPDATA` 的读法错了(或模板别处已切回 current),先查清再说修没修到。
- rel-fix 任何一条红 ⇒ 先分型(量具 / 产品),不许先怀疑判据。
