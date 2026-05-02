"""
base.py - Abstract base crawler | OWNER: Engineer A
RawPost schema is the CONTRACT between Engineer A and Engineer B.
Do not change field names without team agreement.
"""
from abc import ABC, abstractmethod
import queue
from datetime import datetime
import uuid


def make_raw_post(source, source_type, text, url, author=None, timestamp=None, metadata=None):
    return {
        "post_id":     str(uuid.uuid4()),
        "source":      source,
        "source_type": source_type,
        "text":        text,
        "url":         url,
        "author":      author,
        "timestamp":   timestamp or datetime.utcnow().isoformat(),
        "metadata":    metadata or {},
    }


class BaseCrawler(ABC):
    def __init__(self, source_config: dict, keywords: list, post_queue: queue.Queue):
        self.config   = source_config
        self.keywords = keywords
        self.queue    = post_queue

    @abstractmethod
    def crawl(self):
        pass

    def _enqueue(self, raw_post: dict):
        try:
            self.queue.put_nowait(raw_post)
        except queue.Full:
            pass
