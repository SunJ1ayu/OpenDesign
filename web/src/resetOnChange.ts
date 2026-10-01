// 跟着某个对象走的状态(草稿、提示、测试结果):对象一换就重置。**同一个问题只留一个答案**:
// 图墙的标签 / 备注编辑区(GalleryPage)与模型设置的名称 / 地址草稿(settings/ModelSettings)共用这一份。
//
// 为什么不用 useEffect([key]) 重置:effect 在提交**之后**才跑,换对象后的第一帧把上一个对象(或空)的草稿
// 显示在新对象上,这一帧里打的字还会被随后的重置冲掉(e2e「#8 备注回填当前值」偶发读到空串就是这一帧)。
// 这里在渲染当中发现 key 变了就当场重置:React 允许组件在渲染中更新自己的状态,它丢掉这次的结果、
// 立刻用新状态重渲,旧草稿不会被提交到页面上。
// 判据:tests/e2e/stage_history.e2e.mjs「#8 编辑区一出现…」、tests/e2e/model_settings.e2e.mjs「Q8 打开这一家时…」。
import { useState } from "react";

const NEVER = Symbol("never");

/** key 与上一次渲染不同(含第一次渲染)时,在这次渲染里调 reset。reset 里只许调本组件的 setState。 */
export function useResetOnChange(key: unknown, reset: () => void): void {
  const [seen, setSeen] = useState<unknown>(NEVER);
  if (!Object.is(seen, key)) {
    setSeen(key);
    reset();
  }
}
