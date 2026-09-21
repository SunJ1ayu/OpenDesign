// E4 用的替身更新源(track opendesign-electron-shell U2)。只服务一个目录,支持单段 Range
// (electron-updater 的增量下载靠它;GitHub 那边也只给单段),每个请求记一行「路径 / Range / 实发字节」,
// 探针据此算「这次更新实际下了多少」。用法:node serve.mjs <目录> <端口> <日志文件>
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const [root, port, logFile] = process.argv.slice(2);
const note = (s) => fs.appendFileSync(logFile, s + "\n");

http
  .createServer((req, res) => {
    const name = decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/^\/+/, "");
    const file = path.join(root, name);
    if (!name || name.includes("..") || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      note(`404 ${req.method} ${name}`);
      res.writeHead(404).end();
      return;
    }
    const size = fs.statSync(file).size;
    const range = req.headers.range;
    let start = 0, end = size - 1, status = 200;
    if (range) {
      const m = /^bytes=(\d*)-(\d*)$/.exec(range);
      if (!m) {
        note(`416 ${name} ${range}`);
        res.writeHead(416, { "Content-Range": `bytes */${size}` }).end();
        return;
      }
      if (m[1] === "") { start = Math.max(0, size - Number(m[2])); }
      else { start = Number(m[1]); if (m[2] !== "") end = Math.min(Number(m[2]), size - 1); }
      status = 206;
    }
    const len = end - start + 1;
    const headers = { "Content-Length": len, "Accept-Ranges": "bytes", "Content-Type": "application/octet-stream" };
    if (status === 206) headers["Content-Range"] = `bytes ${start}-${end}/${size}`;
    res.writeHead(status, headers);
    if (req.method === "HEAD") { note(`${status} HEAD ${name}`); res.end(); return; }
    note(`${status} GET ${name} ${range || "-"} sent=${len}`);
    fs.createReadStream(file, { start, end }).pipe(res);
  })
  .listen(Number(port), "127.0.0.1", () => note(`listening ${port} ${root}`));
