# Prediccion tendencias Politicas Colombianas de cara a las elecciones de mayo 2026

Analisis de redes sociales (X y facebook) para predecir quien ganara las elecciones a la presidencia de Colombia del 31 de mayo de 2026.

## Metodologia de analisis

### Modelo teorico: THANOS

Se implementa el modelo THANOS (Twitter Hashtag and Network-based Opinion Survey) que predice proporcion de votos usando:
- `x_{t,h,l}^(k)`: proporcion de top 10 hashtags por partido en ventanas temporales
- `h_t`: centralidad armonica del usuario mas influyente
- `r_t^(k)`: proporcion de retweets del influenciador principal por partido
- `y_t`: datos de encuestas (variable dependiente)

Mejora planificada: ponderar hashtags con score de sentimiento via LLM (-1 a +1) para distinguir apoyo genuino de sarcasmo/critica.

Literatura:
1. THANOS: A Predictive Model of Electoral Campaigns Using Twitter Data and Opinion Polls
   - Capitulo relevante el 3.
   - Articulo original: **docs/THANOS_predictivemodel_electoral_campaigns_using_twitter_data.pdf**
   - Resumen: **docs/resumen_matematico_THANOS_Predictive:Model_Electoral_Campaigns.md**

### Obtencion de datos de Twitter

Plan completo de recoleccion en: **docs/plan_estrategico_obtencion_informacion_tweeter.md**

Principios clave:
- Siempre ejecutar `count_recent` ($0.005) antes de cualquier descarga para estimar costo
- Cache JSONL incremental: cada pagina se escribe a disco inmediatamente
- Cache parquet: verificar si el archivo existe antes de llamar al API
- Clave de API en archivo .env

Bloques politicos y cuentas semilla definidos en `config/candidates.yaml`.

### Encuestas

Scraper automatico desde Wikipedia: `src/collectors/poll_scraper.py`. Datos en `data/processed/encuestas.parquet`.

## Estado actual del proyecto

| Componente | Estado | Ubicacion |
|---|---|---|
| Timelines semilla (derecha + izquierda) | Completo | `data/raw/seed_timelines_*.parquet` |
| Resolucion de user IDs | Completo | `config/candidates.yaml` |
| Scraper de encuestas | Completo | `src/collectors/poll_scraper.py` |
| Analisis de red (grafo de interacciones) | Completo | `data/processed/interaction_edges.parquet`, `interaction_in_degree.parquet` |
| Exportacion Gephi | Completo | `data/processed/red_interacciones.gexf` |
| Recoleccion tweets ciudadanos | Pendiente | Ver plan estrategico |
| Modelo THANOS (regresion) | Pendiente | -- |
| Analisis de sentimiento LLM | Pendiente | -- |

### Diagnostico de red actual

El dataset inicial esta sesgado: las cuentas semilla son emisores y receptores a la vez. La red muestra ecosistemas internos de cada bloque, no conversacion ciudadana. Las fases 2-3 del plan estrategico resuelven esto.

## Documentacion clave

| Documento | Contenido |
|---|---|
| `docs/plan_estrategico_obtencion_informacion_tweeter.md` | Plan completo: 5 tacticas + 18 estrategias en 4 fases, flujo del pipeline, protocolo de costos |
| `docs/resumen_matematico_THANOS_Predictive:Model_Electoral_Campaigns.md` | Formulacion matematica del modelo |

`docs/x_api_knowledge.md`: documentación y referencias de funcionalidad de las API de x.com


## Librerias

Desarrollo en python 3.13

Usa Polars en vez de Pandas

Codigo optimizado usando bibliotecas vectoriales. No usar bucles for salvo que sea la unica alternativa

Usa uv en vez de pip

## Estandar de codigo

Use latest versions of libraries and idiomatic approaches as of today  
Keep it simple - NEVER over-engineer, ALWAYS simplify, NO unnecessary defensive programming. No extra features - focus on simplicity.  
Be concise. Keep README minimal.  
IMPORTANT: no emojis ever






















