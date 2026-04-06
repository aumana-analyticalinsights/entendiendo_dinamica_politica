# Plan estrategico de obtencion de informacion de Twitter

## Objetivo

Obtener la maxima cantidad de informacion util para alimentar el modelo THANOS (y su version mejorada con sentimiento) al menor costo posible en la API de X.

## Contexto

### Que necesita el modelo THANOS

| Variable | Descripcion | Fuente |
|---|---|---|
| `x_{t,h,l}^(k)` | Proporcion de los top 10 hashtags del partido k, promediada en ventana temporal (t-h, t-l) | Tweets ciudadanos con hashtags |
| `h_t` | Centralidad armonica del usuario mas influyente de la red en tiempo t | Grafo de interacciones |
| `r_t^(k)` | Proporcion de retweets del influenciador principal del partido k en tiempo t | Cadenas de retweet |
| `y_t` | Proporcion de votos segun encuestas | `poll_scraper.py` (resuelto) |

### Mejora planificada: THANOS + sentimiento LLM

El modelo original cuenta hashtags sin distinguir contexto. Un tweet con `#PalomaPresidenta` puede ser apoyo genuino, sarcasmo o mencion neutral. Incorporar un LLM para clasificar sentimiento transforma la variable de hashtags:

```
x_original = count(tweets con hashtag de partido k) / count(total tweets)

x_mejorada = sum(score_sentimiento * peso_engagement) / count(total tweets)
```

Donde `score_sentimiento` viene del LLM:
- +1.0 = aprobacion genuina
- +0.5 = mencion neutral positiva
-  0.0 = mencion neutral
- -0.5 = critica
- -1.0 = sarcasmo / desaprobacion explicita

### Precios API X (pay-per-use)

| Recurso | Costo unitario |
|---|---|
| Tweet: leer | \$0.005 |
| Usuario: leer | \$0.010 |
| Following/seguidores: leer | \$0.010 |
| Conteos (count_recent) | \$0.005 por solicitud |
| Lista: leer | \$0.005 |

### Problema diagnosticado en el dataset actual

El dataset inicial (timelines de 10 cuentas semilla) esta sesgado: las cuentas semilla son tanto emisores como receptores. El 100% de las interacciones hacia los nodos principales proviene de otras cuentas semilla (ej. `jdoviedoar` menciona 77 veces a `palomavalencial`). La red actual es el ecosistema interno de cada bloque, no la conversacion ciudadana que THANOS requiere.

---

## Tacticas transversales de obtencion

Estas tacticas se aplican como modificadores dentro de cualquier estrategia de busqueda. No son acciones independientes sino reglas que rigen la ejecucion.

### T1. Count-first (obligatorio antes de toda busqueda)

Antes de cualquier `search_recent`, ejecutar `count_recent` con la misma query. Devuelve el volumen de tweets por dia sin descargar contenido.

- Si volumen > 10,000: apretar filtros (subir `min_faves`, reducir ventana temporal)
- Si volumen < 100: ampliar filtros (quitar restricciones, extender ventana)

**Costo:** \$0.005 por consulta.
**Ahorro estimado:** 30-50% del presupuesto total al evitar descargas ciegas.

### T2. Query con operadores restrictivos apilados

Toda query debe construirse siguiendo este patron:

```
(handles OR hashtags) (keywords electorales) lang:es -is:retweet -has:links [min_faves:N]
```

Operadores disponibles:

| Operador | Uso |
|---|---|
| `@handle` | Menciones directas al candidato |
| `from:handle` | Tweets propios del candidato |
| `-is:retweet` | Excluir retweets (reduce volumen, captura opinion original) |
| `lang:es` | Solo en espanol |
| `-has:links` | Excluir spam de bots |
| `-has:media -has:images` | Solo texto puro (opinion directa) |
| `(#tag1 OR #tag2)` | Busqueda por hashtags de campana |
| `is:quote` | Solo quote tweets |
| `min_faves:N` | Filtro por engagement minimo |
| `place_country:CO` | Solo tweets geolocalizados en Colombia |

Combinar multiples exclusiones reduce el volumen 60-80% manteniendo la senal.

### T3. Muestreo progresivo por engagement

En lugar de descargar todo, escalonar por umbral de engagement:

1. Ronda 1: `min_faves:100` (tweets virales, muy pocos, muy baratos)
2. Ronda 2: `min_faves:50` (ampliar si necesita mas datos)
3. Ronda 3: `min_faves:20` (solo si la muestra es insuficiente)

