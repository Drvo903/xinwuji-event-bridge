"""Inspect public XHR/fetch calls from Xinwuji project pages.

Only captures response metadata and small redacted JSON samples.
"""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

URLS = [
    "https://shop.zhuoyou.com/share/project.html?project_id=4134",
    "https://www.xinwuji.com/pc/#/detail?id=4134",
]
OUT = Path("network_results.json")
SECRET_KEYS = ("token", "secret", "password", "cookie", "authorization", "session", "openid", "mobile", "phone", "email", "address")

def scrub(value, depth=0):
    if depth > 4:
        return "[nested]"
    if isinstance(value, dict):
        return {k: ("[redacted]" if any(x in k.lower() for x in SECRET_KEYS) else scrub(v, depth + 1)) for k, v in list(value.items())[:30]}
    if isinstance(value, list):
        return [scrub(v, depth + 1) for v in value[:3]]
    if isinstance(value, str):
        return value[:150]
    return value

def main():
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="zh-CN", timezone_id="Asia/Shanghai")
        for url in URLS:
            page = context.new_page()
            def capture(response):
                if response.request.resource_type not in ("xhr", "fetch"):
                    return
                content_type = response.headers.get("content-type", "")
                safe_url = re.sub(r"([?&](?:token|key|auth|session|sign|signature|secret)=[^&]*)", "[redacted]", response.url, flags=re.I)
                row = {"page": url, "method": response.request.method, "url": safe_url, "status": response.status, "content_type": content_type}
                try:
                    if "json" in content_type:
                        body = response.json()
                        row["json_keys"] = list(body)[:30] if isinstance(body, dict) else ["array"]
                        row["sample"] = scrub(body)
                except Exception as exc:
                    row["parse_error"] = str(exc)[:100]
                records.append(row)
            page.on("response", capture)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(7000)
                print("PAGE", url, "TITLE", page.title())
            except Exception as exc:
                print("ERROR", url, str(exc)[:300])
            page.close()
        browser.close()
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved", len(records), "XHR/fetch responses")
if __name__ == "__main__":
    main()
