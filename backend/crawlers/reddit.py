"""
reddit.py - Reddit crawler via PRAW | OWNER: Engineer A
TODO: implement crawl() body
"""
import os, praw
from .base import BaseCrawler, make_raw_post

GEO_MAP = {
    "india": "IN", "mumbai": "IN-MH", "kerala": "IN-KL",
    "chennai": "IN-TN", "delhi": "IN-DL", "unitedkingdom": "GB",
}

class RedditCrawler(BaseCrawler):
    def __init__(self, source_config, keywords, post_queue):
        super().__init__(source_config, keywords, post_queue)
        self.reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT", "PatientSafetySentinel/1.0"),
        )
        self.subreddits = source_config.get("subreddits", [
            "diabetes", "ozempic", "medicine", "AskDocs", "ChronicIllness"
        ])

    def crawl(self):
        # TODO Engineer A: implement search loop, deduplication, enqueue
        for sub in self.subreddits:
            for kw in self.keywords:
                try:
                    for post in self.reddit.subreddit(sub).search(kw, limit=25, sort="new"):
                        self._enqueue(make_raw_post(
                            source=f"reddit/r/{sub}", source_type="reddit",
                            text=f"{post.title}\n{post.selftext}",
                            url=f"https://reddit.com{post.permalink}",
                            author=str(post.author), timestamp=str(post.created_utc),
                            metadata={"subreddit": sub, "score": post.score,
                                      "geo_proxy": GEO_MAP.get(sub.lower(), "UNKNOWN")},
                        ))
                except Exception as e:
                    print(f"Reddit error [{sub}/{kw}]: {e}")
