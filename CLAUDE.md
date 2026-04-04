# Predicción tendencias Políticas Colombianas de cara a las elecciones de mayo 2026

Quiero realizar un análisis de redes sociales (X y facebook) para identificar las tendencias actuales de quién podrá ganar las elecciones a la presidencia de Colombia del 31 de mayo de 2026

## Metodología de análisis

### Obtención de datos

Inicialmente se va a usar twitter como fuente de datos, ya que tiene la mayor facilidad de obtención de posts. Posteriormente se va a explorar cómo obtener datos de Facebook (mucho más restringido)

### literatura:

Se va a implementar la metodología que desarrolla el modelo de predicción de elecciones usando datos de twitter. Sólo leer los artículos si es necesario. Leer los resumenes en formato markdown primero.

1. THANOS: A Predictive Model of Electoral Campaigns Using Twitter Data and Opinion Polls (Carpeta docs).
   
   - Capítulo relevante el 3.
   
   - articulo original: @docs/THANOS_predictivemodel_electoral_campaigns_using_twitter_data.pd.
   
   - Analizar primero: @docs/resumen_matematico_THANOS_Predictive:Model_Electoral_Campaigns.md

### conexion X API

clave de api en archivo .env
Minimiza las consultas a las APIs. 
Antes de usar una API verificar si los datos ya están en el disco duro. 
Si los datos no se encuentran hacer la descarga y guardar adecuadamente.

## Librerías

Desarrollo en python 3.13

usa Polars en vez de Pandas

Codigo optimizado usando bibliotectas vectoriales. No usar bucles for salvo que sea la única alternativa

Usa uv en vez de pip

## Estandar de código:

Use latest versions of libraries and idiomatic approaches as of today
Keep it simple - NEVER over-engineer, ALWAYS simplify, NO unnecessary defensive programming. No extra features - focus on simplicity.
Be concise. Keep README minimal.

IMPORTANT: no emojis ever






















