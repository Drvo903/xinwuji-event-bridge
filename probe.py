"""Probe public Xinwuji pages and the PC project discovery API.

Captures response metadata and small redacted JSON samples for manual inspection.
"""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "https://www.xinwuji.com"
URLS = [
    "https://shop.zhuoyou.com/share/project.html?project_id=4134",
    f"{BASE}/pc/",
    f"{BASE}/pc/#/list",
    f"{BASE}/pc/#/detail?id=4134",
]
DISCOVERY_URLS = [
    f"{BASE}/api/v1/fundingProjects?p=1&limit=12&status=0&sort=new",
    f"{BASE}/api/v1/fundingProjects?p=1&limit=12&status=0&sort=member",
    "https://api.zhuoyou.com/gateway/v5_0_0/phylum/list",
]
OUT = Path("network_results.json")
SECRET_KEYS = ("token", "secret", "password", "cookie", "authorization", "session", "openid", "mobile", "phone", "email", "address")


def scrub(value, depth=0):
    if depth > 4:
        return "[nested]"
    if isinstance(value, dict):
        return {
            k: "[redacted]" if any(x in k.lower() for x in SECRET_KEYS) else scrub(v, depth + 1)
            for k, v in list(value.items())[:30]
        }
    if isinstance(value, list):
        return [scrub(v, depth + 1) for v in value[:3]]
    if isinstance(value, str):
        return value[:150]
    return value


def capture_response(response, page_url, records):
    if response.request.resource_type not in ("xhr", "fetch"):
        return
    content_type = response.headers.get("content-type", "")
    safe_url = re.sub(
        r"([?&](?:token|key|auth|session|sign|signature|secret)=[^&]*)",
        "[redacted]", response.url, flags=re.I,
    )
    row = {
        "page": page_url,
        "method": response.request.method,
        "url": safe_url,
        "status": response.status,
        "content_type": content_type,
        "request_headers": {
            k: v for k, v in response.request.headers.items()
            if k.lower() in ("app-system", "app-version", "content-type")
        },
    }
    try:
        if "json" in content_type:
            body = response.json()
            row["json_keys"] = list(body)[:30] if isinstance(body, dict) else ["array"]
            row["sample"] = scrub(body)
    except Exception as exc:
        row["parse_error"] = str(exc)[:100]
    records.append(row)


def main():
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="zh-CN", timezone_id="Asia/Shanghai")
        for url in URLS:
            page = context.new_page()
            page.on("response", lambda response, u=url: capture_response(response, u, records))
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(7000)
                print("PAGE", url, "TITLE", page.title(), "FINAL_URL", page.url)
            except Exception as exc:
                print("ERROR", url, str(exc)[:300])
            page.close()

        # Reproduce the public PC-list requests without requiring a logged-in session.
        page = context.new_page()
        for url in DISCOVERY_URLS:
            try:
                headers = {"APP-SYSTEM": "PC"} if "/api/v1/fundingProjects" in url else {}
                response = page.request.get(url, headers=headers, timeout=30000)
                content_type = response.headers.get("content-type", "")
                row = {
                    "page": "direct-discovery-probe",
                    "method": "GET",
                    "url": url,
                    "status": response.status,
                    "content_type": content_type,
                    "request_headers": headers,
                }
                try:
                    body = response.json()
                    row["json_keys"] = list(body)[:30] if isinstance(body, dict) else ["array"]
                    row["sample"] = scrub(body)
                except Exception as exc:
                    row["parse_error"] = str(exc)[:100]
                records.append(row)
                print("API", response.status, url)
            except Exception as exc:
                print("API_ERROR", url, str(exc)[:300])
        browser.close()
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved", len(records), "XHR/fetch and direct API responses")


if __name__ == "__main__":
    main()
