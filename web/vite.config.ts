import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 生产形态:ds_web.py(8766)静态服务 dist + 同源 /api —— 无跨源。
// dev 形态:vite dev server 把 /api 代理到本机 ds_web,前端热更新照常。
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8766",
    },
  },
});
