"""
twitter.py - Twitter/X crawler via twitterapi.io | OWNER: Engineer A
NOTE: Limited credits — batch keywords, cap results, avoid redundant calls
"""
import os, requests
from .base import BaseCrawler, make_raw_post

class TwitterCrawler(BaseCrawler):
    BASE_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"

    def crawl(self):
        query = " OR ".join(f'"{kw}"' for kw in self.keywords[:5])
        query += " lang:en -is:retweet"
        try:
            resp = requests.get(
                self.BASE_URL,
                headers={"X-API-Key": os.getenv("TWITTER_API_KEY")},
                params={"query": query, "maxResults": 20}, timeout=10)
            for tweet in resp.json().get("tweets", []):
                self._enqueue(make_raw_post(
                    source="twitter", source_type="twitter",
                    text=tweet.get("text", ""),
                    url=f"https://twitter.com/i/web/status/{tweet.get('id')}",
                    author=tweet.get("author", {}).get("userName", ""),
                    timestamp=tweet.get("createdAt", ""),
                    metadata={"likes": tweet.get("likeCount", 0),
                              "retweets": tweet.get("retweetCount", 0)},
                ))
        except Exception as e:
            print(f"Twitter error: {e}")
