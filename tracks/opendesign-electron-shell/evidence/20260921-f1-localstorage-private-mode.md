# 事实核查:装好的应用里 localStorage 其实不持久(2026-09-21,主 agent 读出货包源码)

出货包 0.98.9(/root/aiwork/out/opendesign-0.98.9-release/pkg,即安装包里那份 pywebview):
```
139:        'private_mode': True,
173:    private_mode: bool = True,
198:    :param private_mode: Enable private mode. In private mode, cookies and local storage are not preserved.
81:        props.set_IsInPrivateModeEnabled(_state['private_mode'])
```

外壳调用处(仓库 bin/ds_shell.py):
```
1371:        # 🔴 2026-08-30(判据 s6):「窗口打开」这行原来写在 `webview.start()` **之前** ——
1384:        webview.start()          # 阻塞,直到窗口 destroy
```

⇒ `webview.start()` 不传参 ⇒ private_mode=True ⇒ WebView2 以隐私模式运行,pywebview 自己的文档:
「In private mode, cookies and local storage are not preserved.」
⇒ 装好的应用里,前端存进 localStorage 的项目↔对话映射、自动更新开关、图库列数**每次重开都丢**。

对换壳的含义:没有旧数据可迁移;Electron 默认持久化,反而会开始记住(按 origin 分区,端口变了会是另一份)。
⚠️ 读代码得出,未在 Windows 上实测。
