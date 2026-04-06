# Estrategias de ampliación de captura de tweets

## Contexto

El dataset inicial está sesgado: las cuentas semilla son tanto emisores como receptores, generando una red donde cada candidato tiene su "grupo de fans" interno. Para el modelo THANOS se necesita conversación ciudadana orgánica, no el ecosistema interno de los candidatos.

Precios API X: $0.005/tweet leído, $0.010/usuario leído, $0.010/following leído, $0.005/solicitud count_recent.

---

## Estrategia 1: Búsqueda por menciones de candidatos

**Qué captura:** Cualquier usuario que mencione a los candidatos — la conversación ciudadana directa.

**Query:**
```
(@PalomaValenciaL OR @petrogustavo OR @IvanCepedaCast OR @AlvaroUribeVel) lang:es -is:retweet
```

**Cómo medir antes de descargar:** `count_recent` devuelve el volumen de tweets por día sin descargarlos. 1 solicitud = $0.005.

**Estimado:** ~3,000–8,000 tweets/día mencionando candidatos presidenciales activos en Colombia. Período desde 13-mar (~22 días) → ~66,000–176,000 tweets disponibles.

**Costo:** Estimar = $0.005 | Descargar 10,000 tweets = $50 | 50,000 tweets = $250

---

## Estrategia 2: Búsqueda por hashtags electorales

**Qué captura:** Usuarios que usan hashtags como `#EleccionesColombia2026`, `#Presidenciales2026`, `#ColombiaVota`.

**Cómo medir:** `count_recent` por cada hashtag (1 solicitud c/u). Los hashtags orgánicos colombianos son de volumen bajo-medio, más fácil de controlar el costo.

**Estimado:** ~200–1,000 tweets/día por hashtag. 5 hashtags × 22 días × 500 avg = ~55,000 tweets disponibles. Con filtro de mínimo 10 retweets se reduce el volumen ~80%.

**Costo:** Estimar 5 hashtags = $0.025 | Descargar 10,000 tweets = $50 | Con filtro de engagement → ~2,000 tweets útiles = $10

---

## Estrategia 3: Replies a tweets de los candidatos

**Qué captura:** Lo que los ciudadanos le responden directamente a los candidatos — señal de alto valor para THANOS (engagement real).

**Cómo medir:** Ya tenemos `reply_count` por tweet en los datos actuales. La suma es el universo disponible sin gastar nada:

```python
df.filter(pl.col("author_username").is_in(seed_handles))
  .select("reply_count").sum()
```

**Estimado:** 200 tweets por candidato × promedio 50 replies = ~10,000 replies disponibles.

**Costo:** Estimar = $0 (dato ya en disco) | Descargar via `conversation_id` search: 10,000 tweets = $50

---

## Estrategia 4: Timelines de influenciadores orgánicos

**Qué captura:** Periodistas, medios y analistas políticos que ya aparecen en la red orgánica (ej. `aida_quilcue`, `eltiempo`, `elpaisamericaco`) — amplificadores neutrales.

**Cómo medir:** Usar `in_degree` de cuentas no-semilla del dataset actual. Top 50 cuentas orgánicas son candidatas. 1 `user_lookup` por cuenta informa cuántos tweets han publicado desde marzo.

**Estimado:** 50 influenciadores × ~300 tweets desde marzo = 15,000 tweets. Estimado 60% no duplicado con datos actuales.

**Costo:** Lookup 50 usuarios = $0.50 | Descargar 15,000 tweets = $75 | Neto nuevo ~$45

---

## Estrategia 5: Red de following compartido (follower overlap)

**Qué captura:** Cuentas que siguen a candidatos de ambos bloques — potenciales indecisos o ciudadanos transversales, los más valiosos para el modelo.

**Cómo medir:** Descargar listas `following` de los candidatos y calcular intersección entre bloques. El tamaño de la intersección es el universo disponible.

**Estimado:** Intersección izquierda/derecha ~5,000–20,000 cuentas. Tomar top 500 por actividad para recolectar timelines.

**Costo:** Leer seguidores masivos = muy caro ($500+). Alternativa viable: comparar `following` de las 10 semillas (infraestructura ya existe): 10 × 2,000 × $0.010 = $200

---

## Resumen comparativo

| Estrategia | Costo estimar | Tweets capturables | Costo descarga | Calidad señal |
|---|---|---|---|---|
| 1. Menciones directas | $0.005 | ~100,000 | $50–$250 | Alta |
| 2. Hashtags electorales | $0.025 | ~20,000 | $10–$50 | Media |
| 3. Replies a candidatos | $0 | ~10,000 | $50 | Muy alta |
| 4. Timelines influenciadores | $0.50 | ~15,000 | $45–$75 | Media-alta |
| 5. Following overlap | $0.10 | ~10,000 | $200 | Alta (cara) |

## Recomendación

Empezar con **Estrategia 3** (costo de estimación $0, señal muy alta) + **Estrategia 1** usando `count_recent` primero para controlar el volumen antes de descargar. Con $100 se obtiene un dataset ciudadano representativo para el modelo THANOS.
