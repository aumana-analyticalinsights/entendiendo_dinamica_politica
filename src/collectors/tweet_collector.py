"""Tweet collection from X API: seed account timelines and search queries."""

import json
import time
from datetime import datetime
from pathlib import Path

import polars as pl

from src.config import DATA_RAW
from src.twitter_client import (
    EXPANSIONS, TWEET_FIELDS, USER_FIELDS, get_client,
)


SINCE_DATE = "2026-03-13T00:00:00Z"  # Candidacy registration date
DEFAULT_MAX_PAGES = 10  # 10 pages * 100 tweets = 1000 tweets max


def _flatten_tweet(tweet: dict, users_map: dict) -> dict:
    """Extract flat record from a tweet object."""
    entities = tweet.get("entities") or {}
    metrics = tweet.get("public_metrics") or {}
    author_id = tweet.get("author_id", "")
    author = users_map.get(author_id, {})

    hashtags = [h["tag"] for h in entities.get("hashtags", [])]
    mentions = [m["username"] for m in entities.get("mentions", [])]

    ref_tweets = tweet.get("referenced_tweets") or []
    ref_type = ref_tweets[0]["type"] if ref_tweets else None
    ref_id = ref_tweets[0]["id"] if ref_tweets else None

    return {
        "tweet_id": str(tweet["id"]),
        "author_id": str(author_id) if author_id else None,
        "author_username": author.get("username"),
        "author_name": author.get("name"),
        "author_created_at": author.get("created_at"),
        "author_followers": (author.get("public_metrics") or {}).get("followers_count"),
        "author_following": (author.get("public_metrics") or {}).get("following_count"),
        "author_tweet_count": (author.get("public_metrics") or {}).get("tweet_count"),
        "author_verified": author.get("verified"),
        "author_description": author.get("description"),
        "author_location": author.get("location"),
        "text": tweet.get("text", ""),
        "created_at": tweet.get("created_at"),
        "lang": tweet.get("lang"),
        "source": tweet.get("source"),
        "conversation_id": str(tweet["conversation_id"]) if tweet.get("conversation_id") else None,
        "in_reply_to_user_id": str(tweet["in_reply_to_user_id"]) if tweet.get("in_reply_to_user_id") else None,
        "ref_type": ref_type,
        "ref_tweet_id": str(ref_id) if ref_id else None,
        "retweet_count": metrics.get("retweet_count"),
        "reply_count": metrics.get("reply_count"),
        "like_count": metrics.get("like_count"),
        "quote_count": metrics.get("quote_count"),
        "impression_count": metrics.get("impression_count"),
        "hashtags": hashtags,
        "mentions": mentions,
    }


def _build_users_map(includes: dict | None) -> dict:
    """Build user_id -> user_data map from response includes."""
    if not includes:
        return {}
    return {u["id"]: u for u in includes.get("users", [])}


def _load_jsonl(path: Path) -> list[dict]:
    """Load records from a JSONL file."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def _append_jsonl(records: list[dict], path: Path) -> None:
    """Append records to a JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _collect_pages(
    pages_iter,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    jsonl_path: Path | None = None,
) -> list[dict]:
    """Iterate over paginated responses, saving each page to JSONL incrementally."""
    records = []

    for page_num, page in enumerate(pages_iter):
        data = page.get("data") if isinstance(page, dict) else getattr(page, "data", None)
        if not data:
            break

        raw = page if isinstance(page, dict) else page.__dict__
        users_map = _build_users_map(raw.get("includes"))

        page_records = []
        for tweet in data:
            t = tweet if isinstance(tweet, dict) else tweet.__dict__
            page_records.append(_flatten_tweet(t, users_map))

        records.extend(page_records)

        if jsonl_path:
            _append_jsonl(page_records, jsonl_path)
            print(f"  p{page_num + 1}: +{len(page_records)} (total: {len(records)})")

        if max_pages and page_num + 1 >= max_pages:
            print(f"  Limite alcanzado: {max_pages} paginas ({len(records)} tweets)")
            break

        time.sleep(1)

    return records


