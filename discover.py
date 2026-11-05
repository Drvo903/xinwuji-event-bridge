"""Discover current or upcoming event-like projects from Xinwuji's public list."""
import html
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = "https://www.xinwuji.com"
LIST_URL = f"{BASE}/api/v1/fundingProjects"
DETAIL_URL = f"{BASE}/api/v1.10/fundingProject/{{id}}"
GOODS_URL = f"{BASE}/api/v1/fundingProject/goods/{{id}}"
UPDATE_URL = f"{BASE}/api/v1/fundingProjectUpdateRecords/{{id}}"
DATA_DIR = Path("data")
LATEST_PATH = DATA_DIR / "latest.json"
STATUS_PATH = DATA_DIR / "status.json"
PAGE_SIZE = 12
MAX_PAGES = int(os.getenv("XWJ_MAX_PAGES", "200"))
TODAY = datetime.now(ZoneInfo("Asia/Hong_Kong")).date()

EVENT_TERMS = (
    "活动", "展会", "展览", "嘉年华", "漫展", "同人", "only", "市集",
    "跑团", "trpg", "桌游展", "线下", "观影会", "音乐节", "演出", "live",
    "动漫节", "游戏节", "模型展", "玩偶嘉年华", "跑团节", "展会门票",
)
PRODUCT_TERMS = ("骰子套装", "桌游本体", "扩展包", "盲盒", "卡牌", "模型", "手办", "周边")
TICKET_TERMS = ("票", "门票", "入场", "通行证", "逛展", "报名", "活动名额", "单日")
TARGET_PLACES = (
    "浙江", "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华",
    "衢州", "舟山", "台州", "上海", "江苏", "南京", "苏州", "无锡",
    "常州", "镇江", "扬州", "泰州", "南通", "盐城", "淮安", "连云港",
    "徐州", "宿迁",
)
OTHER_PLACES = (
    "北京", "广州", "深圳", "成都", "重庆", "武汉", "西安", "长沙",
    "郑州", "济南", "青岛", "沈阳", "大连", "哈尔滨", "长春", "昆明",
    "贵阳", "南宁", "福州", "厦门", "石家庄", "天津", "合肥", "南昌",
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; XinwujiEventBridge/1.1)",
    "APP-SYSTEM": "PC",
    "Accept": "application/json",
    "Referer": f"{BASE}/pc/",
}


def get_json(url):
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def api_data(url):
    payload = get_json(url)
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise RuntimeError(f"Unexpected API response for {url}: {str(payload)[:300]}")
    return payload.get("data") or {}


def extract_items(data):
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        items = data.get("data")
        return (items if isinstance(items, list) else []), data.get("total")
    return [], None


def flatten(value):
    if isinstance(value, dict):
        return " ".join(flatten(v) for k, v in value.items() if not any(
            secret in k.lower() for secret in ("phone", "mobile", "email", "address_detail", "token", "password", "user_id")
        ))
    if isinstance(value, list):
        return " ".join(flatten(v) for v in value)
    return html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))


def likely_event(project):
    title = str(project.get("title") or "").lower()
    blob = " ".join(str(project.get(key) or "") for key in
                    ("title", "describe", "category_name", "company_name")).lower()
    if not any(term in blob for term in EVENT_TERMS):
        return False
    # A tabletop or dice product is not an event just because it mentions TRPG.
    if any(term in title for term in PRODUCT_TERMS) and not any(
        term in title for term in ("展", "活动", "嘉年华", "only", "市集", "跑团节", "游戏节")
    ):
        return False
    return True


def date_candidates(goods):
    found = []
    rows = goods.get("data", []) if isinstance(goods, dict) else []
    for row in rows if isinstance(rows, list) else []:
        raw = str(row.get("activity_time") or "")
        for y, m, d in re.findall(r"(20\d{2})[./年-](\d{1,2})[./月-](\d{1,2})", raw):
            try:
                found.append(date(int(y), int(m), int(d)))
            except ValueError:
                pass
    return sorted(set(found))


def activity_ticket_present(goods):
    rows = goods.get("data", []) if isinstance(goods, dict) else []
    if not isinstance(rows, list):
        return False
    return any(
        any(term in (str(row.get("name") or "") + " " + str(row.get("description") or "")).lower()
            for term in TICKET_TERMS)
        for row in rows
    )


def place_status(text):
    lower = text.lower()
    if any(place.lower() in lower for place in TARGET_PLACES):
        return "target_region"
    if any(place.lower() in lower for place in OTHER_PLACES):
        return "outside_target_region"
    return "unknown"


