# 发版清单(Windows 安装包)

> 由来:track opendesign-update-check-rate-limit(2026-09-15)。软件查更新**先问发布页订阅源 + 每版清单**,
> API 只是备路(未登录每出口 IP 60 次/小时,业主的 VPN 出口被别人用光过)。
> ⇒ **漏传清单 = 新版发出去了,用户那边照样查不到**(每次回落到被限流的 API)。

版本号只加第三位(`0.98.x`),`1.0.0` 留给业主拍板。bump 必须挂 track。

1. **bump**:`bin/ds_web.py` 的 `VERSION`;`.github/workflows/windows-package-probe.yml` 里四处默认值同步。
2. **打包**(在干净提交上,runlog 收据):
   ```
   runlog -t <track> -n build-installer-<ver>-release -- bash installer/build-installer.sh /root/aiwork/out/opendesign-<ver>-release
   ```
   静态闸 / 成品闸必须全绿;亲眼核 payload 里的 `VERSION` 与本版改动。
3. **写说明**:业主看的中文说明,存成 notes 文件(界面侧栏会显示第一句)。
4. **生成清单**(从构建产物本身算,不许手写):
   ```
   python3 installer/make-update-manifest.py <out>/OpenDesign-Setup-<ver>.exe win-installer-<ver> --notes <notes.md> --out <out>/OpenDesign-update.json
   ```
5. **推送 main,再发 release**(安装包与清单**一起**传):
   ```
   git push origin main
   gh release create win-installer-<ver> <out>/OpenDesign-Setup-<ver>.exe <out>/OpenDesign-update.json \
     -R SunJ1ayu/OpenDesign --target <打包那个提交> --prerelease --title "OpenDesign <ver> —— …" --notes-file <notes.md>
   ```
6. **发布核对**(runlog 收据,缺一不可):
   - 下载回来的安装包与本地逐字节一致;
   - **用产品自己的新路径**以上一版身份查:只问订阅源 + 清单(不问 API)就查到新版,digest / 大小 / 地址与已发布资产一致
     (写法见 `tracks/archive/opendesign-update-check-rate-limit/evidence/*real-github-feed-path-as-0984-v2*`)。
   - ⚠️ 本机自己的 GitHub 免登录额度可能被判据用光 —— 那只影响 API 备路那一步的核对,新路径不受影响。
7. **真机**:业主装机后运行中的软件回显版本号,才算发完(部署规矩)。
