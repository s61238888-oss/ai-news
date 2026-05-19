import os
import json
import requests
import feedparser
import anthropic

SOURCES = [
    "https://www.anthropic.com/news/rss.xml",
    "https://openai.com/blog/rss/",
    "https://www.jiqizhixin.com/rss",
]
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/41e0063e-e3dd-4474-8f84-fe2f6a7ba709"
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def fetch_news():
    items = []
    for url in SOURCES:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                items.append({
                    "title": entry.title,
                    "summary": entry.get("summary", "")[:500],
                    "link": entry.link,
                })
        except Exception as e:
            print(f"抓取失败 {url}: {e}")
    return items

def summarize(items):
    prompt = f"""下面是今天抓到的AI资讯。请：
1. 挑出最重要的5条（重点：模型发布、技术突破、行业大事）
2. 每条用一句中文总结
3. 附上原文链接

输出格式：
1. 【标题】一句话总结
   链接：xxx

资讯列表：
{json.dumps(items, ensure_ascii=False, indent=2)}
"""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

def send_to_feishu(text):
    requests.post(FEISHU_WEBHOOK, json={
        "msg_type": "text",
        "content": {"text": f"📰 今日AI资讯\n\n{text}"}
    })

if __name__ == "__main__":
    news = fetch_news()
    print(f"抓到 {len(news)} 条")
    summary = summarize(news)
    print(summary)
    send_to_feishu(summary)
    print("✅ 已推送到飞书")
