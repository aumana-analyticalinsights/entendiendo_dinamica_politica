"""Phase 2.0: Initial snapshot of the political ecosystem on X since candidacy registration.

Collects:
1. All tweets from seed accounts since March 13, 2026
2. Tweets mentioning main candidates (full archive search)
3. Extracts and ranks hashtags and active handles by bloc
"""

from pathlib import Path

import polars as pl
import yaml

from src.config import DATA_RAW, DATA_PROCESSED, PROJECT_ROOT
from src.collectors.tweet_collector import (
    SINCE_DATE,
    collect_user_timeline,
    resolve_user_ids,
    save_tweets,
    search_tweets,
)


def load_seed_accounts() -> dict[str, list[str]]:
    """Load seed accounts from config, grouped by bloc."""
    config_path = PROJECT_ROOT / "config" / "candidates.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    blocs = {}
    for bloc_name, bloc_data in config["bloques"].items():
        handles = []
        for c in bloc_data.get("candidatos", []):
            handles.append(c["handle"])
        for a in bloc_data.get("cuentas_asociadas", []):
            handles.append(a["handle"])
        blocs[bloc_name] = handles

    return blocs


def step_1_seed_timelines(blocs: dict[str, list[str]]) -> None:
    """Collect timelines of all seed accounts."""
    all_handles = [h for handles in blocs.values() for h in handles]
    print(f"Resolving {len(all_handles)} seed accounts...")
    id_map = resolve_user_ids(all_handles)
    print(f"Resolved {len(id_map)} accounts: {list(id_map.keys())}")

    for bloc_name, handles in blocs.items():
        bloc_records = []
        for handle in handles:
            username = handle.lstrip("@")
            user_id = id_map.get(username)
            if not user_id:
                print(f"  Could not resolve {handle}, skipping")
                continue
            print(f"  Collecting timeline: {handle} (id={user_id})")
            records = collect_user_timeline(user_id)
            print(f"    Got {len(records)} tweets")
            bloc_records.extend(records)

        save_tweets(bloc_records, f"seed_timelines_{bloc_name}")


def step_2_candidate_mentions() -> None:
    """Search for tweets mentioning the 3 main presidential candidates."""
    candidates = [
        ("Cepeda", "@IvanCepedaCast"),
        ("Valencia", "@PalomaValenciaL"),
        ("DelaEspriella", "@ABDELAESPRIELLA"),
    ]
    for name, handle in candidates:
        username = handle.lstrip("@")
        query = f"@{username} OR \"{name}\" lang:es"
        print(f"Searching mentions: {query}")
        records = search_tweets(query, start_time=SINCE_DATE, use_full_archive=True)
        save_tweets(records, f"mentions_{name.lower()}")


def step_3_rank_hashtags_and_handles() -> None:
    """Analyze collected tweets to rank hashtags and handles by frequency."""
    parquet_files = list(DATA_RAW.glob("*.parquet"))
    if not parquet_files:
        print("No data to analyze")
        return

    df = pl.concat([pl.read_parquet(f) for f in parquet_files])
    print(f"Analyzing {len(df)} total tweets")

    # Explode hashtags and count
    hashtags_df = (
        df.select("tweet_id", "hashtags")
        .explode("hashtags")
        .drop_nulls("hashtags")
        .group_by(pl.col("hashtags").str.to_lowercase().alias("hashtag"))
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )

    # Explode mentions and count
    mentions_df = (
        df.select("tweet_id", "mentions")
        .explode("mentions")
        .drop_nulls("mentions")
        .group_by(pl.col("mentions").str.to_lowercase().alias("handle"))
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )

    # Most active authors (non-seed)
    authors_df = (
        df.group_by("author_username")
        .agg(
            pl.len().alias("tweet_count"),
            pl.col("retweet_count").sum().alias("total_retweets"),
            pl.col("like_count").sum().alias("total_likes"),
        )
        .sort("tweet_count", descending=True)
    )

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    hashtags_df.write_parquet(DATA_PROCESSED / "hashtag_rankings.parquet")
    mentions_df.write_parquet(DATA_PROCESSED / "mention_rankings.parquet")
    authors_df.write_parquet(DATA_PROCESSED / "author_rankings.parquet")

    print(f"\nTop 20 hashtags:")
    print(hashtags_df.head(20))
    print(f"\nTop 20 mentioned handles:")
    print(mentions_df.head(20))
    print(f"\nTop 20 most active authors:")
    print(authors_df.head(20))


def run_snapshot() -> None:
    """Execute the full initial snapshot."""
    print("=" * 60)
    print("PHASE 2.0: Initial snapshot")
    print(f"Collecting since: {SINCE_DATE}")
    print("=" * 60)

    blocs = load_seed_accounts()
    print(f"\nBlocs: {list(blocs.keys())}")
    for name, handles in blocs.items():
        print(f"  {name}: {handles}")

    print("\n--- Step 1: Seed account timelines ---")
    step_1_seed_timelines(blocs)

    print("\n--- Step 2: Candidate mentions search ---")
    step_2_candidate_mentions()

    print("\n--- Step 3: Rank hashtags and handles ---")
    step_3_rank_hashtags_and_handles()

    print("\n" + "=" * 60)
    print("Snapshot complete!")


if __name__ == "__main__":
    run_snapshot()