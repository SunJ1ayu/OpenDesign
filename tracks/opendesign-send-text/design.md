# Design: opendesign-send-text

- 做法:`ChatPage.tsx` 的 `.send-btn` 内容由 ↑ svg 换回文字「发送」(aria-label 留着);`app.css` `.send-btn` 回到 `padding: 0 14px`,
  `.send-btn` / `.stop-btn` 都 `min-width: 52px`。
- 检查深度:局部可逆、沿用 07-19 已验证的样子 ⇒ 直接验证,不走 4c、不派外审(impact self)。QA 不另走:改回的是业主定过的老样子,一个元素。
- 判据:composer_zcode e2e「发送键上是文字「发送」」(先红);受影响老判据 model_picker ⑯(窄栏 ↑/发送 在卡里)、narrow_window(1024 宽发送键在窗口里)、frontend_p2_polish(aria-label)照跑。
