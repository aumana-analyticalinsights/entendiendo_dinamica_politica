"""X API client wrapper using xdk with Bearer Token authentication."""

import xdk
from src.config import X_API_KEY


# Fields to request -- broad collection for future LLM analysis and bot detection
TWEET_FIELDS = [
    "author_id", "created_at", "text", "public_metrics", "entities",
    "conversation_id", "in_reply_to_user_id", "referenced_tweets",
    "source", "lang",
]

USER_FIELDS = [
    "username", "name", "created_at", "public_metrics", "verified",
    "description", "location", "profile_image_url",
]

EXPANSIONS = [
    "author_id",
    "referenced_tweets.id",
    "referenced_tweets.id.author_id",
    "entities.mentions.username",
]


def get_client() -> xdk.Client:
    return xdk.Client(bearer_token=X_API_KEY)