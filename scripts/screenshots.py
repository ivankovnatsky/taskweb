"""Take screenshots of TaskWeb for README using Playwright."""

import subprocess
import sys
import time

from playwright.sync_api import sync_playwright


def main():
    port = 5199
    base = f"http://127.0.0.1:{port}"
    width, height = 1280, 900

    server = subprocess.Popen(
        [sys.executable, "-m", "taskweb", "serve", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)

    try:
        with sync_playwright() as p:
            for scheme in ("light", "dark"):
                browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
                ctx = browser.new_context(
                    viewport={"width": width, "height": height},
                    color_scheme=scheme,
                )
                page = ctx.new_page()

                # Main view
                page.goto(base)
                page.wait_for_load_state("networkidle")
                page.screenshot(path=f"screenshots/{scheme}-mode.png")
                print(f"  {scheme}-mode.png")

                if scheme == "light":
                    # Task detail
                    first_link = page.query_selector("a.task-link")
                    if first_link:
                        first_link.click()
                        page.wait_for_load_state("networkidle")
                        page.screenshot(path="screenshots/task-detail.png")
                        print("  task-detail.png")

                        # Edit view
                        edit_link = page.query_selector("a.btn-submit")
                        if edit_link:
                            edit_link.click()
                            page.wait_for_load_state("networkidle")
                            page.screenshot(path="screenshots/task-edit.png")
                            print("  task-edit.png")

                    # Completed view
                    page.goto(f"{base}/completed")
                    page.wait_for_load_state("networkidle")
                    page.screenshot(path="screenshots/completed.png")
                    print("  completed.png")

                ctx.close()
                browser.close()
    finally:
        server.terminate()
        server.wait()

    print("Done!")


if __name__ == "__main__":
    main()
