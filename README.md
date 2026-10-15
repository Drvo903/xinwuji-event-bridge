# 新物集活动情报桥（接口验证阶段）

目标：从新物集发现江浙沪跑团展、桌游展、ONLY、特色展览及其他线下活动，排除普通商品众筹。

## 首次实测（2026-10-15）

GitHub Actions 运行记录：[38677604552](https://github.com/Drvo903/xinwuji-event-bridge/actions/runs/38677604552)。Playwright 成功打开手机与 PC 端页面，发现 8 个 XHR/fetch 响应。样本为项目 ID `4134`：**SDT杭州坠入奇点跑团节（10.24-10.25）**。

已验证的公开读取接口：

- `GET https://www.xinwuji.com/api/v1.10/fundingProject/4134` — PC 端项目详情（标题、主办方等）。
- `GET https://www.xinwuji.com/api/v1/fundingProject/goods/4134` — 票种（`activity_time`、`market_price`、`preferential_price`、库存、购买状态等）。
- `GET https://www.xinwuji.com/api/v1/fundingProjectUpdateRecords/4134?limit=20` — 官方更新公告。
- `GET https://api.zhuoyou.com/gateway/shop/v1/project/detail?project_id=4134` — 手机端分享项目详情（页面实际调用时附带缓存破坏时间戳）。

**注意：尚未找到项目列表、全站搜索或自动发现未知活动的接口。已知项目 ID 的详情抓取并不等于完整活动监控。**

## 运行探测
Actions → **Probe Xinwuji API** → **Run workflow**，运行结束下载 Artifacts 中的 `xinwuji-network-results`，查看 `network_results.json`。日志和样本可能含第三方返回信息，分享前应核对敏感内容。

## 下一阶段
1. 从 PC 首页 / 分类导航的网络请求中定位可公开使用的项目发现接口。
2. 只保留活动票务，结合标题、活动日期、城市、场馆及公告进行筛选。
3. 增量去重并生成 `data/latest.json`、`data/status.json`，接入现有江浙沪活动周报。
