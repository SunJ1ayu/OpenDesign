我先读实施方案、探路证据和现有外壳/更新代码，从业主实际使用路径核对这份方案会在哪里落空。
手动装那一次会先拆掉他现在能用的 0.98.8，而探路把「有进程应答」当成装好了。两台电脑都会在他自己看见窗口之前失去退路。

## 1. 完全按方案做，目标仍会怎样落空

业主要的是：装上就能看见界面，档案、key、对话还在，以后更新不挡开机，窗口别再白装一次。下面每条都是方案原文会走到的事。

**手动装那一次（公司机，他双击）。** 正在跑的 0.98.8 看不见这次发布：`parse_atom` 只留下 tag 形如 `win-installer-<版本>` 的条目（`bin/ds_update.py` 的 `TAG_RE`、`parse_atom`）。新 tag 是 `v<版本>`，所以两台都得他自己双击，这是拍板过的。他双击之后看到的第一页是「为哪位用户安装」。第六跑的默认是「仅为我安装」，点「下一步」。**这条向导首装没有跑过。** 探针自己写明 E3 用的是 `/S`，而且不带 `/D`（`tracks/opendesign-electron-shell/spike/probe/electron-shell-probe.ps1` 开头和 E3-3）。第四跑收据写明：非静默首装没测。静默能装回 `HKCU\Software\OpenDesign\InstallDir`，不能当成他点出来的目录页也会停在 `F:\AI\OpenDesign`。

