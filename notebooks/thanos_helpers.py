"""Funciones de analisis para el modelo THANOS.

Script acompanante de modelo_thanos.ipynb. Contiene logica reutilizable
para las 18 estrategias del plan estrategico y el ajuste del modelo.

NO duplica funciones de src/ -- solo agrega analisis nuevos.
"""

import time
from datetime import date, timedelta

import networkx as nx
import numpy as np
import polars as pl
import statsmodels.api as sm
import yaml
from statsmodels.genmod.families import Binomial

from src.config import DATA_PROCESSED, DATA_RAW, PROJECT_ROOT
from src.cost_estimator import COST_TWEET_READ
from src.twitter_client import get_client

# Cuentas polarizantes con millones de seguidores cuyos replies reflejan
# peleas historicas / gestion de gobierno, no conversacion de campana 2026.
# Se excluyen de descargas quirurgicas (E11-E14) pero se mantienen en
# hashtags y retweets (variables x, r del modelo THANOS).
EXCLUDED_DOWNLOAD_HANDLES: set[str] = {"petrogustavo", "alvarouribevel"}

# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------


def load_all_seed_tweets() -> pl.DataFrame:
    """Carga y concatena tweets semilla de ambos bloques con columna 'bloque'."""
    frames = []
    for bloque in ("derecha", "izquierda"):
        path = DATA_RAW / f"seed_timelines_{bloque}.parquet"
        if path.exists():
            df = pl.read_parquet(path).with_columns(pl.lit(bloque).alias("bloque"))
            frames.append(df)
    return pl.concat(frames).unique(subset=["tweet_id"])


def load_candidates_config() -> dict[str, list[dict]]:
    """Parsea candidates.yaml y retorna handles+ids por bloque.

    Returns:
        {"derecha": [{"handle": "@X", "id": "123", ...}, ...], "izquierda": [...]}
    """
    config_path = PROJECT_ROOT / "config" / "candidates.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    result: dict[str, list[dict]] = {}
    for bloque_name, bloque_data in config["bloques"].items():
        accounts = []
        for key in ("candidatos", "cuentas_asociadas"):
            for a in bloque_data.get(key, []):
                accounts.append({
                    "handle": a["handle"],
                    "id": a.get("id", ""),
                    "nombre": a.get("nombre", a["handle"]),
                    "rol": a.get("rol", ""),
                })
        result[bloque_name] = accounts
    return result


def get_all_seed_handles(config: dict[str, list[dict]]) -> set[str]:
    """Extrae todos los handles semilla (lowercase, sin @) del config."""
    return {a["handle"].lstrip("@").lower() for accounts in config.values() for a in accounts}


def load_edges() -> pl.DataFrame:
    """Lee interaction_edges.parquet."""
    return pl.read_parquet(DATA_PROCESSED / "interaction_edges.parquet")


def load_encuestas() -> pl.DataFrame:
    """Lee encuestas.parquet y parsea la columna fecha a pl.Date.

    La columna 'fecha' en el parquet tiene formato tipo '19-25 Mar' o similar.
    Se extrae la fecha final del rango como fecha de referencia.
    """
    df = pl.read_parquet(DATA_PROCESSED / "encuestas.parquet")
    # La columna fecha ya deberia estar como string; la convertimos a date
    # Formato esperado: "DD-DD Mon" o "DD Mon-DD Mon" -- tomamos la fecha final
    if df.schema.get("fecha") == pl.Utf8:
        month_map = {
            "Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Ago": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12,
            "Jan": 1, "Apr": 4, "Aug": 8, "Dec": 12,
        }

        def _parse_fecha_fin(s: str) -> date | None:
            parts = s.strip().split()
            if len(parts) < 2:
                return None
            month_str = parts[-1]
            month = month_map.get(month_str)
            if month is None:
                return None
            # El dia final esta justo antes del mes, puede ser "DD-DD" o solo "DD"
            day_part = parts[-2] if len(parts) > 2 else parts[0]
            day_str = day_part.split("-")[-1]
            try:
                return date(2026, month, int(day_str))
            except ValueError:
                return None

        fechas = df["fecha"].to_list()
        parsed = [_parse_fecha_fin(f) if isinstance(f, str) else None for f in fechas]
        df = df.with_columns(pl.Series("fecha_ref", parsed, dtype=pl.Date))
    return df


