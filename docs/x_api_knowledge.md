# X API v2 -- Referencia tecnica

Documento de referencia rapida para el proyecto. Ultima actualizacion: 2026-04-05.

## Pricing (desde Feb 2026)

X API migro a **pay-per-use** con creditos prepagados (Developer Console).

- No hay tiers obligatorios. Los planes fijos (Basic $200, Pro $5000) siguen disponibles como alternativa.
- Creditos se compran por adelantado y se descuentan por llamada API.
- Deduplicacion: solicitar el mismo recurso multiples veces dentro de una ventana 24h UTC cuenta como un solo cobro.
- Bonus xAI credits segun gasto acumulado en el ciclo de facturacion:
  - $200-$499: 10%
  - $500-$999: 15%
  - $1,000+: 20%
- Pay-per-use tiene limite de 2M post reads/mes. Arriba de eso requiere Enterprise.
- Usuarios del antiguo free tier recibieron voucher de $10 al migrar.

Fuentes:
- https://docs.x.com/x-api/getting-started/pricing
- https://devcommunity.x.com/t/announcing-the-launch-of-x-api-pay-per-use-pricing/256476

## Endpoints principales

### search_recent
- URL: `GET /2/tweets/search/recent`
- Ventana: ultimos 7 dias (no configurable)
- `start_time`: debe estar dentro de los ultimos 7 dias. Si se omite, usa el rango completo de 7 dias automaticamente.
- `max_results`: 10-100 por pagina
- `sort_order`: "recency" o "relevancy"
- Soporta expansions, tweet_fields, user_fields
- Docs: https://docs.x.com/x-api/posts/search-recent-posts.md

### search_all (full archive)
- URL: `GET /2/tweets/search/all`
- Acceso a todo el archivo historico
- Mismos parametros que search_recent pero sin restriccion de 7 dias
- Docs: https://docs.x.com/x-api/posts/search-all-posts.md

### counts_recent
- URL: `GET /2/tweets/counts/recent`
- Solo cuenta tweets, no los descarga
- Ventana: ultimos 7 dias
- Granularidad: minute, hour (default), day
- Campos: start, end, tweet_count
- Docs: https://docs.x.com/x-api/posts/get-count-of-recent-posts.md

### counts_all (full archive)
- URL: `GET /2/tweets/counts/all`
- Conteo sobre todo el archivo historico
- Docs: https://docs.x.com/x-api/posts/get-count-of-all-posts.md

### get_quoted (quote tweets)
- URL: `GET /2/tweets/:id/quote_tweets`
- Endpoint dedicado para obtener quotes de un tweet especifico
- No requiere operador de busqueda
- Docs: https://docs.x.com/x-api/posts/get-quoted-posts

## Operadores de busqueda

### Disponibles en search_recent y counts_recent

| Operador | Ejemplo | Nota |
|---|---|---|
| keyword / frase | `elecciones` / `"voto en blanco"` | |
| #hashtag | `#Colombia2026` | |
| @mencion | `@IvanCepedaCast` | |
| from: | `from:petrogustavo` | Tweets de un usuario |
| to: | `to:petrogustavo` | Replies a un usuario |
| conversation_id: | `conversation_id:123456` | Tweets en un hilo |
| is:retweet | `-is:retweet` | Filtrar retweets |
| is:reply | `is:reply` | |
| is:quote | `is:quote` | |
| has:media | `has:images` | |
| lang: | `lang:es` | |
| url: | `url:123456` | Buscar por URL contenida |
| OR, AND (espacio), NOT (-) | `(A OR B) -C` | Booleanos |

### Solo en search (NO en counts)

| Operador | Ejemplo | Nota |
|---|---|---|
| min_likes: | `min_likes:50` | Operador v2. Reemplaza min_faves (deprecado) |
| min_reposts: | `min_reposts:10` | Operador v2. Reemplaza min_retweets (deprecado) |
| min_replies: | `min_replies:5` | |

### NO disponibles como operadores

| Operador | Estado | Alternativa |
|---|---|---|
| `quoted_tweet_id:` | No existe en v2 | Usar endpoint `get_quoted` o `url:{id} is:quote` |
| `min_faves` | Deprecado | Usar `min_likes:N` |
| `min_retweets` | Deprecado | Usar `min_reposts:N` |

## XDK (X Developer Kit) -- Python

SDK oficial de X para Python.

```
pip install xdk
# o con uv:
uv add xdk
```

### Autenticacion

```python
import xdk
client = xdk.Client(bearer_token=API_KEY)
```

### Paginacion

Todos los metodos paginados retornan **generadores**. Iterar con:

```python
for page in client.posts.search_recent(query="...", max_results=100):
    data = page.get("data", [])
    # procesar data
```

### Metodos principales

**Posts (client.posts):**
- `search_recent(query, ...)` -- busqueda ultimos 7 dias
- `search_all(query, ...)` -- busqueda archivo completo
- `get_counts_recent(query, granularity)` -- conteo ultimos 7 dias
- `get_counts_all(query, granularity)` -- conteo archivo completo
- `get_quoted(id, ...)` -- quote tweets de un tweet
- `get_by_id(id)` / `get_by_ids(ids)` -- tweets por ID
- `get_liking_users(id)` -- usuarios que dieron like
- `get_reposted_by(id)` -- usuarios que repostearon

**Users (client.users):**
- `get_following(id, ...)` -- cuentas que sigue un usuario
- `get_followers(id, ...)` -- seguidores de un usuario
- `get_by_username(username)` / `get_by_usernames(usernames)` -- buscar por username
- `get_posts(id, ...)` -- timeline de un usuario
- `get_mentions(id, ...)` -- menciones a un usuario

Repo: https://github.com/xdevplatform/xdk-python
Docs: https://docs.x.com/xdks/python/overview

## Documentacion oficial

- Indice completo para LLMs: https://docs.x.com/llms.txt
- Operadores: https://docs.x.com/x-api/posts/search/integrate/operators
- Construir queries: https://docs.x.com/x-api/posts/search/integrate/build-a-query
- Tools & libraries: https://docs.x.com/x-api/tools-and-libraries/overview