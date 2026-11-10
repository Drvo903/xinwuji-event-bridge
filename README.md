# 新物集活动情报桥

目标：从新物集发现江浙沪跑团展、桌游展、ONLY、特色展览及其他线下活动，筛除普通商品众筹，并保留待核实候选。

## 已验证接口

### 项目发现（2026-10-30）

公开 PC 列表接口：

```http
GET https://www.xinwuji.com/api/v1/fundingProjects?p=1&limit=12&status=0&sort=new
APP-SYSTEM: PC
```

响应含 `data.total` 和分页项目数组及项目 ID、标题、状态、分类、创建时间等字段。分类导航接口为：

```http
GET https://api.zhuoyou.com/gateway/v5_0_0/phylum/list
```

分类筛选 ID 与导航 ID 曾出现不一致，因此采集流程不依赖分类参数。

### 详情、票种和公告（样本 ID：4134）

- `GET https://www.xinwuji.com/api/v1.10/fundingProject/4134` — 项目详情。
- `GET https://www.xinwuji.com/api/v1/fundingProject/goods/4134` — 票种及活动时间、价格、库存、购买状态等。
- `GET https://www.xinwuji.com/api/v1/fundingProjectUpdateRecords/4134?limit=20` — 项目更新公告。
- `GET https://api.zhuoyou.com/gateway/shop/v1/project/detail?project_id=4134` — 手机端分享详情。

## 自动发现

`discover.py` 每次运行会：

1. 按最新上线顺序分页扫描项目列表，默认最多 200 页（每页 12 条；当前约 180 页）。
2. 用活动线索初筛标题，再要求候选至少包含门票、入场、通行证等票务信息。
3. 读取候选详情、票种和更新公告，从票种 `activity_time`、项目详情文本和公告中提取活动日期；支持完整年月日、中文月日和 `10.31-11.01` 一类日期区间。缺少年份时暂以项目上线年份推断，并标记为 `year_inferred`，不当作已确认日期。
4. 排除明确在今天之前结束的活动；日期缺失的候选标为 `needs_date_review`。
5. 按江浙沪地点保留目标地区活动；已明确识别为外地的活动会被排除，地点不明确的保留待核。
6. 以项目 ID 去重，生成 `data/latest.json` 和 `data/status.json`。

**2026-11-09 定时运行结果复盘：**已完整扫描 2,152 个项目，但9条保留候选均缺少可识别日期，详情中无法访问的项目会记为部分成功。日期识别现已扩展至项目详情和更新公告文本；明确早于今天的候选会跳过，并计入 `expired_candidate_count`。年份由上线年份推断的日期可能误判，需结合 `date_sources`、`date_confidence` 人工复核。

自动筛选仍可能漏掉活动日期只出现在海报图片中的项目（当前没有 OCR），也可能漏掉标题线索不明显或地点只存在于图片里的项目。年月日未完整标出的文本日期会按项目上线年份推断，标记来源供复核；图片海报日期、日期歧义和未知地点都不能当作已确认信息发布。

## 定时工作流

GitHub Actions 的 **Discover Xinwuji Events** 每天 03:20 UTC（香港时间 11:20）运行，也可手动触发。手动运行默认扫描 200 页。成功后会提交最新数据并上传 `xinwuji-event-data` artifact。

查看结果：

- `data/latest.json`：当前/未来候选活动，含日期和地区核验状态。
- `data/status.json`：本轮扫描页数、项目数、初筛与保留数量、错误信息。
- Actions → 选中最新的 **Discover Xinwuji Events** → 下载 `xinwuji-event-data` artifact。

首次探测记录：[2026-10-15 Actions run 38677604552](https://github.com/Drvo903/xinwuji-event-bridge/actions/runs/38677604552)。