# ---------------------------------------------------------------------------
# Fase 0: E1-E7
# ---------------------------------------------------------------------------


def hashtags_by_bloc(df: pl.DataFrame) -> pl.DataFrame:
    """E1: Diccionario de hashtags agrupado por bloque politico.

    Returns:
        DataFrame con {hashtag, bloque, count, rank}
    """
    ranked = (
        df.select("tweet_id", "hashtags", "bloque")
        .explode("hashtags")
        .drop_nulls("hashtags")
        .with_columns(pl.col("hashtags").str.to_lowercase().alias("hashtag"))
        .group_by("hashtag", "bloque")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )
    # Rank dentro de cada bloque
    ranked = ranked.with_columns(
        pl.col("count")
        .rank(method="ordinal", descending=True)
        .over("bloque")
        .alias("rank")
    )
    return ranked.sort("bloque", "rank")


def retweet_chains(df: pl.DataFrame, config: dict[str, list[dict]]) -> pl.DataFrame:
    """E2: Cadenas de retweet y calculo de r_t^(k).

    Returns:
        DataFrame con {bloque, top_influencer, retweet_count, total_retweets, r_t_k}
    """
    # Mapear tweet_id -> autor original
    tweet_author = df.select(
        pl.col("tweet_id").alias("ref_tweet_id"),
        pl.col("author_username").str.to_lowercase().alias("original_author"),
    )

    # Filtrar retweets y unir con autor original
    rts = (
        df.filter(pl.col("ref_type") == "retweeted")
        .select("author_username", "ref_tweet_id", "bloque")
        .join(tweet_author, on="ref_tweet_id", how="inner")
    )

    # Contar retweets por (bloque, original_author)
    rt_counts = (
        rts.group_by("bloque", "original_author")
        .agg(pl.len().alias("retweet_count"))
        .sort("retweet_count", descending=True)
    )

    # Total por bloque
    totals = rt_counts.group_by("bloque").agg(
        pl.col("retweet_count").sum().alias("total_retweets")
    )

    # Top influencer por bloque
    top_per_bloc = rt_counts.group_by("bloque").first()

    result = (
        top_per_bloc.join(totals, on="bloque")
        .with_columns(
            (pl.col("retweet_count") / pl.col("total_retweets")).alias("r_t_k")
        )
        .rename({"original_author": "top_influencer"})
        .select("bloque", "top_influencer", "retweet_count", "total_retweets", "r_t_k")
    )
    return result


def proxy_influence(df: pl.DataFrame) -> pl.DataFrame:
    """E3: Ranking de influencia por max author_followers."""
    return (
        df.group_by("author_username", "bloque")
        .agg(pl.col("author_followers").max().alias("max_followers"))
        .sort("max_followers", descending=True)
        .drop_nulls("max_followers")
    )


def hashtag_cooccurrence(df: pl.DataFrame, min_count: int = 2) -> pl.DataFrame:
    """E4: Pares de hashtags que co-ocurren en el mismo tweet.

    Genera pares ordenados alfabeticamente para evitar duplicados.
    Filtra por min_count co-ocurrencias.
    """
    # Tweets con al menos 2 hashtags
    multi = (
        df.select("tweet_id", "hashtags")
        .filter(pl.col("hashtags").list.len() >= 2)
        .with_columns(
            pl.col("hashtags").list.eval(pl.element().str.to_lowercase()).alias("tags_lower")
        )
        .explode("tags_lower")
        .rename({"tags_lower": "tag"})
    )

    # Self-join para generar pares
    pairs = (
        multi.join(multi, on="tweet_id", suffix="_b")
        .filter(pl.col("tag") < pl.col("tag_b"))
        .group_by(
            pl.col("tag").alias("hashtag_a"),
            pl.col("tag_b").alias("hashtag_b"),
        )
        .agg(pl.len().alias("cooccurrence"))
        .filter(pl.col("cooccurrence") >= min_count)
        .sort("cooccurrence", descending=True)
    )
    return pairs


