# 新物集活动情报桥

目标：从新物集发现江浙沪跑团展、桌游展、ONLY、特色展览及其他线下活动，排除普通商品众筹。

## 已验证接口

### 项目发现（2026-10-30）

检查 PC 前端代码并以公开只读请求验证项目列表接口：

```http
GET https://www.xinwuji.com/api/v1/fundingProjects?p=1&limit=12&status=0&sort=new
APP-SYSTEM: PC
```

响应为 `code=0`，含 `data.total`、分页项目数组及项目 `id/title/status/category_name/created_at` 等字段，可发现未知项目 ID。PC 列表页参数：

- `p`：页码，从 1 开始；`limit`：每页数量，页面默认 12。
- `status`：列表筛选值；前端选项为 `0` 全部、`10` 预售中、`17` 预热中、`20` 预售完成。
- `sort`：空值默认排序、`new` 最新上线、`member` 支持人数最多、`amount` 预售金额最高。

分类导航接口：

```http
GET https://api.zhuoyou.com/gateway/v5_0_0/phylum/list
```

返回 `data.phylum_list`，包含分类 `id/name/show_type`。分类参数映射尚未厘清：观察到 `category_id=3` 返回旧“桌游”类结果，而导航返回的桌游 ID 为 `1`，查询 `category_id=1` 返回 0 条。因此发现流程暂不依赖分类过滤，而是在本地筛选。

### 项目详情、票种和公告（样本 ID：4134）

- `GET https://www.xinwuji.com/api/v1.10/fundingProject/4134` — PC 项目详情。
- `GET https://www.xinwuji.com/api/v1/fundingProject/goods/4134` — 票种及活动时间、价格、库存、购买状态等。
- `GET https://www.xinwuji.com/api/v1/fundingProjectUpdateRecords/4134?limit=20` — 官方更新公告。
- `GET https://api.zhuoyou.com/gateway/shop/v1/project/detail?project_id=4134` — 手机端分享详情。

样本项目为 **SDT杭州坠入奇点跑团节（10.24-10.25）**。新物集项目列表以众筹为主，并非完整活动日历；自动化结果需要人工复核，不能视为完整活动监测。

## 自动发现 MVP

`discover.py` 执行以下流程：

1. 按 `sort=new` 扫描最新项目，默认最多 20 页（每页 12 条，可用 `XWJ_MAX_PAGES` 调整）。
2. 按活动关键词初筛，排除若干明显商品类标题。
3. 对候选项目读取详情、票种和最近 20 条更新公告。
4. 按项目 ID 合并去重，输出 `data/latest.json`；运行状态写入 `data/status.json`。

关键词筛选是保守 MVP，可能漏掉标题不含活动线索的项目，也可能保留误命中的商品众筹。当前保存的是累计发现的候选项目，不代表每一项已被人工确认。

GitHub Actions 工作流 **Discover Xinwuji Events** 每天 03:20 UTC（香港时间 11:20）运行，也可手动触发并调整扫描页数。成功后会把变化提交到仓库，同时上传 `xinwuji-event-data` artifact。首次启用后应在 Actions 页面观察首次运行结果，并根据漏报/误报调整关键词。

## 网络探测

手动运行 Actions → **Probe Xinwuji API** → **Run workflow**，下载 `xinwuji-network-results` artifact 查看首页、列表页、详情页以及列表/分类接口响应。探测脚本只保留有限字段和小型响应样本。

## 后续核验

- 核对不同页是否返回不同 ID 集合，以及 `data.total` 和分页边界是否一致。
- 对照列表页的状态、排序和分类操作检查对应请求参数。
- 抽查自动筛中的活动与商品，持续调整关键词及排除规则。
- 对候选项目确认真实日期、城市/场馆、票种和购买状态，再接入江浙沪活动周报。

## 最初探测记录

首次 Playwright 探测运行：[2026-10-15 Actions run 38677604552](https://github.com/Drvo903/xinwuji-event-bridge/actions/runs/38677604552)。当时从手机与 PC 项目详情页采集到 8 个 XHR/fetch 响应。
