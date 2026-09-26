# 探针:本机真实网关数据里,对话文件元数据的 updated_at 与「最后一条消息的时间」各是什么分布
# (网关默认每 15 分钟对闲置对话做一次空闲压缩,每次都把 updated_at 刷成当时 —— nanobot agent/memory.py compact_idle_session)
import collections, glob, json, os
root = os.path.expanduser("~/.nanobot/workspace/sessions")
meta, last = collections.Counter(), collections.Counter()
for p in glob.glob(os.path.join(root, "websocket_*.jsonl")):
    ts = None
    with open(p, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if i == 0 and d.get("_type") == "metadata":
                meta[(d.get("updated_at") or "none")[:10]] += 1
            elif d.get("timestamp"):
                ts = d["timestamp"]
    last[(ts or "none")[:10]] += 1
print("对话数", sum(meta.values()))
print("元数据 updated_at 的日期:", dict(sorted(meta.items())))
print("最后一条消息的日期:", dict(sorted(last.items())))