Detenerse cuando se tenga suficiente poder estadistico. Aplicar T1 (count-first) antes de cada ronda.

**Como estimar costo:** Correr `count_recent` con cada umbral. El conteo de la ronda 1 × \$0.005 = costo de la ronda 1. Decidir si vale la pena la ronda 2 antes de ejecutarla.

### T4. Listas de X para timelines agrupados

En lugar de recolectar N timelines individuales, crear una lista privada en X con esas N cuentas y usar el endpoint `/2/lists/:id/tweets`. Una sola llamada paginada retorna tweets mezclados de todos los miembros. Misma cobertura, menos requests.

**Costo:** \$0.005 por tweet (igual que timeline), pero con menos overhead de paginacion.

### T5. Recoleccion alineada a picos y encuestas

Usar `count_recent` para identificar dias pico de actividad (debates, escandalos, publicacion de encuestas). Concentrar la descarga en esos dias. Los periodos de baja actividad tienen menos senal predictiva.

Las fechas de encuestas se obtienen de `poll_scraper.py`, que ya extrae las fechas de publicacion de cada encuestadora desde Wikipedia.

**Como estimar costo:** `count_recent` del dia pico × \$0.005 = costo de descargar ese dia. Comparar contra dias normales para decidir si el pico justifica la inversion.

---

## Fase 0: Exprimir datos actuales (costo \$0)

Estas estrategias extraen informacion de los datos ya recolectados sin llamar al API.

### E1. Extraccion de diccionario de hashtags desde timelines semilla

Extraer todos los hashtags de los tweets semilla. Agrupar por bloque politico segun el autor. Rankear por frecuencia. Resultado: diccionario inicial `{hashtag: bloque}`.

**Input THANOS:** Lista inicial de hashtags por partido para `x_{t,h,l}^(k)`.

### E2. Cadenas de retweet desde datos existentes

Los tweets ya tienen `ref_type == "retweeted"` y `ref_tweet_id`. Reconstruir las cadenas: quien retweetea a quien y cuantas veces. Calcular la proporcion de retweets por influenciador por partido.

**Input THANOS:** `r_t^(k)` directo.

### E3. Proxy de influencia via author_followers

Ya recolectamos `author_followers` en cada tweet. Usar el maximo de `author_followers` por cuenta para rankear influencia sin hacer lookups de usuario adicionales.

**Ahorro:** \$0.010 por usuario evitado. Con 500 usuarios = \$5 ahorrados.

### E4. Clustering de hashtags por co-ocurrencia

Construir una matriz de co-ocurrencia: que hashtags aparecen juntos en el mismo tweet. Hashtags que co-ocurren frecuentemente pertenecen al mismo bloque. Valida y expande el diccionario de E1 automaticamente.

**Input THANOS:** Clasificacion automatica de hashtags nuevos a su partido correspondiente.

### E5. Filtro de bots por heuristicas

Filtrar cuentas probablemente automatizadas: creadas despues de enero 2026 + tweet_count > 10,000 + ratio following/followers > 10. Limpiar antes de calcular metricas.

**Mejora:** Calidad de todas las variables THANOS.

### E6. Ratio replies/likes como proxy de controversia

`reply_count / like_count` alto indica contenido polarizante. Clasificar tweets por controversia permite ponderar las ventanas temporales: dias con alta controversia tienen mas senal predictiva para el modelo.

**Input THANOS:** Mejora la seleccion de ventanas (h, l).

### E7. Estimacion de replies disponibles desde reply_count

Sumar `reply_count` de todos los tweets de candidatos ya en disco. Esto da el volumen exacto de tweets ciudadanos disponibles para descargar (estrategia E10) sin costo.

**Como estimar costo de la descarga posterior:** `sum(reply_count) × \$0.005 = costo de descargar todos los replies`. Si es muy alto, priorizar los top N hilos por reply_count.

---

## Fase 1a: Monitoreo inmediato (~\$2/mes)

Estrategias que no dependen del diccionario de hashtags y se pueden arrancar de inmediato para acumular serie temporal.

### E9. Deteccion de picos noticiosos via count_recent

Correr `count_recent` con queries generales (`elecciones Colombia 2026 lang:es`) para cada dia. Identificar picos de actividad donde la senal predictiva es maxima.

**Costo:** \$0.005/dia = ~\$0.15/mes.
**Como estimar costo:** Fijo.
**Output:** Calendario de picos para alimentar T5 (recoleccion alineada).

