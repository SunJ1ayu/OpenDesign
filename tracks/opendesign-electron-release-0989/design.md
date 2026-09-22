# Design: opendesign-electron-release-0989

## 出货包
electron-e2e 的 E1 先用补丁版 package.json(更新源 → 127.0.0.1:8900)打被测包 `dist-v1`;**同一个 job 紧接着** `git checkout -- package.json` 再打出货包 `dist-release`。
云上当场判:① `resources/app-update.yml` 的 url = `https://github.com/SunJ1ayu/OpenDesign/releases/latest/download`;
② `win-unpacked` 两份逐文件比哈希,只允许 `resources/app-update.yml` 与 `resources/app.asar` 不同;app.asar 不同时解开比,只允许 `package.json` 不同;
③ `release-feed.mjs verify` 出货清单与出货安装包字节一致。上传 artifact `release`(安装包 / blockmap / latest.yml)。

## 「所有用户」
electron-builder 选「所有用户」⇒ `SetShellVarContext all` ⇒ `$LOCALAPPDATA` = `C:\ProgramData`。模板自己用 LOCALAPPDATA 前后都切回 current
(`templates/nsis/include/installer.nsh` 注释 "electron always uses per user app data")。我们的 customInstall 照抄这个写法包住 provision。
云 E7(业主误点场景):旧版装在自选目录、开机自启开着 → 带界面装新版,「为哪位用户」点「所有用户」→ 记下装到哪、卸载项在哪;
判:旧版收干净、资料与配置原样、没有 `C:\ProgramData\OpenDesign`、软件起得来且版本一致、开机自启指新 exe。

## 发布
照 `installer/RELEASE.md`:verify → rewrite(安装包地址改成 `download/v0.98.9/` 绝对地址)→ verify → gh-command。tag 指向推送后的同一个提交。
