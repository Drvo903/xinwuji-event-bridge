# 新物集活动情报桥（接口探测阶段）

目标：发现新物集上的展览、跑团展、ONLY、游戏展和其他线下活动，不采集普通商品众筹。

当前仅测试项目 4134 的电脑版与手机分享页的公开 XHR/Fetch 请求；尚未确认用于自动发现新活动的接口。

## 手动测试
打开仓库 Actions → **Probe Xinwuji API** → **Run workflow**。运行结束后，在该次运行的 Artifacts 中下载 `xinwuji-network-results`，查看 `network_results.json`。

输出仅保留部分字段并尝试遮盖敏感信息，公开分享前仍应检查令牌及个人数据。
