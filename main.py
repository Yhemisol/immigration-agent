"""Immigration Intelligence Agent — main orchestrator."""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from agent.crawlers import crawl_all
from agent.db import init_db, upsert_item, log_report
from agent.classifier import classify_all
from agent.reporter import build_html_report, send_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run() -> None:
    logger.info("=== Immigration Intelligence Agent starting ===")
    init_db()
    run_date = datetime.utcnow().strftime("%Y-%m-%d")

    # 1. Crawl all sources
    raw_items = crawl_all()
    logger.info("Total crawled items: %d", len(raw_items))

    # 2. Detect new / changed items
    new_items: list[dict] = []
    for item in raw_items:
        is_new, _ = upsert_item(item.source, item.url, item.title, item.content)
        if is_new:
            new_items.append({
                "source": item.source,
                "url": item.url,
                "title": item.title,
                "content": item.content,
            })
    logger.info("New / changed items: %d", len(new_items))

    # 3. Classify with Claude
    if new_items:
        classified = classify_all(new_items)
        logger.info("Successfully classified: %d", len(classified))
    else:
        classified = []

    # 4. Build and send report (always send — even if 0 new items, as a heartbeat)
    html = build_html_report(classified, run_date)

    # Save report locally
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    report_path = out_dir / f"report_{run_date}.html"
    report_path.write_text(html, encoding="utf-8")
    logger.info("Report saved to %s", report_path)

    # 5. Send email
    sent = send_report(html, run_date, len(classified))
    log_report(len(classified), sent)
    logger.info("=== Run complete ===")


if __name__ == "__main__":
    run()