### E10. Tracking de share of voice por candidato

Correr diariamente `count_recent` para cada candidato por separado (`@PalomaValenciaL lang:es`, `@petrogustavo lang:es`, etc.). La proporcion de menciones entre candidatos es en si misma una variable predictiva.

**Costo:** 10 candidatos × \$0.005 = \$0.05/dia = ~\$1.50/mes.
**Como estimar costo:** Fijo.
**Output:** Share of voice diario. Variable predictiva adicional para complementar THANOS.

---

## Fase 2: Descarga quirurgica de tweets ciudadanos (~\$30-\$80)

Estrategias que descargan contenido real, siempre precedidas por T1 (count-first) para estimar costo.

### E11. Tweets cross-bloque (votantes que comparan candidatos)

Buscar tweets que mencionan candidatos de AMBOS bloques en el mismo tweet:

```
(@PalomaValenciaL OR @AlvaroUribeVel) (@petrogustavo OR @IvanCepedaCast) lang:es -is:retweet
```

Estos son los tweets mas valiosos: personas comparando candidatos activamente. Volumen esperado muy bajo.

**Como estimar costo:** `count_recent` con la query → conteo × \$0.005.
**Estimado:** 200-1,000 tweets → \$1-\$5.
**Input sentimiento LLM:** Preferencia relativa entre candidatos. Alta prioridad para clasificacion.

### E12. Top N hilos de conversacion por reply_count

Ordenar tweets de candidatos por `reply_count` descendente (dato ya en disco, gratis). Tomar los 50 tweets con mas replies. Descargar solo esos hilos via `conversation_id:X`.

**Como estimar costo:** Ya conocemos el `reply_count` exacto de cada tweet. Sumar los top 50 × \$0.005.
**Estimado:** 50 hilos × ~100 replies promedio = 5,000 tweets → \$25.
**Input sentimiento LLM:** Opinion directa y sin filtro hacia el candidato. Ideal para aprobacion/desaprobacion y deteccion de sarcasmo.

### E13. Quote tweets de publicaciones virales

Buscar citas de los tweets semilla con mayor `quote_count`:

```
quoted_tweet_id:XXXXX lang:es
```

Las citas contienen opinion original + contexto del tweet citado. Son especialmente ricas para deteccion de sarcasmo (la gente cita para burlarse frecuentemente).

**Como estimar costo:** `quote_count` ya esta en disco. Sumar los top N × \$0.005.
**Estimado:** 1,000-4,000 citas → \$5-\$20.
**Input sentimiento LLM:** Sarcasmo y opinion con contexto. Prioridad alta.

### E14. Busqueda de menciones ciudadanas con engagement

Busqueda general de menciones a candidatos desde cuentas no-semilla, con filtro de engagement (T3):

```
(@PalomaValenciaL OR @petrogustavo OR @IvanCepedaCast) lang:es -is:retweet min_faves:20
```

**Como estimar costo:** `count_recent` con la query y umbral → conteo × \$0.005. Ajustar umbral hasta que el costo este en rango aceptable.
**Estimado:** Con min_faves:20, ~2,000-5,000 tweets → \$10-\$25.
**Input THANOS:** Hashtags ciudadanos para `x_{t,h,l}^(k)`. Descubrimiento de hashtags emergentes para E4.

### E15. Recoleccion alineada a fechas de encuestas

Identificar fechas de publicacion de encuestas desde `poll_scraper.py`. Descargar tweets en ventanas de +/- 3 dias alrededor de cada encuesta. Maximiza la correlacion tweet-encuesta que THANOS necesita para calibrar los coeficientes.

**Como estimar costo:** `count_recent` para cada ventana de 6 dias → conteo × \$0.005. Numero de encuestas × costo por ventana.
**Estimado:** ~10 encuestas × 1,000 tweets por ventana = 10,000 tweets → \$50.
**Input THANOS:** Alineacion directa con `y_t`. Fundamental para la regresion.

---

## Fase 3: Expansion de la red via listas curadas (~\$50-\$150)

Estrategias para construir el grafo completo que THANOS necesita para `h_t` (centralidad armonica). En lugar de expansion snowball algoritmica, se usan listas curadas en X: el usuario crea listas privadas agrupando cuentas por rol, y el endpoint `/2/lists/:id/tweets` recolecta todos los tweets en una sola llamada paginada. Esto da costo predecible y curacion semantica de la red.

