# 新物集活动情报桥（接口验证阶段）

目标：从新物集发现江浙沪跑团展、桌游展、ONLY、特色展览及其他线下活动，排除普通商品众筹。

## 首次实测（2026-10-15）

GitHub Actions 运行记录：[38677604552](https://github.com/Drvo903/xinwuji-event-bridge/actions/runs/38677604552)。Playwright 成功打开手机与 PC 项目详情页，发现 8 个 XHR/fetch 响应。样本为项目 ID `4134`：**SDT杭州坠入奇点跑团节（10.24-10.25）**。

已验证的公开读取接口：

- `GET https://www.xinwuji.com/api/v1.10/fundingProject/4134` — PC 端项目详情（标题、主办方等）。
- `GET https://www.xinwuji.com/api/v1/fundingProject/goods/4134` — 票种（`activity_time`、`market_price`、`preferential_price`、库存、购买状态等）。
- `GET https://www.xinwuji.com/api/v1/fundingProjectUpdateRecords/4134?limit=20` — 官方更新公告。
- `GET https://api.zhuoyou.com/gateway/shop/v1/project/detail?project_id=4134` — 手机端分享项目详情（页面调用会附带缓存破坏时间戳）。

## 活动发现接口（2026-10-30 实测）

检查当前 PC 前端静态代码，并使用公开只读请求验证了项目列表接口：

```http
GET https://www.xinwuji.com/api/v1/fundingProjects?p=1&limit=12&status=0&sort=new
APP-SYSTEM: PC
```

响应为 `code=0`，含 `data.total`、分页项目数组及项目 `id/title/status/category_name/created_at` 等字段。该接口可发现未知项目 ID；已知 ID 再交给详情、票种及更新公告接口读取。

PC 列表页前端使用参数：

- `p`：页码（从 1 开始）；`limit`：页大小（页面默认 12）。
- `status`：列表状态筛选。前端选项为 `0` 全部、`10` 预售中、`17` 预热中、`20` 预售完成。
- `sort`：空值默认排序、`new` 最新上线、`member` 支持人数最多、`amount` 预售金额最高。
- 可选 `category_id`：观察到 `category_id=3` 返回旧“桌游”类结果；当前分类导航接口返回桌游 ID 为 `1`，但用 `category_id=1` 查询列表返回 0 条。分类 ID 映射尚未厘清，暂不依赖分类参数。

分类导航候选接口（PC 前端静态包及公开请求均验证）：

```http
GET https://api.zhuoyou.com/gateway/v5_0_0/phylum/list
```

返回 `data.phylum_list`，其中含分类 `id/name/show_type`。当前接口暴露项目发现能力，但项目列表覆盖范围、线下活动类别覆盖情况和分类参数映射仍需持续核对。新物集列表以众筹项目为主，不等同于完整活动日历。

## 最小可行采集方式

1. 定期以 `sort=new` 请求项目列表，逐页读取并按项目 ID 去重；初期抓全部类别，不依赖尚未厘清的分类筛选。
2. 对新增 ID 调用详情、票种和更新公告接口。
3. 用标题、描述、票种时间、城市/场馆、报名与主办方信息筛选线下活动，排除普通商品众筹。
4. 保留原始项目 ID 与抓取时间；确认候选活动后再增量生成 `data/latest.json`、`data/status.json` 并接入周报。

## 运行探测

Actions → **Probe Xinwuji API** → **Run workflow**，运行结束下载 Artifacts 中的 `xinwuji-network-results`，查看 `network_results.json`。脚本访问 PC 首页、列表页、详情页及分享页，并直接请求列表与分类接口。日志和响应样本只保留有限字段/样本，分享前仍应核对第三方返回信息。

## 后续核验重点

- 检查不同 `p` 是否返回不同 ID 集合，`total` 与实际分页是否一致。
- 人工在 PC 列表页切换状态、排序和分类，确认请求参数与页面选项逐项对应。
- 特别验证分类筛选：当前观察到导航分类 ID 与 `category_id` 查询结果不一致；在确认映射前采用全量列表本地过滤。
- 用新发现 ID 验证详情/票种接口，并确认是否包含真实活动日期、城市、场馆或购票状态。