def get_following(
    user_id: str,
    *,
    min_followers: int = 10_000,
    max_pages: int = 10,
) -> list[dict]:
    """Get accounts followed by user_id with min_followers threshold.

    Uses JSONL cache. Returns list of user dicts with id, username, followers_count.
    """
    jsonl_path = DATA_RAW / f"_following_{user_id}.jsonl"

    if jsonl_path.exists():
        records = _load_jsonl(jsonl_path)
        print(f"  Cache: {len(records)} cuentas desde {jsonl_path.name}")
        return records

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    client = get_client()
    pages = client.users.get_following(
        id=user_id,
        max_results=1000,
        user_fields=USER_FIELDS,
    )

    records = []
    page_count = 0
    for page in pages:
        data = page.get("data") if isinstance(page, dict) else getattr(page, "data", None)
        if not data:
            break

        page_records = []
        for user in data:
            u = user if isinstance(user, dict) else user.__dict__
            metrics = (u.get("public_metrics") or {})
            followers = metrics.get("followers_count", 0)
            if followers >= min_followers:
                page_records.append({
                    "user_id": str(u["id"]),
                    "username": u.get("username"),
                    "name": u.get("name"),
                    "followers_count": followers,
                    "following_count": metrics.get("following_count"),
                    "tweet_count": metrics.get("tweet_count"),
                    "verified": u.get("verified"),
                    "description": u.get("description"),
                })

        records.extend(page_records)
        _append_jsonl(page_records, jsonl_path)

        page_count += 1
        if max_pages and page_count >= max_pages:
            break
        time.sleep(1)

    print(f"  {len(records)} cuentas con >={min_followers:,} seguidores")
    return records


def expand_network(
    seed_user_ids: list[str],
    *,
    min_followers: int = 10_000,
) -> list[dict]:
    """Get deduped high-influence accounts followed by all seed accounts."""
    seen = {}
    for user_id in seed_user_ids:
        print(f"Following de {user_id}...")
        for account in get_following(user_id, min_followers=min_followers):
            uid = account["user_id"]
            if uid not in seen or account["followers_count"] > seen[uid]["followers_count"]:
                seen[uid] = account

    result = sorted(seen.values(), key=lambda x: x["followers_count"], reverse=True)
    print(f"\nRed expandida: {len(result)} cuentas unicas con >={min_followers:,} seguidores")
    return result


def resolve_user_ids(usernames: list[str]) -> dict[str, str]:
    """Resolve Twitter usernames to user IDs."""
    client = get_client()
    clean = [u.lstrip("@") for u in usernames]
    result = client.users.get_by_usernames(
        usernames=clean,
        user_fields=USER_FIELDS,
    )
    data = result.data if hasattr(result, "data") else result.get("data", [])
    mapping = {}
    for user in data:
        u = user if isinstance(user, dict) else user.__dict__
        mapping[u["username"]] = u["id"]
    return mapping


def collect_user_timeline(
    user_id: str,
    *,
    start_time: str = SINCE_DATE,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[dict]:
    """Collect tweets from a user's timeline. Uses JSONL cache if available."""
    jsonl_path = DATA_RAW / f"_timeline_{user_id}.jsonl"

    if jsonl_path.exists():
        records = _load_jsonl(jsonl_path)
        print(f"  Cache: {len(records)} tweets desde {jsonl_path.name}")
        return records

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    client = get_client()
    pages = client.users.get_posts(
        id=user_id,
        start_time=start_time,
        max_results=100,
        tweet_fields=TWEET_FIELDS,
        expansions=EXPANSIONS,
        user_fields=USER_FIELDS,
    )
    return _collect_pages(pages, max_pages=max_pages, jsonl_path=jsonl_path)


def search_tweets(
    query: str,
    *,
    start_time: str | None = SINCE_DATE,
    max_pages: int = DEFAULT_MAX_PAGES,
    use_full_archive: bool = False,
) -> list[dict]:
    """Search tweets by query. Uses JSONL cache if available.

    For search_recent (Basic tier), start_time is omitted by default since the
    API only allows the last 7 days and defaults to that range automatically.
    Pass start_time=None explicitly or rely on the automatic behaviour.
    """
    import hashlib
    safe_prefix = query.replace(" ", "_").replace("@", "")[:40]
    query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
    jsonl_path = DATA_RAW / f"_search_{safe_prefix}_{query_hash}.jsonl"

    if jsonl_path.exists():
        records = _load_jsonl(jsonl_path)
        print(f"  Cache: {len(records)} tweets desde {jsonl_path.name}")
        return records

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    client = get_client()
    search_fn = client.posts.search_all if use_full_archive else client.posts.search_recent

    kwargs: dict = dict(
        query=query,
        max_results=100,
        tweet_fields=TWEET_FIELDS,
        expansions=EXPANSIONS,
        user_fields=USER_FIELDS,
        sort_order="recency",
    )
    # search_recent (Basic) only supports last 7 days; skip start_time unless full archive
    if use_full_archive and start_time:
        kwargs["start_time"] = start_time

    pages = search_fn(**kwargs)
    return _collect_pages(pages, max_pages=max_pages, jsonl_path=jsonl_path)


def save_tweets(records: list[dict], name: str) -> Path:
    """Save tweet records to parquet in data/raw/."""
    if not records:
        print(f"No tweets to save for {name}")
        return DATA_RAW

    df = pl.DataFrame(records, infer_schema_length=None)
    df = df.with_columns(pl.lit(datetime.now().isoformat()).alias("collected_at"))
    df = df.unique(subset=["tweet_id"])

    output = DATA_RAW / f"{name}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output)
    print(f"Saved {len(df)} tweets to {output}")
    return output
