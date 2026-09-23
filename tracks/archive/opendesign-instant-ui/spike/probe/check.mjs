// 判读规则(看结果之前写死):每条 OK/FAIL,FAIL 即该前提不成立。
import fs from "node:fs";
const w = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const r = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
let fail = 0;
const V = (n, ok, d) => { if (!ok) fail++; console.log(`${ok ? "OK  " : "FAIL"} ${n} :: ${JSON.stringify(d)}`); };
V("P0 页面在 app:// 下跑起来、没超时", !w.error && w.origin === "app://opendesign", { origin: w.origin, err: w.error });
V("P1 就绪前发的 /api 请求被挂起、就绪后成功返回(≥2500ms)", w.getSeen && w.getSeen.path === "/api/echo?x=1" && w.heldMs >= 2500, { held: w.heldMs, seen: w.getSeen });
V("P2 后台看到的请求:Host=127.0.0.1:端口、无 Origin、无 Sec-Fetch-Site", w.getSeen && /^127\.0\.0\.1:\d+$/.test(w.getSeen.host) && !w.getSeen.origin && !w.getSeen.sfs, w.getSeen);
V("P3 5MB 上传经代理完整到达", w.upload && w.upload.len === 5 * 1024 * 1024, w.upload);
V("P4 JSON POST 经代理、后台看不到 Origin", w.post && w.post.method === "POST" && w.post.len === 7 && !w.post.origin, w.post);
V("P5 图片 src=/api/img 能显示", w.img === 1, w.img);
V("P6 app:// 页面直连 ws://127.0.0.1 成功(无混合内容拦截)", w.ws === "echo:hi", w.ws);
V("P7 系统代理指向死端口时,回环请求照样通(代理绕过回环)", !!w.getSeen, "见 P1");
V("P8 深链路径回落到页面", w.deep === 200, w.deep);
V("P9 localStorage 写入成功", w.lsWrote === true, w.lsWrote);
V("P10 重开之后 localStorage 还在(app:// 源持久)", r.lsBefore === "written-run1", r.lsBefore);
console.log(`探针结束 FAIL ${fail}`);
process.exit(fail ? 1 : 0);
