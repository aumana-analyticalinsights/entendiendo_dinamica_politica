# Estrategia de analisis: Prediccion elecciones Colombia 2026

## Objetivo

Predecir el resultado de las elecciones presidenciales del 31 de mayo de 2026 usando datos de X (Twitter), siguiendo la metodologia THANOS/THOS.

---

## Modelo teorico de referencia

Se implementa el modelo **THANOS** (Twitter Hashtag and Network-based Opinion Survey). Ver `resumen_matematico_THANOS_Predictive:Model_Electoral_Campaigns.md`.

El modelo predice la proporcion de votos para cada candidato usando dos grupos de variables:

- **Variables de hashtag** `x_{t,h,l}^(k)`: proporcion de los 10 hashtags mas populares del partido k, promediada en ventanas de tiempo (h, l)
- **Variables de red** `h_t`, `r_t^(k)`: centralidad armonica del usuario mas influyente y proporcion de retweets del influenciador principal por partido

La prediccion final promedia estimaciones de multiples ventanas temporales para estabilizar el modelo.

---

## Bloques politicos y cuentas semilla

Se trabaja con dos bloques:

**Derecha** (5 cuentas):
- `@PalomaValenciaL` -- candidata presidencial CD
- `@ABDELAESPRIELLA` -- candidato presidencial MSN
- `@JDOviedoAr` -- candidato a vicepresidencia (formula Paloma Valencia)
- `@CeDemocratico` -- partido Centro Democratico
- `@AlvaroUribeVel` -- expresidente, figura central del bloque

**Izquierda** (4 cuentas):
- `@IvanCepedaCast` -- candidato presidencial PH
- `@petrogustavo` -- presidente, figura central del bloque
- `@PizarroMariaJo` -- lider de izquierda
- `@GustavoBolivar` -- lider de izquierda
- `@PactoHistorico` -- partido politico

---

## Estrategia de recoleccion de datos

### Fuentes de datos (en orden de costo)

**1. Timelines de cuentas semilla**
- Consulta directa a cada cuenta (`GET /users/:id/tweets`)
- Periodo: desde el 13 de marzo 2026 (fecha de inscripcion de candidaturas)
- Limite: 10 paginas por cuenta (1000 tweets max) para controlar costo
- Guardado: `data/raw/seed_timelines_{bloque}.parquet`

**2. Menciones de candidatos principales**
- Busqueda filtrada: `@handle lang:es -is:retweet`
- Excluye retweets para reducir volumen y quedarse con opinion original
- Limite: 5 paginas por candidato (500 tweets max)
- Guardado: `data/raw/mentions_{candidato}.parquet`

**3. Expansion de red (por ejecutar)**
- Para cada cuenta semilla: obtener a quienes siguen
- Filtrar cuentas con >10,000 seguidores (influenciadores verificados)
- De esas cuentas: buscar tweets que usen los hashtags de campana identificados
- Query: `(#hashtag1 OR #hashtag2 OR ...) lang:es -is:retweet`
- Guardado: `data/raw/expanded_network_tweets.parquet`

### Operadores de busqueda relevantes (X API v2)

| Operador | Uso |
|----------|-----|
| `@handle` | Menciones directas al candidato |
| `from:handle` | Tweets propios del candidato |
| `-is:retweet` | Excluir retweets (reduce volumen, captura opinion original) |
| `lang:es` | Solo en espanol |
| `-has:links` | Excluir spam de bots |
| `(#tag1 OR #tag2)` | Busqueda por hashtags de campana |
| `is:quote` | Solo quote tweets (opinion + amplificacion) |

### Mecanismos de proteccion de costo

- **Cache JSONL incremental**: cada pagina del API se escribe a disco inmediatamente en `data/raw/_timeline_{user_id}.jsonl` o `data/raw/_search_{query}.jsonl`. Si la consulta aborta (saldo agotado), lo descargado se preserva.
- **Cache de parquet**: al inicio de cada celda de recoleccion se verifica si el parquet ya existe. Si existe, se carga de disco sin llamar al API.
- **Limite de paginas por defecto**: `DEFAULT_MAX_PAGES = 10`. Se puede subir explicitamente pero nunca queda ilimitado.

---

## Pipeline de analisis

```
Timelines semilla
      +
Menciones candidatos   -->  DataFrame unificado  -->  Top hashtags por bloque
      +                                          -->  Top handles mencionados
Red expandida (hashtags)                         -->  Autores mas activos
                                                 -->  Volumen diario
                                                       |
                                                       v
                                              Variables THANOS/THOS
                                              x_{t,h,l}^(k), h_t, r_t^(k)
                                                       |
                                                       v
                                              Regresion logistica
                                              con multiples ventanas (h,l)
                                                       |
                                                       v
                                              Promedio de predicciones
                                              -> proporcion de votos estimada
```

---

## Estado actual (3 abril 2026)

| Dataset | Estado | Archivo |
|---------|--------|---------|
| Timelines derecha | Completo | `seed_timelines_derecha.parquet` |
| Timelines izquierda | Completo | `seed_timelines_izquierda.parquet` |
| Menciones candidatos | Pendiente | -- |
| Red expandida | Pendiente | -- |

---

## Archivos clave

| Archivo | Descripcion |
|---------|-------------|
| `config/candidates.yaml` | Cuentas semilla por bloque |
| `src/collectors/tweet_collector.py` | Funciones de recoleccion con cache |
| `src/twitter_client.py` | Cliente X API (Bearer Token) |
| `notebooks/snapshot_analisis.ipynb` | Pipeline principal de recoleccion y analisis |
| `data/raw/*.parquet` | Datos crudos por fuente |
| `data/processed/hashtag_rankings.parquet` | Top hashtags (input del modelo) |
| `data/processed/mention_rankings.parquet` | Top handles mencionados |
| `data/processed/author_rankings.parquet` | Ranking de autores por engagement |
