"""Discover likely offline events from Xinwuji's public project list.

This is a conservative MVP: it scans a bounded window of newest projects,
then enriches event-like candidates with their detail and ticket/goods records.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://www.xinwuji.com"
LIST_URL = f"{BASE}/api/v1/fundingProjects"
DETAIL_URL = f"{BASE}/api/v1.10/fundingProject/{{id}}"
GOODS_URL = f"{BASE}/api/v1/fundingProject/goods/{{id}}"
UPDATE_URL = f"{BASE}/api/v1/fundingProjectUpdateRecords/{{id}}"
DATA_DIR = Path("data")
LATEST_PATH = DATA_DIR / "latest.json"
STATUS_PATH = DATA_DIR / "status.json"
PAGE_SIZE = 12
MAX_PAGES = int(os.getenv("XWJ_MAX_PAGES", "20"))
KEYWORDS = (
    "活动", "展会", "展览", "嘉年华", "漫展", "同人", "only", "市集",
    "跑团", "桌游展", "线下", "观影会", "音乐节", "演出", "live",
)
NEGATIVE_HINTS = ("盲盒", "扩展包", "卡牌", "桌游", "模型", "手办", "骰子", "周边", "众筹", "游戏")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; XinwujiEventBridge/1.0)",
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


def text_blob(project):
    values = [
        project.get("title"), project.get("describe"), project.get("category_name"),
        project.get("company_name"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def looks_event_like(project):
    blob = text_blob(project)
    if not any(word in blob for word in KEYWORDS):
        return False
    # Keep broad positives such as "展" or "活动", but suppress obvious product-only hits.
    title = str(project.get("title") or "").lower()
    if any(word in title for word in ("盲盒", "扩展包", "金属骰", "模型", "手办")):
        return False
    return True


def safe_project(project):
    # Keep public, user-facing fields only; omit account/session-like data.
    keys = (
        "id", "title", "describe", "category_id", "category_name", "type", "status",
        "company_name", "cover", "list_cover", "created_at", "start_time", "over_time",
        "reservation_time", "min_price", "max_price", "support_number",
        "reservation_num", "source_status",
    )
    return {key: project.get(key) for key in keys if key in project}


def extract_items(data):
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        items = data.get("data")
        return (items if isinstance(items, list) else []), data.get("total")
    return [], None


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    previous = []
    if LATEST_PATH.exists():
        try:
            previous = json.loads(LATEST_PATH.read_text(encoding="utf-8")).get("items", [])
        except (json.JSONDecodeError, AttributeError):
            previous = []
    by_id = {str(item.get("id")): item for item in previous if item.get("id") is not None}

    scanned = 0
    pages_read = 0
    total = None
    candidates = 0
    errors = []
    try:
        for page_num in range(1, MAX_PAGES + 1):
            params = urlencode({"p": page_num, "limit": PAGE_SIZE, "status": 0, "sort": "new"})
            data = api_data(f"{LIST_URL}?{params}")
            rows, response_total = extract_items(data)
            if total is None:
                total = response_total
            pages_read += 1
            if not rows:
                break
            for project in rows:
                scanned += 1
                if not looks_event_like(project) or project.get("id") is None:
                    continue
                project_id = int(project["id"])
                candidates += 1
                item = safe_project(project)
                try:
                    detail = api_data(DETAIL_URL.format(id=project_id))
                    if isinstance(detail, dict):
                        item["detail"] = detail
                except Exception as exc:
                    errors.append(f"detail {project_id}: {str(exc)[:160]}")
                try:
                    goods_payload = get_json(GOODS_URL.format(id=project_id))
                    if isinstance(goods_payload, dict) and goods_payload.get("code") == 0:
                        goods = goods_payload.get("data")
                        item["goods"] = goods
                    else:
                        errors.append(f"goods {project_id}: unexpected response")
                except Exception as exc:
                    errors.append(f"goods {project_id}: {str(exc)[:160]}")
                # Store only public update records, and avoid turning a secondary failure
                # into failure of the discovery run.
                try:
                    update_data = api_data(f"{UPDATE_URL.format(id=project_id)}?limit=20")
                    item["updates"] = update_data
                except Exception as exc:
                    errors.append(f"updates {project_id}: {str(exc)[:160]}")
                item["discovered_at"] = datetime.now(timezone.utc).isoformat()
                by_id[str(project_id)] = item
                time.sleep(0.2)
            if len(rows) < PAGE_SIZE or (total is not None and scanned >= total):
                break
            time.sleep(0.25)
    except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        errors.append(f"listing: {str(exc)[:240]}")
        # Preserve existing output on a listing failure, but report unhealthy status.
        status = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "collector_status": "error",
            "pages_read": pages_read,
            "projects_scanned": scanned,
            "candidate_count": candidates,
            "list_total": total,
            "errors": errors[:30],
        }
        STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(1)

    items = sorted(by_id.values(), key=lambda item: str(item.get("discovered_at", "")), reverse=True)
    latest = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": LIST_URL,
        "scan_window": {"pages": pages_read, "page_size": PAGE_SIZE, "max_pages": MAX_PAGES},
        "items": items,
    }
    status = {
        "updated_at": latest["updated_at"],
        "collector_status": "partial" if errors else "ok",
        "pages_read": pages_read,
        "projects_scanned": scanned,
        "candidate_count": candidates,
        "retained_item_count": len(items),
        "list_total": total,
        "errors": errors[:30],
    }
    LATEST_PATH.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
