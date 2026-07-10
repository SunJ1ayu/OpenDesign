// 助手消息的 markdown 渲染配置(T5,design.md D-C3)。
// 铁律:禁 raw HTML——react-markdown 默认不渲染 HTML(转义成文本),这是
// localStorage 口令不被模型输出 XSS 偷走的结构性前提,焊在 oracle
// (tests/test_chat_transcript.mjs XSS 闸)不靠自觉。谁在这里加 rehype-raw
// 或自定义 html 组件,oracle 会红。
// 刻意用 .ts + createElement 而非 .tsx:Node 原生 strip-types 不吃 JSX,
// 这样 oracle 能用 react-dom/server 直接渲染断言。
import { createElement, type ReactElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function renderMarkdown(content: string): ReactElement {
  return createElement(ReactMarkdown, { remarkPlugins: [remarkGfm] }, content);
}
