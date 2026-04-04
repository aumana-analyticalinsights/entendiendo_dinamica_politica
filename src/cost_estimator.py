"""X API cost estimator. Call estimate_* functions before running collectors."""

# Costs per resource/request in USD (source: docs/precios tweeter.txt)
COST_TWEET_READ = 0.005
COST_USER_READ = 0.010
COST_FOLLOWING_READ = 0.010


def estimate_timeline(user_ids: list[str], tweets_per_user: int = 1000) -> dict:
    """Estimate cost of collecting timelines for a list of users."""
    total_tweets = len(user_ids) * tweets_per_user
    cost = total_tweets * COST_TWEET_READ
    return {
        "operation": "timeline",
        "users": len(user_ids),
        "tweets_per_user": tweets_per_user,
        "total_resources": total_tweets,
        "cost_usd": round(cost, 2),
    }


def estimate_search(query_count: int = 1, tweets_per_query: int = 1000) -> dict:
    """Estimate cost of tweet search queries."""
    total_tweets = query_count * tweets_per_query
    cost = total_tweets * COST_TWEET_READ
    return {
        "operation": "search",
        "queries": query_count,
        "tweets_per_query": tweets_per_query,
        "total_resources": total_tweets,
        "cost_usd": round(cost, 2),
    }


def estimate_following(
    user_ids: list[str],
    avg_following_per_user: int = 2000,
) -> dict:
    """Estimate cost of fetching following lists."""
    total_follows = len(user_ids) * avg_following_per_user
    cost = total_follows * COST_FOLLOWING_READ
    return {
        "operation": "following",
        "users": len(user_ids),
        "avg_following_per_user": avg_following_per_user,
        "total_resources": total_follows,
        "cost_usd": round(cost, 2),
    }


def estimate_user_lookup(user_count: int) -> dict:
    """Estimate cost of looking up user profiles."""
    cost = user_count * COST_USER_READ
    return {
        "operation": "user_lookup",
        "total_resources": user_count,
        "cost_usd": round(cost, 2),
    }


def print_estimate(*estimates: dict, budget: float | None = None) -> float:
    """Print cost breakdown and return total. Optionally compare against budget."""
    total = 0.0
    print("--- Estimacion de costos X API ---")
    for est in estimates:
        print(f"  {est['operation']}: {est['total_resources']:,} recursos -> ${est['cost_usd']:.2f}")
        total += est["cost_usd"]
    print(f"  TOTAL: ${total:.2f}")
    if budget is not None:
        remaining = budget - total
        status = "OK" if remaining >= 0 else "EXCEDE PRESUPUESTO"
        print(f"  Presupuesto: ${budget:.2f} | Restante: ${remaining:.2f} | {status}")
    print("---")
    return total
