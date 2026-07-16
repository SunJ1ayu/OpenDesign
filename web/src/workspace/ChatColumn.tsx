import { useState } from "react";
import ChatPage from "../chat/ChatPage";
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
  onNewChat?: () => void; // 清当前项目映射+强制新会话
};

export default function ChatColumn({
  session, prefill, dispatch, onConnected, onTurnEnd,
  resume, onChatId, onAttachFailed, firstSendPrefix, onNewChat,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <section className={`chatcol${collapsed ? " collapsed" : ""}`}>
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
        />
      </div>
    </section>
  );
}
