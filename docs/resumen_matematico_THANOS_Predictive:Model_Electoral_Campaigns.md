**1. Modelo THOS (Twitter Hashtag based Opinion Survey)** Este es el modelo inicial (Ecuación 3.1), el cual se basa exclusivamente en las frecuencias de los *hashtags* y es adecuado para elecciones donde el margen de victoria es amplio. Su formulación matemática es: log(1−yt​yt​​)=b0​+b1​xt,h,l(1)​+b2​xt,h,l(2)​+b3​xt,h,l(1)​xt,h,l(2)​​+ϵt​

Donde las variables se definen de la siguiente manera:

- yt​: Es la proporción de votos obtenida por el Partido 1 según las encuestas de opinión.
- xt,h,l(k)​: Es la proporción de los 10 *hashtags* más populares correspondientes al Partido k (donde k=1,2), promediada durante el período de tiempo de (t−h) a (t−l).
- h **y** l: Son parámetros temporales que determinan la ventana de tiempo de rezago; indican qué tanta historia pasada se necesita analizar (h) y qué tan a futuro se puede predecir (l), donde h>l.
- b0​,b1​,b2​,b3​: Representan el término de intersección (intercepto) y los coeficientes ponderadores de los respectivos predictores.
- ϵt​: Representa la variable de error en el tiempo t.

Para generar la previsión final, el modelo calcula múltiples predicciones individuales (p^​h,lTH​) utilizando diferentes combinaciones de ventanas de tiempo h y l, y luego **calcula el promedio lineal de todas estas predicciones**. Matemáticamente, esto se expresa como: ph,lTH​=∣(h,l)∣1​∑h,l​p^​h,lTH​ Promediar estas estimaciones estabiliza el predictor y lo protege de los efectos de cambios bruscos o repentinos en los números de las encuestas en puntos de tiempo aislados.

**2. Modelo THANOS (Twitter Hashtag and Network-based Opinion Survey)** Para escenarios electorales más reñidos donde el margen de victoria es estrecho, el modelo THOS resulta inadecuado, por lo que los autores introducen la Ecuación 3.2 que incorpora **características adicionales sobre la estructura de la red de Twitter**. La formulación matemática es: log(1−yt​yt​​)=b0​+b1​xt,h,l(1)​+b2​xt,h,l(2)​+b3​xt,h,l(1)​xt,h,l(2)​​+b4​ht​+b5​rt(1)​+b6​rt(2)​+ϵt​

A las variables ya existentes en la Ecuación 3.1 se le suman nuevos predictores topológicos:

- ht​: Es la **puntuación de Centralidad Armónica** (Harmonic centrality score) del usuario más influyente de toda la red en el tiempo t. Esta métrica es crucial porque captura la efectividad del influenciador principal para impactar a todo el electorado general, incluyendo a los votantes indecisos.
- rt(k)​: Es la **Proporción de Retweets** del usuario más influyente del partido k (para k=1,2) en el tiempo t.
- b4​,b5​,b6​: Son los nuevos coeficientes correspondientes a estas características de red.

Al igual que con el primer modelo, el pronóstico final (previsión THANOS) se obtiene promediando las estimaciones resultantes de las diferentes ventanas de tiempo analizadas: ph,lTHN​=∣(h,l)∣1​∑h,l​p^​h,lTHN​