def detect_bots(
    df: pl.DataFrame,
    created_after: str = "2026-01-01",
    tweet_threshold: int = 10_000,
    ratio_threshold: float = 10.0,
) -> pl.DataFrame:
    """E5: Deteccion heuristica de bots.

    Criterios: cuenta creada despues de created_after AND
    tweet_count > tweet_threshold AND following/followers > ratio_threshold.
    """
    authors = (
        df.group_by("author_username", "author_id")
        .agg(
            pl.col("author_created_at").first(),
            pl.col("author_tweet_count").first(),
            pl.col("author_followers").first(),
            pl.col("author_following").first(),
        )
    )

    authors = authors.with_columns([
        (pl.col("author_created_at") > created_after).fill_null(False).alias("recent_account"),
        (pl.col("author_tweet_count") > tweet_threshold).fill_null(False).alias("high_volume"),
        (
            pl.col("author_following").cast(pl.Float64)
            / pl.col("author_followers").cast(pl.Float64).clip(lower_bound=1)
            > ratio_threshold
        ).fill_null(False).alias("high_ratio"),
    ])

    authors = authors.with_columns(
        (pl.col("recent_account") & pl.col("high_volume") & pl.col("high_ratio")).alias("is_bot")
    )
    return authors.select(
        "author_username", "author_id", "is_bot",
        "recent_account", "high_volume", "high_ratio",
        "author_created_at", "author_tweet_count", "author_followers", "author_following",
    )


def controversy_ratio(df: pl.DataFrame) -> pl.DataFrame:
    """E6: reply_count / max(like_count, 1) como proxy de controversia."""
    return (
        df.filter(pl.col("ref_type").is_null())  # Solo originales
        .with_columns(
            (
                pl.col("reply_count").cast(pl.Float64)
                / pl.col("like_count").cast(pl.Float64).clip(lower_bound=1)
            ).alias("controversy_score")
        )
        .sort("controversy_score", descending=True)
    )


def estimate_replies_volume(
    df: pl.DataFrame, seed_handles: set[str], exclude: set[str] = EXCLUDED_DOWNLOAD_HANDLES,
) -> pl.DataFrame:
    """E7: Estima volumen de replies disponibles y costo de descarga."""
    active_handles = seed_handles - {h.lower() for h in exclude}
    return (
        df.filter(
            pl.col("ref_type").is_null()
            & pl.col("author_username").str.to_lowercase().is_in(active_handles)
        )
        .group_by("author_username")
        .agg(pl.col("reply_count").sum().alias("total_replies"))
        .with_columns(
            (pl.col("total_replies") * COST_TWEET_READ).alias("estimated_cost_usd")
        )
        .sort("total_replies", descending=True)
    )


# ---------------------------------------------------------------------------
# Fase 1: E8-E10
# ---------------------------------------------------------------------------


def build_hashtag_queries(hashtag_dict: pl.DataFrame, top_n: int = 20) -> list[str]:
    """E8: Construye queries para count_recent de los top N hashtags."""
    top_tags = (
        hashtag_dict.group_by("hashtag")
        .agg(pl.col("count").sum())
        .sort("count", descending=True)
        .head(top_n)
        .get_column("hashtag")
        .to_list()
    )
    return [f"#{tag} lang:es" for tag in top_tags]


def build_candidate_queries(config: dict[str, list[dict]]) -> list[str]:
    """E10: Construye queries de count_recent por candidato."""
    queries = []
    for accounts in config.values():
        for a in accounts:
            if a.get("rol", "").startswith("Candidat"):
                handle = a["handle"].lstrip("@")
                queries.append(f"@{handle} lang:es -is:retweet")
    return queries