若目录页停在别的地方（electron-builder 当前用户的常见默认是 `%LOCALAPPDATA%\Programs\OpenDesign`），他不会去核对路径，会再点「下一步」。方案要求「不论他在选目录页选了哪里，都按注册表里的旧目录跑旧卸载器」。旧卸载器认到哨兵 `ds\bin\ds_shell.py` 就 `RMDir /r` 整个安装目录，并删掉开机自启和 `HKCU\Software\OpenDesign`（`installer/OpenDesign.nsi` 的 `un.OpenDesign`）。`F:\AI\OpenDesign` 里的程序没了。资料根 `%LOCALAPPDATA%\OpenDesign` 还在：卸载里「连资料一起删」是默认不勾的 `/o`，`/S` 不会选它，E3 也对 key 和档案做了哈希。他放进安装目录里的任何别的文件会跟着整棵目录一起没。新程序若落在他不认识的目录里，开机自启会被改写成那个新 exe（探路在 `preInit` 里记住旧 Run 值，首装时写回去）。第二天他仍会看到托盘里有东西，但 `F:\` 已经空了。家里那台对 `D:\AI\OpenDesign` 再来一遍。

他若在第一页改选「所有用户」（这一页他要求留着，而且第六跑证明**每次更新**都会再出现，不只首装）：安装器要管理员，程序进 `C:\Program Files`，旧目录仍按上面的逻辑被卸掉。开机自启写在提权之后的 HKCU 里，公司电脑上这个人和点「是」的管理员不是同一个账户时，明天托盘不会自己起来。

**之后第一次「重启以更新」。** 他点了按钮，管家 stdin 被关掉，接着 `quitAndInstall()` 默认参数，向导大约两分钟，选目录页会被跳过。第六跑在「只点默认下一步」时，目录、资料指纹、单条卸载项都还在，窗口能到前台。探针认定成功的条件是「健康检查有响应」：`E4.relaunch` 只看 `[bool]$h`。第二跑收据里 exe 已是 `0.98.11.0`，应答却是 `"version": "0.98.9"`。造 0.98.11 的工作流只给 `ds_web.py` 末尾追加一行注释，`VERSION = "0.98.9"` 不动（`.github/workflows/electron-shell-probe.yml` 里 E4 准备那一步）。旧更新器会把这次判失败：`health_says` 要求版本等于这一版（`bin/ds_update_apply.py`），接力脚本还要在应答里看见 nonce，避免没死透的旧进程也回 200（同文件 `:ask_health`；`bin/ds_web.py` 的 `/api/health` 注释写的就是这件事）。方案把这条闸和「装到旁边、起不来就改回名字」一起退役。他看见窗口，侧栏版本仍来自 `VERSION`，他还在跑旧的后台。两台各点一次，就各停在这个状态。

这两分钟里进度页的「取消」是灰的（第四跑截图）。他若关机，NSIS 是原地盖文件，没有 `.old` 可换回来。补救只剩发布页上的旧安装包，而原来那句「上次没成功、这一版不会再自动更新」（`web/src/App.tsx` 的 `tellIfRolledBack`）在退役清单里。托盘菜单只有打开、导出诊断、退出，没有这句话。

**他不点按钮。** 现成的「更新」在「设置」弹层里面，不在主界面上。收起的「设置」行上那个圆点是专门为这件事加的，注释写明：不留记号的话「有新版」只活在弹层里，他永远看不到（`web/src/workspace/Sidebar.tsx`，`hasUpdateBadge`）。方案把状态推到设置页，并退役横幅，没有写留下这个圆点。「重启以更新」若只出现在弹层里，不点是默认，不是他选了 C 之后的取舍。下载失败（他习惯先开软件、后开 VPN；`ds_update._open` 和 `_default_download` 就是为这件事改成每次请求现建代理）同样只在那一层里，下一次再查要等 4 小时。

**退役物里还要用的保证。** 版本对准和 nonce 如上。`/UPDATE` 不跑 provisioning，是为了更新时不重写 `UserData`（`OpenDesign.nsi` 文件头）。电子更新的 `--updated` 会跳过 `customInstall`，以后的更新守得住。换壳那一次不是 `--updated`，会跑 `ds_provision.provision`，在已有配置上做合并。E3 只检查 `config.json` 还在，没有对字节做哈希。同一版只自动试一次，在「必须他点」之后就不那么要紧。

## 2. 哪个前提是假的就要重做

前提是：**他只点向导里已经选好的「下一步」，新文件就会落在注册表记下的那个目录（公司 `F:\AI\OpenDesign`、家里 `D:\AI\OpenDesign`），起来之后 `/api/health` 的 `version` 等于这一版的 `ds_web.VERSION`。**

静默 E3 只证明了前半句的 `/S` 形态。第六跑的向导是更新、不是首装，而且成功标准不看版本。这句若是假的，换壳那一版不能发给他：要么装到别的目录同时拆掉旧目录，要么窗口开着、后台仍是旧 `VERSION`。

最小实验，放在现有的 `electron-shell-probe`（`windows-latest`）里：首装不要 `/S`，用第六跑那套 Win32 点击只点默认的「下一步」和「完成」，不要去点「所有用户」。断言安装目录等于事先写入的 `HKCU\Software\OpenDesign\InstallDir`，Run 键指向该目录里的 `OpenDesign.exe`，并且 `/api/health` 的 `version` 等于 exe 的 ProductVersion、也等于 `ds_web.VERSION`。后一条用现在这份工作流就会红，这正是要的红。

## 3. 更简单的做法

有。把探路版 `installer.nsh` 原样拿来当产品：只对已经算定的 `$INSTDIR` 跑旧卸载器，不要「选了别的目录也去卸注册表里的旧目录」；更新就用第六跑的 `quitAndInstall()` 默认参数。

牺牲的是：他机器上若第一眼是白的（0.93 就是只有他的机器白、包内前端和上一版逐字节相同），0.98.8 已经被 `RMDir /r` 掉了，当晚得再下一次 `win-installer-0.98.8`，还要自己把目录指回 `F:\` 或 `D:\`。云 Windows 上看不见这件事，E2 的界面在探针机器上是出来的。上面那个「向导默认下一步」实验只能分辨目录认不认得出；认得出，简单做法就够用到「他的窗口是白的」为止。

---

Direction: 换壳那一次先把旧目录改名为同盘的 `OpenDesign.old`，新版仍装进原来的 `F:\AI\OpenDesign` 或 `D:\AI\OpenDesign`；只有新进程的 `/api/health` 报出的 `version` 等于 `app.getVersion()`（打包时从 `ds_web.VERSION` 写入）才删 `.old`。对不上就留着 `.old`，窗口停在一句话上，告诉他双击 `.old\OpenDesign.exe`。之后的「重启以更新」仍是向导原地覆盖；同一条版本核对失败时，这句话改成发布页上上一版安装包的链接。「重启以更新」做在收起的「设置」那一行上，就是现在圆点占的位置。

Core bet: 他的退路是磁盘上那棵已经在用的 0.98.8，不是发布页，也不是探针里「有 JSON 应答」。旧卸载器一看到哨兵就会删整棵目录；探路的绿没有挡住「exe 是 0.98.11、健康检查仍是 0.98.9」。

How it works: `preInit` 仍把 `HKCU\Software\OpenDesign\InstallDir` 抄成默认目录。文件拷贝之前，把该目录改名为同级的 `OpenDesign.old`（同一块盘上的改名，不复制那一万个小文件）。卸载注册表项由脚本删掉，避免以后「应用和功能」里的旧项去删新目录；不要对 `.old` 调用 `卸载.exe /S`，因为 `un.OpenDesign` 会 `RMDir /r`。开机自启先别改。新版起来后主进程请求 `/api/health`：`version` 与 `app.getVersion()` 一致，才把 Run 键指到新 exe 并删 `.old`。不一致，或一直没有这份应答，Run 键指回 `.old\OpenDesign.exe`，主窗口不进工作区。更新（`--updated`）不再留第二棵树，核对失败只给人话和上一版安装包链接。按钮和失败原因都在收起的「设置」行上，弹层里再放「约 2 分钟，期间请别关机」。

Best at: 公司机当晚白屏或后台版本对不上时，他不用开 VPN 再下一遍 0.98.8，家里那台也还没被动过。也堵住现在这种「探针全绿、健康检查仍是旧 VERSION」的发版。

Sacrifices: 换壳当晚多占一份旧树的磁盘，直到核对通过。他若在核对通过前强杀进程，`.old` 会留在盘上。电子版之间的更新仍是原地覆盖，盖坏了只能装回发布页上的旧包。他改选「所有用户」时，新文件会进 Program Files，`.old` 仍在原来的盘上，两处都在，要靠那句人话告诉他该点哪一个。

Blind spots in the brief: 第六跑的增量是替身服务器把两个 blockmap 放在同一个目录里量的；`previousBlockmapBaseUrlOverride` 指向 `releases/download/v<当前版本>/` 这条 GitHub 布局没有跑过。第二跑在更宽松的同目录服务器上已经因 416 退回整包 158MB。`installer/RELEASE.md` 仍要求 `gh release create ... --prerelease`，而 `releases/latest` 会跳过 prerelease（`ds_update.py` 文件头，第二跑 curl 也是 404）。首装会跑 `ds_provision`，E3 没有核对 `config.json` 的字节。安装包没有签名，探针在同一台机器上生成并运行安装器，看不到他下载之后的 SmartScreen。

Smallest first step: 在现有 `electron-shell-probe` 里把 E3 之后和 `E4.relaunch` 改成：`/api/health` 的 `version` 必须等于 exe 的 ProductVersion。用现在这份「只追加注释、不改 `VERSION`」的工作流跑一次，确认它变红，再写改名。