### E16. Listas curadas por categoria

Crear listas privadas en X con cuentas seleccionadas a partir de los nodos organicos descubiertos en Fase 0 (in_degree de no-semillas) y de las menciones/RT encontrados en Fase 2. Listas propuestas:

| Lista | Contenido | Cuentas estimadas |
|---|---|---|
| Medios | ElTiempo, Semana, ElEspectador, RCN, Caracol, etc. | ~15 |
| Periodistas/analistas | Vicky Davila, Daniel Coronell, Salud Hernandez, Nestor Morales, etc. | ~15 |
| Influencers derecha | Cuentas con alto in_degree mencionadas por semillas de derecha | ~20 |
| Influencers izquierda | Cuentas con alto in_degree mencionadas por semillas de izquierda | ~20 |
| Politicos clave no-candidatos | Congresistas, gobernadores, alcaldes que opinan activamente | ~20 |

Aplicar T4: una sola llamada por lista en vez de N timelines individuales.

**Como estimar costo:** Lookup de las ~90 cuentas (\$0.90) para estimar volumen de tweets desde marzo. Ese conteo × \$0.005.
**Estimado:** 90 cuentas × ~300 tweets = 27,000 tweets → \$135. Con filtro temporal o de engagement se reduce.
**Input THANOS:** `h_t` (centralidad armonica). Las interacciones (menciones, RT, replies) dentro de estos tweets revelan la red ciudadana alrededor de cuentas de elite y conectan los clusters aislados de cada bloque.

### E17. Identificacion de swing users via replies bidireccional

De la estrategia E12 (replies a candidatos), identificar autores que respondieron a candidatos de AMBOS bloques. Estos son votantes indecisos activos. Recolectar sus timelines para analizar hacia donde se inclinan.

**Como estimar costo:** Identificar swing users = gratis (ya estan en los datos de E12). Lookup de los top 100 swing users (\$1.00) para saber cuantos tweets tienen. Ese conteo × \$0.005.
**Estimado:** 100 users × ~200 tweets = 20,000 tweets → \$100. Puede reducirse a top 30 users → \$30.
**Input sentimiento LLM:** Trayectoria de opinion de votantes indecisos. La senal mas directa para predecir movimiento de votos.

---

## Fase 1b: Monitoreo de hashtags con diccionario enriquecido (~\$3/mes)

Se activa despues de las Fases 2 y 3. El diccionario de hashtags ahora incluye hashtags organicos ciudadanos (de Fase 2) y hashtags de coyuntura (de Fase 3), no solo los de propaganda de las semillas.

### E8. Tracking diario de hashtags via count_recent

Correr `count_recent` diariamente para los top 50-80 hashtags del diccionario enriquecido (E1 + E4 + hashtags descubiertos en Fases 2-3). Clasificados por tipo:

