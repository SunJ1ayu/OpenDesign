# Electron 版发布清单

版本号仍只增加第三位，且 `bin/ds_web.py` 与 `desktop/package.json` 必须保持一致。本清单不代替发布审批，也不自动推送或创建 release。

1. 在干净提交上触发 `electron-e2e`，所有 Linux 判据与云 Windows E1～E7 **全部**通过(FAIL 0)。出货包 artifact `release` 在 E7 之前就上传了 —— 只从整跑 FAIL 0 的那次运行取包。
2. 从 workflow artifact 取回以下三样资产：
   - `OpenDesign-<版本>-electron-setup.exe`
   - `OpenDesign-<版本>-electron-setup.exe.blockmap`
   - `latest.yml`
3. 先核安装包字节：
   ```sh
   node desktop/scripts/release-feed.mjs verify <latest.yml> <安装包.exe>
   ```
4. 把 feed 中的安装包地址改写到带版本的正式 release 路径，再复核一次：
   ```sh
   node desktop/scripts/release-feed.mjs rewrite <构建产物/latest.yml> <发布目录/latest.yml> <版本>
   node desktop/scripts/release-feed.mjs verify <发布目录/latest.yml> <安装包.exe>
   ```
5. 生成发布命令，由有发布权限的业主亲自执行：
   ```sh
   node desktop/scripts/release-feed.mjs gh-command <版本> <安装包.exe> <安装包.exe.blockmap> <发布目录/latest.yml>
   ```

生成的命令会创建 tag `v<版本>` 的正式 release（不是 prerelease），并且恰好上传安装包、`.blockmap` 与改写过的 `latest.yml` 三样资产。换壳首版两台机器错开一天手动安装；旧版安装包继续保留在发布页。
