# e:/PikDrishti AI/app/services/news_service.py
import feedparser

class NewsService:
    """Fetch latest Indian agricultural news via RSS feed."""

    # primary and fallback RSS sources
    PRIMARY_RSS = "https://khetigaadi.com/blog/category/agriculture/feed/"
    FALLBACK_RSS = "https://www.farmersline.com/rss"

    @staticmethod
    def get_agri_news(limit: int = 5):
        """Return list of news items (title, link, published, summary)."""
        feed = feedparser.parse(NewsService.PRIMARY_RSS)

        # if primary feed fails, try fallback
        if feed.bozo or not getattr(feed, "entries", []):
            feed = feedparser.parse(NewsService.FALLBACK_RSS)

        items = []
        for entry in feed.entries[:limit]:
            # truncate summary to 30 words for UI
            raw_summary = entry.get("summary", "")
            words = raw_summary.split()
            truncated = " ".join(words[:30]) + ("…" if len(words) > 20 else "")
            items.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published", ""),
                "summary": truncated,
                "categories": [tag.term for tag in getattr(entry, "tags", [])],
                "image": entry.get("media_content", [{}])[0].get("url", entry.get("media_thumbnail", [{}])[0].get("url", ""))
            })
        return items
