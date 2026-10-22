# Founder Pain Radar

Reads the week's top posts from r/Entrepreneur and r/smallbusiness, groups them by the problem each describes, and shows the result on a radar page. The top problem becomes a startup concept, Account Lifeboat.

## Run it

```
python3 server.py
```

Open http://localhost:8765. The server fetches Reddit's public RSS feeds (cached 15 minutes), groups posts by keyword and saves the result to `site/latest.json`. If Reddit rate-limits a subreddit (HTTP 429), the last good copy is shown and the fetch is retried after a minute.

## Notes
- RSS has no upvote or comment counts, so groups are ranked by post count.
- Grouping is keyword-based and approximate.
- Part of the AI Integration Challenge: Reddit (data), Claude Docs (report), Notion (board and post database), Google Drive (report folder), Claude Artifact (website), GitHub (this repo).
