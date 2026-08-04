// 助手消息的 markdown 渲染配置(T5,design.md D-C3)。
// 铁律:禁 raw HTML——react-markdown 默认不渲染 HTML(转义成文本),这是
// localStorage 口令不被模型输出 XSS 偷走的结构性前提,焊在 oracle
// (tests/test_chat_transcript.mjs XSS 闸)不靠自觉。谁在这里加 rehype-raw
// 或自定义 html 组件,oracle 会红。
// 刻意用 .ts + createElement 而非 .tsx:Node 原生 strip-types 不吃 JSX,
// 这样 oracle 能用 react-dom/server 直接渲染断言。
import { createElement, type ReactElement, type AnchorHTMLAttributes } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// 链接一律开新标签(track opendesign-chat-reconnect / T5b)。
// 为什么算在"断线自愈"那一单里:在本页跳走 = 工作台被卸载,回来要重新连一次 ——
// 它自己就是一次人为断线。`rel="noreferrer"` 连带断掉 window.opener(新页拿不到
// 反向引用)。**这里只加属性,href 仍走 react-markdown 默认的 urlTransform** ——
// 那正是 javascript:/data: 被剥空的地方,谁在这里把 href 原样透传回去,
// tests/test_chat_transcript.mjs 的 XSS 闸会红。
const components: Components = {
  a: ({ node: _node, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    node?: unknown;
  }) => createElement("a", { ...props, target: "_blank", rel: "noreferrer" }),
};

export function renderMarkdown(content: string): ReactElement {
  return createElement(
    ReactMarkdown,
    { remarkPlugins: [remarkGfm], components },
    content,
  );
}