def run_count_recent(queries: list[str], granularity: str = "day") -> pl.DataFrame:
    """Ejecuta count_recent para una lista de queries.

    Returns:
        DataFrame con {query, date, count}
    """
    cost = len(queries) * 0.005
    print(f"Ejecutando {len(queries)} queries count_recent (costo: ${cost:.3f})")

    client = get_client()
    rows: list[dict] = []

    for q in queries:
        for page in client.posts.get_counts_recent(query=q, granularity=granularity):
            data = page.get("data", []) if isinstance(page, dict) else getattr(page, "data", []) or []
            for entry in data:
                e = entry if isinstance(entry, dict) else vars(entry)
                rows.append({
                    "query": q,
                    "date": str(e.get("start", ""))[:10],
                    "count": e.get("tweet_count", 0),
                })
        time.sleep(0.5)

    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# Fase 2: E11-E15
# ---------------------------------------------------------------------------


def build_cross_bloc_query(
    config: dict[str, list[dict]], exclude: set[str] = EXCLUDED_DOWNLOAD_HANDLES,
) -> str:
    """E11: Query que busca tweets mencionando candidatos de AMBOS bloques."""
    bloques_handles: dict[str, list[str]] = {}
    for bloque, accounts in config.items():
        handles = [
            a["handle"].lstrip("@") for a in accounts
            if a["handle"].lstrip("@").lower() not in {h.lower() for h in exclude}
        ]
        bloques_handles[bloque] = handles

    bloque_names = list(bloques_handles.keys())
    left = " OR ".join(f"@{h}" for h in bloques_handles[bloque_names[0]])
    right = " OR ".join(f"@{h}" for h in bloques_handles[bloque_names[1]])
    return f"({left}) ({right}) lang:es -is:retweet"


def top_reply_threads(
    df: pl.DataFrame, seed_handles: set[str], top_n: int = 50,
    max_replies_per_thread: int = 500,
    exclude: set[str] = EXCLUDED_DOWNLOAD_HANDLES,
) -> pl.DataFrame:
    """E12: Top N tweets semilla por reply_count (candidatos a descargar hilos).

    Agrega columna 'capped_replies' con min(reply_count, max_replies_per_thread)
    para presupuestar descargas.
    """
    active_handles = seed_handles - {h.lower() for h in exclude}
    return (
        df.filter(
            pl.col("ref_type").is_null()
            & pl.col("author_username").str.to_lowercase().is_in(active_handles)
        )
        .sort("reply_count", descending=True)
        .head(top_n)
        .with_columns(
            pl.col("reply_count").clip(upper_bound=max_replies_per_thread).alias("capped_replies")
        )
        .select("conversation_id", "tweet_id", "author_username", "text",
                "reply_count", "capped_replies", "like_count")
    )


def top_quoted_tweets(
    df: pl.DataFrame, top_n: int = 30, exclude: set[str] = EXCLUDED_DOWNLOAD_HANDLES,
) -> pl.DataFrame:
    """E13: Top N tweets por quote_count."""
    return (
        df.filter(
            pl.col("ref_type").is_null()
            & ~pl.col("author_username").str.to_lowercase().is_in(exclude)
        )
        .sort("quote_count", descending=True)
        .head(top_n)
        .select("tweet_id", "author_username", "text", "quote_count", "like_count")
    )


