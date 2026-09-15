# 更新检查的夹具(录下来的真实响应,不是手编的)

**为什么必须录**:判据不许有外网出口(2026-08-10 事故:一份考卷真去叫外部模型,
一上午烧光额度)。所以查更新的逻辑一律喂这里的夹具,不打真网。

## `github-releases-20260907.json`

```
GET https://api.github.com/repos/SunJ1ayu/OpenDesign/releases?per_page=100
2026-09-07  http=200  104164 字节  20 个 release
```

**这份夹具存在的第一理由:20 个 release 全部 `prerelease: true`。**

同一天同一台机器上量到的另一半:

```
GET https://api.github.com/repos/SunJ1ayu/OpenDesign/releases/latest
→ http=404  {"message": "Not Found"}
```

`/releases/latest` **按 GitHub 的设计跳过 prerelease**,而本仓一版正式发布都没有
⇒ 谁要是把挑版本的逻辑改成那个接口,这个功能会**永远查不到新版本,而且不报错**。
判据 t1 钉的就是这件事,变异 m1 咬的也是它。**改这份夹具之前先想清楚你在放走什么。**

## `releases-atom-20260915.xml`(track opendesign-update-check-rate-limit)

```
GET https://github.com/SunJ1ayu/OpenDesign/releases.atom
2026-09-15  http=200  23407 字节  10 个 entry
```

从真响应裁出 0.98.5 / 0.98.4 / 0.98.3 三个 entry,`<content>` 截到前 400 字符(在实体边界上截);
结构、命名空间、`<link href=".../releases/tag/<tag>">` 原样。**它没有资产、没有 digest** —— 那一半来自每版清单 `OpenDesign-update.json`。
同一台机器上连打 70 次全是 200、响应头没有 x-ratelimit(对照:api.github.com 未登录 60 次/小时)。
