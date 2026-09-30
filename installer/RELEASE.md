# Electron 版发布清单

版本号仍只增加第三位，且 `bin/ds_web.py` 与 `desktop/package.json` 必须保持一致。发版由 `.github/workflows/release.yml` 在 GitHub 上完成，**真正发出去只认业主在 GitHub 上的那一下批准**。

1. **发版 PR**：只改两处版本号（和要随版本走的说明），照普通 PR 过 CI、评审后合进 main。普通 PR 不改版本号。
2. **触发**：仓库 Actions → `release` → Run workflow，分支选 `main`。业主点或让 agent 点都行。
3. **workflow 自己做的**（任何一步红了都发不出去）：
   - 只在 main 上跑；environment `release` 存在、审批人是业主、部署分支只有 main（名字写错或被删掉时 GitHub 会自动建一个**没有任何保护**的，不等批准就发出去）；两处版本号一致；tag `v<版本>` 还不存在（同一版本不发两次）。
   - 整跑 `electron-e2e`：Linux 组包 + 云 Windows E1～E7 **全部**通过（FAIL 0）。出货包 artifact `release` 就取自这同一次运行。
   - 停下来等业主批准（environment `release`）。
4. **业主批准**：运行页面上点 Review deployments → 勾 `release` → Approve and deploy。不想发就不点，或者点 Reject。
5. **批准后 workflow 接着做**，用的都是 `desktop/scripts/release-feed.mjs` 这一个工具（`tests/test_desktop_release.mjs` 钉着它）：
   ```sh
   node desktop/scripts/release-feed.mjs verify <latest.yml> <安装包.exe>              # 先核安装包字节
   node desktop/scripts/release-feed.mjs rewrite <构建产物/latest.yml> <发布目录/latest.yml> <版本>
   node desktop/scripts/release-feed.mjs verify <发布目录/latest.yml> <安装包.exe>     # 改写后再核一次
   node desktop/scripts/release-feed.mjs gh-command <版本> <安装包.exe> <安装包.exe.blockmap> <发布目录/latest.yml> --target <构建提交> --run
   ```
   最后一条建 tag `v<版本>` 的正式 release（不是 prerelease），恰好上传安装包、`.blockmap` 与改写过的 `latest.yml` 三样资产；tag 打在本次构建的提交上，不是发布那一刻 main 的最新提交。
6. **核对**：运行摘要里写着版本、构建提交、tag 指向和三样资产；tag 指向与构建提交对不上时这一步会红。

一次性设置（仓库 Settings → Environments → New environment，名字**必须**是 `release`）：Required reviewers 选业主（`.aiwork/policy.json` 里 owner 那个账号）；Deployment branches and tags 选 Selected，只加 `main`。

换壳首版两台机器错开一天手动安装；旧版安装包继续保留在发布页。