def download_quotes(
    top_quoted: pl.DataFrame, max_quotes_per_tweet: int = 100,
) -> list[dict]:
    """E13: Descarga quote tweets usando el endpoint dedicado get_quoted.

    No usa search_recent (quoted_tweet_id no existe como operador v2).
    Cada tweet se guarda incrementalmente a JSONL.
    """
    from src.collectors.tweet_collector import (
        _collect_pages, _append_jsonl, TWEET_FIELDS, EXPANSIONS, USER_FIELDS, DATA_RAW,
    )

    client = get_client()
    max_pages = max(1, max_quotes_per_tweet // 100)
    jsonl_path = DATA_RAW / "_quotes_all.jsonl"
    all_records: list[dict] = []

    for row in top_quoted.iter_rows(named=True):
        tid = row["tweet_id"]
        pages = client.posts.get_quoted(
            id=tid,
            max_results=100,
            tweet_fields=TWEET_FIELDS,
            expansions=EXPANSIONS,
            user_fields=USER_FIELDS,
        )
        records = _collect_pages(pages, max_pages=max_pages, jsonl_path=jsonl_path)
        all_records.extend(records)
        print(f"  Tweet {tid} ({row['author_username']}): {len(records)} quotes")
        time.sleep(0.5)

    print(f"\nTotal quotes descargados: {len(all_records)}")
    print(f"Costo: ${len(all_records) * COST_TWEET_READ:.2f}")
    return all_records


def download_threads_capped(
    threads: pl.DataFrame, max_replies_per_thread: int = 500,
) -> list[dict]:
    """E12: Descarga replies de hilos con cap por thread.

    Args:
        threads: DataFrame de top_reply_threads con conversation_id
        max_replies_per_thread: maximo de replies a descargar por hilo

    Returns:
        Lista de records descargados
    """
    from src.collectors.tweet_collector import search_tweets, save_tweets

    max_pages = max(1, max_replies_per_thread // 100)
    all_records: list[dict] = []

    for row in threads.iter_rows(named=True):
        conv_id = row["conversation_id"]
        query = f"conversation_id:{conv_id} -is:retweet"
        records = search_tweets(query, max_pages=max_pages)
        all_records.extend(records)
        print(f"  {row['author_username']}: {len(records)} replies (cap {max_replies_per_thread})")
        time.sleep(0.5)

    print(f"\nTotal descargado: {len(all_records)} tweets")
    print(f"Costo real: ${len(all_records) * COST_TWEET_READ:.2f}")
    return all_records


def download_citizen_mentions(
    config: dict[str, list[dict]], min_likes: int = 50, max_pages: int = 20,
    exclude: set[str] = EXCLUDED_DOWNLOAD_HANDLES,
) -> list[dict]:
    """E14: Descarga menciones ciudadanas con filtro de engagement.

    Usa search_recent con min_likes (operador v2, reemplaza min_faves).
    """
    from src.collectors.tweet_collector import search_tweets

    candidate_handles = " OR ".join(
        f"@{a['handle'].lstrip('@')}"
        for accounts in config.values() for a in accounts
        if a.get("rol", "").startswith("Candidat")
        and a["handle"].lstrip("@").lower() not in {h.lower() for h in exclude}
    )
    query = f"({candidate_handles}) lang:es -is:retweet min_likes:{min_likes}"
    print(f"Query: {query[:100]}...")
    records = search_tweets(query, max_pages=max_pages)
    print(f"Descargados: {len(records)} tweets (min_likes:{min_likes})")
    print(f"Costo: ${len(records) * COST_TWEET_READ:.2f}")
    return records


def poll_date_windows(
    encuestas: pl.DataFrame, window_days: int = 3,
) -> list[dict]:
    """E15: Ventanas temporales +/- window_days alrededor de cada encuesta.

    Returns:
        Lista de {"encuestadora": str, "start": str (ISO), "end": str (ISO)}
    """
    if "fecha_ref" not in encuestas.columns:
        encuestas = load_encuestas()

    windows = []
    for row in encuestas.iter_rows(named=True):
        fecha = row.get("fecha_ref")
        if fecha is None:
            continue
        start = fecha - timedelta(days=window_days)
        end = fecha + timedelta(days=window_days)
        windows.append({
            "encuestadora": row.get("encuestadora", ""),
            "fecha_ref": str(fecha),
            "start": f"{start}T00:00:00Z",
            "end": f"{end}T23:59:59Z",
        })
    return windows


# ---------------------------------------------------------------------------
# Fase 3: E16-E18
# ---------------------------------------------------------------------------


def identify_organic_nodes(in_degree: pl.DataFrame, top_n: int = 10) -> list[str]:
    """E16: Top N nodos no-semilla por in_degree."""
    return (
        in_degree.filter(~pl.col("is_seed"))
        .sort("in_degree", descending=True)
        .head(top_n)
        .get_column("target")
        .to_list()
    )


def identify_swing_users(
    citizen_tweets: pl.DataFrame, config: dict[str, list[dict]],
) -> pl.DataFrame:
    """E18: Usuarios que respondieron a candidatos de ambos bloques."""
    handles_by_bloc = {
        bloque: {a["handle"].lstrip("@").lower() for a in accounts}
        for bloque, accounts in config.items()
    }
    bloque_names = list(handles_by_bloc.keys())

    # Solo replies
    replies = citizen_tweets.filter(pl.col("in_reply_to_user_id").is_not_null())

    # Marcar a que bloque respondio
    replies = replies.with_columns(
        pl.col("mentions")
        .list.eval(pl.element().str.to_lowercase())
        .list.set_intersection(list(handles_by_bloc[bloque_names[0]]))
        .list.len()
        .gt(0)
        .alias(f"replied_{bloque_names[0]}"),
        pl.col("mentions")
        .list.eval(pl.element().str.to_lowercase())
        .list.set_intersection(list(handles_by_bloc[bloque_names[1]]))
        .list.len()
        .gt(0)
        .alias(f"replied_{bloque_names[1]}"),
    )

    # Agrupar por autor
    swing = (
        replies.group_by("author_username", "author_id")
        .agg(
            pl.col(f"replied_{bloque_names[0]}").sum().alias(f"{bloque_names[0]}_replies"),
            pl.col(f"replied_{bloque_names[1]}").sum().alias(f"{bloque_names[1]}_replies"),
        )
        .filter(
            (pl.col(f"{bloque_names[0]}_replies") > 0)
            & (pl.col(f"{bloque_names[1]}_replies") > 0)
        )
        .sort(f"{bloque_names[0]}_replies", descending=True)
    )
    return swing


# ---------------------------------------------------------------------------
# Modelo THANOS
# ---------------------------------------------------------------------------


def compute_hashtag_proportions(
    daily_counts: pl.DataFrame,
    hashtag_dict: pl.DataFrame,
    h: int,
    l: int,
    ref_date: str,
    top_n: int = 10,
) -> dict[str, float]:
    """Calcula x_{t,h,l}^(k): proporcion de top hashtags por partido en ventana (t-h, t-l).

    Args:
        daily_counts: DataFrame de run_count_recent con {query, date, count}
        hashtag_dict: DataFrame de hashtags_by_bloc con {hashtag, bloque, ...}
        h: dias hacia atras (inicio ventana)
        l: dias hacia atras (fin ventana, l < h)
        ref_date: fecha de referencia "YYYY-MM-DD"
        top_n: numero de hashtags por bloque

    Returns:
        {"x_derecha": float, "x_izquierda": float}
    """
    ref = date.fromisoformat(ref_date)
    start = str(ref - timedelta(days=h))
    end = str(ref - timedelta(days=l))

    # Top N hashtags por bloque
    top_per_bloc: dict[str, list[str]] = {}
    for bloque in hashtag_dict["bloque"].unique().to_list():
        tags = (
            hashtag_dict.filter(pl.col("bloque") == bloque)
            .sort("count", descending=True)
            .head(top_n)
            .get_column("hashtag")
            .to_list()
        )
        top_per_bloc[bloque] = tags

    # Filtrar counts en ventana
    window_counts = daily_counts.filter(
        (pl.col("date") >= start) & (pl.col("date") <= end)
    )
    total_in_window = window_counts["count"].sum()
    if total_in_window == 0:
        return {f"x_{b}": 0.0 for b in top_per_bloc}

    result = {}
    for bloque, tags in top_per_bloc.items():
        tag_queries = {f"#{t} lang:es" for t in tags}
        bloc_count = (
            window_counts.filter(pl.col("query").is_in(tag_queries))["count"].sum()
        )
        result[f"x_{bloque}"] = bloc_count / total_in_window

    return result


def compute_harmonic_centrality(edges: pl.DataFrame) -> tuple[str, float]:
    """Calcula centralidad armonica y retorna (top_user, h_t)."""
    G = nx.from_pandas_edgelist(
        edges.to_pandas(),
        source="source",
        target="target",
        create_using=nx.DiGraph(),
    )
    hc = nx.harmonic_centrality(G)
    top_user = max(hc, key=hc.get)
    return top_user, hc[top_user]


def compute_retweet_proportions(
    df: pl.DataFrame, config: dict[str, list[dict]],
) -> dict[str, float]:
    """Calcula r_t^(k) con datos expandidos (todos los tweets disponibles)."""
    handles_by_bloc = {
        bloque: {a["handle"].lstrip("@").lower() for a in accounts}
        for bloque, accounts in config.items()
    }

    tweet_author = df.select(
        pl.col("tweet_id").alias("ref_tweet_id"),
        pl.col("author_username").str.to_lowercase().alias("original_author"),
    )

    rts = (
        df.filter(pl.col("ref_type") == "retweeted")
        .select("author_username", "ref_tweet_id")
        .join(tweet_author, on="ref_tweet_id", how="inner")
    )

    result = {}
    for bloque, handles in handles_by_bloc.items():
        bloc_rts = rts.filter(pl.col("original_author").is_in(handles))
        total = len(bloc_rts)
        if total == 0:
            result[f"r_{bloque}"] = 0.0
            continue
        top_author = (
            bloc_rts.group_by("original_author")
            .agg(pl.len().alias("rt_count"))
            .sort("rt_count", descending=True)
            .head(1)
        )
        result[f"r_{bloque}"] = top_author["rt_count"][0] / total
    return result


def prepare_y_t(encuestas: pl.DataFrame, target_col: str = "Cepeda PH") -> pl.DataFrame:
    """Prepara y_t desde encuestas: proporcion + log-odds.

    Args:
        encuestas: DataFrame de encuestas con columna target_col (porcentaje 0-100)
        target_col: columna del candidato objetivo

    Returns:
        DataFrame con {encuestadora, fecha_ref, y_t, log_odds_y}
    """
    if "fecha_ref" not in encuestas.columns:
        encuestas = load_encuestas()

    cols = ["encuestadora", "fecha_ref", target_col]
    available = [c for c in cols if c in encuestas.columns]

    result = (
        encuestas.select(available)
        .with_columns(
            (pl.col(target_col).cast(pl.Float64) / 100.0).alias("y_t")
        )
        .drop_nulls("y_t")
        .filter((pl.col("y_t") > 0) & (pl.col("y_t") < 1))
        .with_columns(
            (pl.col("y_t") / (1.0 - pl.col("y_t"))).log().alias("log_odds_y")
        )
    )
    return result


def fit_thanos(
    features: pl.DataFrame,
    y_col: str = "y_t",
    x_cols: list[str] | None = None,
) -> sm.GLM:
    """Ajusta modelo THANOS con GLM Binomial(logit).

    Args:
        features: DataFrame con variable dependiente y predictores
        y_col: nombre de la columna con proporcion de votos (0-1)
        x_cols: columnas predictoras. Default: todas menos y_col

    Returns:
        Objeto GLMResults con summary(), params, aic, bic, etc.
    """
    if x_cols is None:
        x_cols = [c for c in features.columns if c != y_col and c not in ("encuestadora", "fecha_ref", "log_odds_y")]

    y = features[y_col].to_numpy()
    X = features.select(x_cols).to_numpy()
    X = sm.add_constant(X)

    model = sm.GLM(y, X, family=Binomial())
    result = model.fit()

    # Imprimir nombres de variables en el summary
    var_names = ["const"] + x_cols
    result.model.exog_names = var_names
    return result


def average_window_predictions(predictions: dict[tuple[int, int], float]) -> float:
    """Promedio de predicciones sobre ventanas (h,l): p_THN = mean(p_hat_{h,l})."""
    if not predictions:
        return 0.0
    return np.mean(list(predictions.values()))
