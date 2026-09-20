"""启动被更新检查挡住多久 —— 改之前的基线(track opendesign-startup-not-blocked-by-update)。

🔴 这份探针的存在本身就是本单的一条教训:0.98.7 的规格里写着「检查超过 35 秒中断」,
那个数字是**算出来的、而且算错了**(代码注释说"后端三跳最多约 30 秒",实测是两跳 20 秒),
从头到尾没有人量过一次。两家外部评审都看过那条规格,没人问过 35 秒本身合不合理。
"""
import sys, time
sys.path.insert(0, "bin")
import ds_update

print(f"后端单跳超时 TIMEOUT_S = {ds_update.TIMEOUT_S}s")
print(f"缓存 TTL = {ds_update.CACHE_TTL_S}s(6 小时),但 _cache 是**进程内 dict** ⇒ 关软件即失效")
print("⇒ 每次打开软件都是冷缓存,必然真去联网\n")

# 最坏情况:网络可达但对端不回话(不是断网 —— 断网反而快)。
# 192.0.2.1 是 RFC5737 TEST-NET-1,保证不可路由,用来模拟"网络很差但没断"。
for name in ("releases_url", "atom_url"):
    setattr(ds_update, name, lambda *a, **k: "https://192.0.2.1/x")
ds_update.manifest_url = lambda *a, **k: "https://192.0.2.1/z"

t0 = time.time()
result = ds_update.check_for_update("0.98.6")
elapsed = time.time() - t0

print(f"一次查更新耗时:{elapsed:.1f} 秒")
print(f"前端 App.tsx 的上限是 35s,且 startupPhase 初值为 'checking'")
print(f"⇒ 这段时间里**整个工作区不渲染**,业主只能看全屏「正在检查更新…」")
print(f"\n基线判定:{'🔴 启动被阻塞超过 5 秒' if elapsed > 5 else '未复现'} —— 实测 {elapsed:.1f}s")
sys.exit(0 if elapsed > 5 else 1)   # 复现成功=0;测不出问题才是异常
