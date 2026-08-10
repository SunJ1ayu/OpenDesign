import { useState } from "react";
import ChatPage from "../chat/ChatPage";
import ConsentCard from "./ConsentCard";
import InboxCard from "./InboxCard";
import type { ChatSession } from "../chat/connection";

// 聊天列(handoff §4,340px):头部(项目助手 / ≡ / » 收起)+ ChatPage 真身。
// 收起(design 窄窗策略:稿上有 » 按钮)= 收成 36px 竖条,« 展开。
// P3 keep-mounted 同规矩:收起也走 CSS 隐藏,不卸载 ChatPage(卸载=丢对话)。

type Props = {
  session: ChatSession;
  prefill?: { text: string; nonce: number };
  dispatch?: { text: string; nonce: number }; // connect-ux:程序化发送透传
  onConnected?: () => void;
  onTurnEnd?: () => void;
  // project-thread:每项目一条工作对话(App 派生/记账,本组件只透传)
  resume?: { sessionKey: string; chatId: string; nonce: number } | null;
  onChatId?: (chatId: string) => void;
  onAttachFailed?: () => void;
  firstSendPrefix?: string;
  projectLabel?: string;   // -p2:聊天存图起名用(纯透传)
  dataEpoch?: number;      // -p2:收件箱卡片搬到本列顶部,沿用同一刷新节拍
  inboxActive?: boolean;   // -p2:路由门(仅工作区路由拉收件箱数据)
  onNewChat?: () => void; // 清当前项目映射+强制新会话
};

export default function ChatColumn({
  session, prefill, dispatch, onConnected, onTurnEnd,
  resume, onChatId, onAttachFailed, firstSendPrefix, projectLabel, onNewChat,
  dataEpoch = 0, inboxActive = false,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <section className={`chatcol${collapsed ? " collapsed" : ""}`}>
      {/* ⓪ 收件箱(-p2,用户提的:放项目助手上面,款式对齐左列)。
          原先刻意让它在收起态也留着(理由:它不属于聊天,不该跟着聊天消失)——
          **2026-07-27 真机截图推翻了这条**:36px 竖条里它只能被压成一字一行的竖排、
          还顶出视口右缘,"留着"等于留一片看不懂的残字。改成随收起一起 CSS 隐藏
          (app.css `.chatcol.collapsed > .inbox-card`),仍然不卸载。
          代价记账:收起期间看不到收件箱提示;collapsed 不持久化,刷新即回展开态。 */}
      {/* 业主同意卡(track opendesign-owner-consent):**排在收件箱上面**。
          理由:收件箱是"有东西等你归类",这张是"助手要扩大自己能看到的范围,
          等你点头" —— 后者不处理就一直卡着助手,而且是安全动作,该先看见。
          没有待确认时它自己不渲染,不占地方。 */}
      <ConsentCard dataEpoch={dataEpoch} active={inboxActive} />
      <InboxCard dataEpoch={dataEpoch} active={inboxActive} />
      {/* 工作区体检卡曾经在这里(T8)。**2026-07-28 用户拍板挪进「设置」** ——
          他自己说的用法是"偶尔校一次",常驻一张低频卡片是占地方。
          现在由 App 渲染在设置浮层里,本列不再出面(挪走就挪干净,别两处都有)。 */}
      {collapsed ? (
        <div className="chat-rail">
          <button className="icon-btn" title="展开项目助手" onClick={() => setCollapsed(false)}>
            «
          </button>
        </div>
      ) : (
        <div className="chatcol-head">
          <span className="t">项目助手</span>
          <span className="grow" />
          {onNewChat && (
            <button className="icon-btn" title="新对话(这个项目重新开一条)" onClick={onNewChat}>
              +
            </button>
          )}
          <button className="icon-btn" title="收起" onClick={() => setCollapsed(true)}>
            »
          </button>
        </div>
      )}
      <div className={`chatcol-body${collapsed ? " route-hidden" : ""}`}>
        <ChatPage
          session={session}
          prefill={prefill}
          dispatch={dispatch}
          onConnected={onConnected}
          onTurnEnd={onTurnEnd}
          resume={resume}
          onChatId={onChatId}
          onAttachFailed={onAttachFailed}
          firstSendPrefix={firstSendPrefix}
          projectLabel={projectLabel}
        />
      </div>
    </section>
  );
}