def public_detail(detail):
    if not isinstance(detail, dict):
        return {}
    keep = (
        "id", "title", "describe", "category_name", "company_name", "status",
        "start_time", "over_time", "detail_information", "update",
    )
    return {key: detail[key] for key in keep if key in detail}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    old_items = {}
    if LATEST_PATH.exists():
        try:
            old_items = {
                str(item.get("id")): item
                for item in json.loads(LATEST_PATH.read_text(encoding="utf-8")).get("items", [])
            }
        except (json.JSONDecodeError, AttributeError):
            old_items = {}

    scanned = pages_read = total = raw_candidates = ticket_candidates = 0
    items_by_id = {}
    errors = []
    try:
        for page_num in range(1, MAX_PAGES + 1):
            params = urlencode({"p": page_num, "limit": PAGE_SIZE, "status": 0, "sort": "new"})
            rows_data = api_data(f"{LIST_URL}?{params}")
            rows, response_total = extract_items(rows_data)
            if total is None:
                total = response_total
            pages_read += 1
            if not rows:
                break

            for project in rows:
                scanned += 1
                if project.get("id") is None or not likely_event(project):
                    continue
                raw_candidates += 1
                project_id = int(project["id"])
                record = {
                    "id": project_id,
                    "title": project.get("title"),
                    "category_name": project.get("category_name"),
                    "company_name": project.get("company_name"),
                    "status": project.get("status"),
                    "created_at": project.get("created_at"),
                    "project_url": f"{BASE}/pc/#/detail?id={project_id}",
                }
                try:
                    detail = api_data(DETAIL_URL.format(id=project_id))
                    record["detail"] = public_detail(detail)
                except Exception as exc:
                    errors.append(f"detail {project_id}: {str(exc)[:160]}")
                    detail = {}
                try:
                    goods = api_data(GOODS_URL.format(id=project_id))
                    record["goods"] = goods
                except Exception as exc:
                    errors.append(f"goods {project_id}: {str(exc)[:160]}")
                    goods = {}

                ticketed = activity_ticket_present(goods)
                if not ticketed:
                    continue
                ticket_candidates += 1
                activity_dates = date_candidates(goods)
                if activity_dates and max(activity_dates) < TODAY:
                    continue

                combined = flatten([project, detail, goods])
                region = place_status(combined)
                if region == "outside_target_region":
                    continue

                try:
                    updates = api_data(f"{UPDATE_URL.format(id=project_id)}?limit=20")
                    record["updates"] = updates
                    combined += " " + flatten(updates)
                    # Recheck region after reading announcements, which often provide venue.
                    region = place_status(combined)
                    if region == "outside_target_region":
                        continue
                except Exception as exc:
                    errors.append(f"updates {project_id}: {str(exc)[:160]}")

                previous = old_items.get(str(project_id), {})
                record["activity_dates"] = [d.isoformat() for d in activity_dates]
                record["date_status"] = "confirmed" if activity_dates else "needs_date_review"
                record["region_status"] = region
                record["first_seen_at"] = previous.get(
                    "first_seen_at", datetime.now(timezone.utc).isoformat()
                )
                record["last_seen_at"] = datetime.now(timezone.utc).isoformat()
                items_by_id[str(project_id)] = record
                time.sleep(0.15)

            if len(rows) < PAGE_SIZE or (total is not None and scanned >= total):
                break
            time.sleep(0.1)
    except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        errors.append(f"listing: {str(exc)[:240]}")
        STATUS_PATH.write_text(json.dumps({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "collector_status": "error",
            "pages_read": pages_read,
            "projects_scanned": scanned,
            "raw_candidate_count": raw_candidates,
            "ticket_candidate_count": ticket_candidates,
            "list_total": total,
            "errors": errors[:30],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(1)

    items = sorted(items_by_id.values(), key=lambda item: (
        item["activity_dates"][-1] if item["activity_dates"] else "9999-99-99",
        str(item.get("created_at") or ""),
    ))
    now = datetime.now(timezone.utc).isoformat()
    latest = {
        "updated_at": now,
        "source": LIST_URL,
        "scan_window": {"pages": pages_read, "page_size": PAGE_SIZE, "max_pages": MAX_PAGES},
        "items": items,
    }
    status = {
        "updated_at": now,
        "collector_status": "partial" if errors else "ok",
        "pages_read": pages_read,
        "projects_scanned": scanned,
        "raw_candidate_count": raw_candidates,
        "ticket_candidate_count": ticket_candidates,
        "retained_item_count": len(items),
        "list_total": total,
        "errors": errors[:30],
    }
    LATEST_PATH.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
