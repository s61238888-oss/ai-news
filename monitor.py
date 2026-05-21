import json
import os
import sys
from typing import Any

import feedparser
import requests
from openai import OpenAI


SOURCES = [
    "https://tensorfeed.ai/feed.xml",
    "https://planet-ai.net/rss.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://news.mit.edu/rss/topic/artificial-intelligence2",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
]

AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL") or "https://api.lingshi.chat/v1"
AI_MODEL = os.getenv("AI_MODEL") or "gpt-4"
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")


def require_env(name: str, value: str | None) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def fetch_news() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    for url in SOURCES:
        try:
            feed = feedparser.parse(url)
            if getattr(feed, "bozo", False):
                print(f"Warning: feed parse issue for {url}: {feed.bozo_exception}")

            for entry in feed.entries[:5]:
                items.append(
                    {
                        "title": str(getattr(entry, "title", "")).strip(),
                        "summary": str(entry.get("summary", "")).strip()[:500],
                        "link": str(getattr(entry, "link", "")).strip(),
                    }
                )
            print(f"Fetched {len(feed.entries[:5])} items from {url}")
        except Exception as exc:
            print(f"Failed to fetch {url}: {exc}", file=sys.stderr)

    return [item for item in items if item["title"] and item["link"]]


def build_fallback_summary(items: list[dict[str, str]], reason: str | None = None) -> str:
    lines = []
    if reason:
        lines.append(f"AI summary failed, sending raw news instead.\nReason: {reason}\n")

    for index, item in enumerate(items[:5], start=1):
        summary = item["summary"].replace("\n", " ")
        if len(summary) > 160:
            summary = f"{summary[:157]}..."
        lines.append(f"{index}. {item['title']}\n   {summary}\n   Link: {item['link']}")

    return "\n\n".join(lines) if lines else "No AI news items were fetched today."


def summarize(items: list[dict[str, str]]) -> str:
    api_key = require_env("AI_API_KEY", AI_API_KEY)
    client = OpenAI(api_key=api_key, base_url=AI_BASE_URL)

    prompt = f"""Below is today's collected AI news.
Please:
1. Pick the 5 most important items, especially model releases, technical breakthroughs, and major industry events.
2. Summarize each item in one Chinese sentence.
3. Include the original link.

Output format:
1. [Title] One-sentence Chinese summary
   Link: xxx

News list:
{json.dumps(items, ensure_ascii=False, indent=2)}
"""

    response = client.chat.completions.create(
        model=AI_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or build_fallback_summary(items)


def send_to_feishu(text: str) -> None:
    webhook = require_env("FEISHU_WEBHOOK", FEISHU_WEBHOOK)
    response = requests.post(
        webhook,
        json={
            "msg_type": "text",
            "content": {"text": f"Daily AI News\n\n{text}"},
        },
        timeout=30,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Feishu webhook failed with HTTP {response.status_code}: {response.text}"
        )

    try:
        body: dict[str, Any] = response.json()
    except ValueError:
        body = {}

    if body.get("code") not in (None, 0):
        raise RuntimeError(f"Feishu webhook returned an error: {body}")


def main() -> None:
    news = fetch_news()
    print(f"Fetched {len(news)} total valid items")

    if not news:
        message = "No AI news items were fetched today."
    else:
        try:
            message = summarize(news)
        except Exception as exc:
            print(f"AI summary failed: {exc}", file=sys.stderr)
            message = build_fallback_summary(news, str(exc))

    print(message)
    send_to_feishu(message)
    print("Sent to Feishu")


if __name__ == "__main__":
    main()
