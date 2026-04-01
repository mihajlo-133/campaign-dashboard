"""
QA Screenshot Capture

Takes screenshots of the dashboard at multiple viewports using Playwright CLI.
Polls for server readiness before capturing.

Usage:
  python qa/screenshot.py --port 8099 --prefix qa --wait
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

VIEWPORTS = [
    ("desktop", 1440, 900),
    ("tablet", 768, 1024),
    ("mobile", 375, 812),
]

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"

CAPTURE_SCRIPT_TEMPLATE = """
const {{ chromium }} = require('playwright');

(async () => {{
  const browser = await chromium.launch();
  const context = await browser.newContext({{
    viewport: {{ width: {width}, height: {height} }},
    deviceScaleFactor: 2,
  }});
  const page = await context.newPage();

  // Dashboard
  await page.goto('http://localhost:{port}/');
  await page.waitForTimeout(2000);  // let JS render
  await page.screenshot({{ path: '{out_path}', fullPage: true }});

  // Admin page (may redirect to login if no ADMIN_PASSWORD)
  try {{
    await page.goto('http://localhost:{port}/admin');
    await page.waitForTimeout(1000);
    await page.screenshot({{ path: '{admin_out_path}', fullPage: true }});
  }} catch (e) {{
    // Admin not accessible — skip
  }}

  await browser.close();
}})();
"""


def wait_for_server(port: int, timeout: float = 15.0) -> bool:
    """Poll GET /api/data until the server responds or timeout."""
    url = f"http://localhost:{port}/api/data"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def capture_screenshots(port: int, prefix: str) -> list[str]:
    """Capture screenshots at all viewports. Returns list of saved paths."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []

    for name, width, height in VIEWPORTS:
        out_path = SCREENSHOTS_DIR / f"{prefix}_{name}_{ts}.png"
        admin_out_path = SCREENSHOTS_DIR / f"{prefix}_admin_{name}_{ts}.png"

        script = CAPTURE_SCRIPT_TEMPLATE.format(
            width=width,
            height=height,
            port=port,
            out_path=str(out_path).replace("\\", "/"),
            admin_out_path=str(admin_out_path).replace("\\", "/"),
        )

        result = subprocess.run(
            ["npx", "playwright", "test", "--browser", "chromium", "-"],
            input=script,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Fallback: use playwright's screenshot CLI directly if test mode doesn't work
        if result.returncode != 0:
            # Use page.screenshot via a node eval with playwright
            node_script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const ctx = await browser.newContext({{ viewport: {{ width: {width}, height: {height} }}, deviceScaleFactor: 2 }});
  const page = await ctx.newPage();
  await page.goto('http://localhost:{port}/');
  await page.waitForTimeout(2000);
  await page.screenshot({{ path: '{str(out_path).replace(chr(92), "/")}', fullPage: true }});
  try {{
    await page.goto('http://localhost:{port}/admin');
    await page.waitForTimeout(1000);
    await page.screenshot({{ path: '{str(admin_out_path).replace(chr(92), "/")}', fullPage: true }});
  }} catch (e) {{}}
  await browser.close();
}})();
"""
            result2 = subprocess.run(
                ["node", "-e", node_script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result2.returncode != 0:
                print(f"  WARN: Failed to capture {name} viewport: {result2.stderr[:200]}")
                continue

        if out_path.exists():
            saved.append(str(out_path))
            print(f"  Saved: {out_path.name}")
        if admin_out_path.exists():
            saved.append(str(admin_out_path))
            print(f"  Saved: {admin_out_path.name}")

    return saved


def main():
    parser = argparse.ArgumentParser(description="QA Screenshot Capture")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--prefix", default="qa", help="Filename prefix (e.g., qa, manual)")
    parser.add_argument("--wait", action="store_true", help="Wait for server to be ready")
    args = parser.parse_args()

    if args.wait:
        print(f"Waiting for server on port {args.port}...")
        if not wait_for_server(args.port):
            print("ERROR: Server did not become ready within 15s")
            sys.exit(1)
        print("Server is ready.")

    print(f"Capturing screenshots (prefix={args.prefix})...")
    saved = capture_screenshots(args.port, args.prefix)

    if saved:
        print(f"\n{len(saved)} screenshots saved to {SCREENSHOTS_DIR}/")
    else:
        print("\nNo screenshots captured. Check Playwright installation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