- **Campana:** hashtags creados por las campanas oficiales (ej. #PalomaPresidenta)
- **Organicos:** hashtags emergentes de la ciudadania (ej. #ColombiaDespierta)
- **Coyuntura:** hashtags ligados a temas del momento (ej. #ReformaLaboral)

No descarga tweets, solo conteos.

**Costo:** 50 hashtags × \$0.005 = \$0.25/dia = ~\$7.50/mes. Con 30 hashtags = ~\$4.50/mes.
**Como estimar costo:** Fijo, predecible.
**Input THANOS:** Serie temporal de `x_{t,h,l}^(k)` con hashtags que reflejan opinion ciudadana real, no solo propaganda de campana.

---

## Flujo completo del pipeline

```
FASE 0: DATOS EN DISCO (\$0)                    FASE 1a: MONITOREO INMEDIATO (\$2/mes)
                                               (arranque inmediato, sin depender de hashtags)
E1 Diccionario hashtags (inicial) ─────┐        E9 Deteccion picos ──> Calendario
E2 Cadenas retweet ───> r_t^(k)        │        E10 Share of voice ──> Variable extra
E3 Proxy influencia                    │
E4 Co-ocurrencia ──> Clasificador      │
E5 Filtro bots                         │
E6 Controversia ──> Pesos ventanas     │
E7 Estimacion replies ──> Presupuesto  │
                                       │
       │                               │
       v                               v

FASE 2: DESCARGA QUIRURGICA (\$30-\$80)         FASE 3: LISTAS CURADAS (\$50-\$150)
                                               
count_recent (T1)                              Crear listas privadas en X:
       │                                       - Medios (~15 cuentas)
       v                                       - Periodistas/analistas (~15)
E11 Cross-bloque ──────┐                       - Influencers derecha (~20)
E12 Top replies ───────┤                       - Influencers izquierda (~20)
E13 Quote tweets ──────┤                       - Politicos clave (~20)
E14 Menciones eng. ────┤                              │
E15 Alineado encuestas ┤                       E16 Recoleccion via /lists/:id/tweets
       │                                       E17 Swing users (de datos E12)
       v                                              │
Tweets ciudadanos                                     v
       │                                       Grafo expandido
       │                                              │
  ┌────┴────────────────┐                             v
  │         │           │                      h_t (centralidad armonica)
  v         v           v
Hashtags   LLM sent.   Hashtags organicos
nuevos     │           y de coyuntura
  │        │                  │
  v        v                  v

         FASE 1b: MONITOREO HASHTAGS (\$3-\$7/mes)
         (se activa con diccionario enriquecido)

         E8 Tracking diario 50-80 hashtags
         (campana + organicos + coyuntura)
                    │
                    v
         x_{t,h,l}^(k) ponderada por sentimiento
                    │
                    │     r_t^(k)     h_t      y_t (poll_scraper.py)
                    │        │         │           │
                    └────────┴─────────┴───────────┘
                                  │
                                  v
                          THANOS mejorado
                                  │
                                  v
                     Prediccion proporcion votos
```

---

## Protocolo de estimacion de costos

Antes de ejecutar cualquier estrategia de las fases 2 y 3, seguir este protocolo:

### Paso 1: Estimar volumen

```python
from src.twitter_client import get_client

client = get_client()
counts = client.posts.count_recent(
    query="@PalomaValenciaL lang:es -is:retweet",
    granularity="day",
)
# Sumar total_tweet_count de cada dia
```

Costo: \$0.005 por query.

### Paso 2: Calcular costo de descarga

```python
from src.cost_estimator import estimate_search, print_estimate

est = estimate_search(query_count=1, tweets_per_query=total_from_count)
print_estimate(est)
```

### Paso 3: Decidir

- Si costo < presupuesto asignado a la estrategia: ejecutar.
- Si costo > presupuesto: apretar filtros (subir min_faves, reducir ventana) y volver al paso 1.

### Paso 4: Ejecutar con limites

```python
from src.collectors.tweet_collector import search_tweets

results = search_tweets(query, max_pages=N)  # N calculado en paso 2
```

El cache JSONL incremental protege la inversion: si la descarga aborta, lo descargado se preserva.

---

## Resumen de costos por fase

| Fase | Estrategias | Costo | Output principal | Cuando ejecutar |
|---|---|---|---|---|
| 0. Datos en disco | E1-E7 | \$0 | Variables THANOS iniciales, diccionario hashtags, red limpia | Inmediato |
| 1a. Monitoreo inmediato | E9-E10 | ~\$2/mes | Share of voice, calendario de picos | Inmediato (en paralelo con Fase 0) |
| 2. Descarga quirurgica | E11-E15 | \$30-\$80 | Tweets ciudadanos, hashtags organicos, input LLM | Despues de Fase 0 |
| 3. Listas curadas | E16-E17 | \$50-\$150 | Grafo expandido, centralidad armonica, swing users | Despues de Fase 2 |
| 1b. Monitoreo hashtags | E8 | ~\$3-\$7/mes | Serie temporal hashtags enriquecidos (campana + organicos + coyuntura) | Despues de Fases 2-3 |

**Total para modelo THANOS basico (fases 0, 1a, 1b):** ~\$5/mes
**Total para modelo THANOS completo con sentimiento (fases 0-3 + 1b):** ~\$85-\$235 + ~\$5-\$9/mes de monitoreo

---

## Pendientes fuera de este plan

- **LLM inference:** Clasificar ~10,000 tweets tiene su propio costo. Modelo local (Llama/Mistral) = gratis pero lento. Claude API ~\$0.003/tweet = ~\$30 por 10,000 tweets.
- **Validacion del clasificador de sentimiento:** 200-300 tweets etiquetados manualmente como ground truth antes de ponderar THANOS con scores de sentimiento.
- **Otros candidatos:** El config actual solo tiene derecha (Paloma, De La Espriella) e izquierda (Cepeda). Fajardo, Galan y Vargas Lleras estan en `otros_candidatos` sin cuentas semilla. Si la campana se amplia, hay que agregar sus handles.
