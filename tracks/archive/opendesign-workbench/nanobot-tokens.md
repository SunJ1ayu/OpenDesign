# nanobot WebUI 设计 token(2026-07-07 从 pip 包编译产物提取)

来源:`nanobot-ai==0.2.2` 包内 `nanobot/web/dist/assets/index-DR8ZH26Q.css`。
用途:opendesign-workbench 改版"像素级抄 nanobot 视觉"的依据(用户 7-06 反馈)。
体系:Tailwind + shadcn/ui 风格 CSS 变量(HSL 空格分隔,`hsl(var(--x))` 引用)。

## 浅色(:root)

```css
:root {
  color-scheme: light;
  --background: 0 0% 100%;
  --foreground: 240 3% 12%;
  --card: 0 0% 100%;
  --card-foreground: 240 3% 12%;
  --popover: 0 0% 100%;
  --popover-foreground: 240 3% 12%;
  --primary: 240 4% 16%;
  --primary-foreground: 0 0% 98%;
  --secondary: 0 0% 96.1%;
  --secondary-foreground: 0 0% 9%;
  --muted: 0 0% 96.1%;
  --muted-foreground: 0 0% 45.1%;
  --accent: 0 0% 96.1%;
  --accent-foreground: 0 0% 9%;
  --destructive: 0 84.2% 60.2%;
  --destructive-foreground: 0 0% 98%;
  --border: 0 0% 89.8%;
  --input: 0 0% 89.8%;
  --ring: 0 0% 3.9%;
  --radius: .4375rem;            /* 7px,全站统一圆角 */
  --sidebar: 0 0% 98.5%;         /* 侧栏比主背景深半档 */
  --sidebar-foreground: 0 0% 3.9%;
  --sidebar-accent: 0 0% 95.8%;  /* 侧栏 hover/选中 */
  --sidebar-accent-foreground: 0 0% 9%;
  --sidebar-border: 0 0% 89.8%;
  --scrollbar-thumb: hsl(var(--muted-foreground) / .26);
  --scrollbar-thumb-hover: hsl(var(--muted-foreground) / .42);
  --cjk-line-height: 1.625;
}
```

## 深色(.dark)

```css
.dark {
  color-scheme: dark;
  --background: 0 0% 10%;        /* #1a1a1a */
  --foreground: 240 4% 96%;
  --card: 0 0% 12%;
  --card-foreground: 240 4% 96%;
  --popover: 0 0% 12%;
  --popover-foreground: 240 4% 96%;
  --primary: 240 5% 98%;
  --primary-foreground: 0 0% 9%;
  --secondary: 0 0% 12%;
  --secondary-foreground: 0 0% 98%;
  --muted: 0 0% 13%;
  --muted-foreground: 0 0% 60%;
  --accent: 0 0% 15%;
  --accent-foreground: 0 0% 98%;
  --destructive: 0 62.8% 30.6%;
  --destructive-foreground: 0 0% 98%;
  --border: 0 0% 18%;
  --input: 0 0% 18%;
  --ring: 0 0% 83.1%;
  --sidebar: 0 0% 11.5%;
  --sidebar-accent: 0 0% 15.5%;
  --sidebar-accent-foreground: 0 0% 98%;
  --sidebar-border: 0 0% 18%;
  --scrollbar-thumb: hsl(var(--muted-foreground) / .28);
  --scrollbar-thumb-hover: hsl(var(--muted-foreground) / .44);
}
```

## 字体

```css
body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto,
    Helvetica Neue, Arial, Noto Sans, Noto Sans SC, PingFang SC,
    Hiragino Sans GB, Microsoft YaHei, sans-serif,
    "Apple Color Emoji", "Segoe UI Emoji";
  -webkit-font-smoothing: antialiased;
}
/* 代码 */
font-family: JetBrains Mono, Fira Code, Cascadia Code, Source Code Pro,
  Menlo, Consolas, monospace;
```

- 基准字号 **13px / 14px**(紧凑感的关键,P0 用的字号偏大)
- 中文行高 `--cjk-line-height: 1.625`
- `body { overflow: hidden }`(应用壳布局,滚动在内部面板)

## 质感要点(非变量,从整体 CSS 归纳)

- 几乎零阴影:分区全靠 1px `--border` 边框 + 侧栏底色半档差
- 点缀色仅两处:destructive 红 + 橙色高亮 `rgba(255,138,61,.16)`(focus ring 类)
- 自定义细滚动条(thumb = muted-foreground 低透明度)
- 组件底座 = Radix(shadcn/ui),我们不搬组件代码(压缩产物,fork=屎山),
  只搬 token + 照样子重写布局:左侧栏(会话列表)+ 聊天流 + 底部输入框
