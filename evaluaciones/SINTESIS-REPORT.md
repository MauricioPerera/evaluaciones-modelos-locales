# SINTESIS-REPORT — Límite de síntesis multi-hecho del 1B (MiniCPM5-1B)

Medición del límite de síntesis multi-hecho del modelo `minicpm5-fable5-thinking` (MiniCPM5-1B) servido por
Ollama, usando RAG-local (colección `aurora2`, 14 facts del oráculo congelado) y dos condiciones por
pregunta: **R** (retrieval real, k=5, umbral 0.35) y **O** (contexto oráculo: exactamente los
`needed_facts`, sin retrieval). 14 preguntas × 2 condiciones = **28 evaluaciones**, ninguna omitida.

`python sintesis.py` → **exit 0**. `count aurora2 == 14` (verificado). Los agregados de este reporte son
idénticos a `sintesis_results.json` (verificado por recomputación: `INTEGRITY_OK`).

## Decisiones de diseño (trade-offs)

- **`temperature: 0`**: se mide *capacidad* de síntesis, no adherencia a un protocolo previo; se anula el
  ruido del muestreo. Anotado como decisión, no como ajuste posterior a los resultados.
- **Delimitador de respuesta**: el spec decía razonamiento terminando en `'VIOUS'`; el modelo real emite un
  tag de cierre de razonamiento (construido vía `chr(60)+"/think"+chr(62)` para evitar filtrado de tokens
  especiales en el pipeline). Se extrae la respuesta tras la última ocurrencia de ese tag; si no aparece, se
  cae a `'VIOUS'` y luego a la respuesta cruda. El **último número** extraído coincide en ambos caminos, así
  que `expected_number` es robusto independientemente del delimitador.
- **`keywords_all` sobre el texto final** (post-reasoning), consistente con `expected_number` (que también
  opera post-reasoning). Mide si el modelo *produce* la respuesta, no si la menciona en el razonamiento.
- **`count` vía query k=50** (ids distintos): el endpoint `GET /collections` lista nombres pero no devuelve
  conteo por colección, así que se cuenta con una consulta de amplio espectro. Evidencia cruda guardada en
  `count_evidence`. Asumido como proxy válido (los 14 ids `f1..f14` aparecen).
- **Umbral 0.35 y grading NO ajustados tras ver resultados** (regla del oráculo congelado). Si algo da mal,
  ese es el hallazgo.
- **R puede inyectar facts extra ruidosos** (hasta k=5) incluso cuando `retrieval_completo=True`. Eso es parte
  de lo que se mide: ruido de contexto vs. contexto oráculo limpio.

## Tabla tier × condición (aciertos)

| Tier | R (retrieval) | O (oráculo) |
|---|---|---|
| control (3) | 3/3 (100%) | 3/3 (100%) |
| join (4) | 3/4 (75%) | 4/4 (100%) |
| aritmetica (4) | 2/4 (50%) | 3/4 (75%) |
| cadena (3) | 2/3 (66.7%) | 3/3 (100%) |
| **Total (14)** | **10/14 (71.4%)** | **13/14 (92.9%)** |

La brecha R−O (71.4% vs 92.9%) aísla dos efectos: (a) retrieval incompleto y (b) ruido de contexto extra.
El único fallo en O es aritmético (`a1`): ni con contexto perfecto el 1B hace el `+1`.

## Controles como línea base

Los 3 controles (hecho único, sin síntesis) pasan en **ambas** condiciones (3/3 R, 3/3 O). Esto valida el
pipeline end-to-end (retrieval → contexto → LLM → grading) y confirma que los fallos en tiers superiores son
de **síntesis**, no de infraestructura.

## Atribución de fallos (retrieval vs. síntesis)

| Categoría | Cuenta | Ítems |
|---|---|---|
| Éxito | 23 | (evaluaciones que pasaron) |
| Fallo de **retrieval** (R, contexto incompleto) | 2 | `j4`, `ch1` |
| Fallo de **síntesis** en R (retrieval completo) | 2 | `a1`, `a3` |
| Fallo de **síntesis** en O (contexto oráculo) | 1 | `a1` |
| **Total fallos** | **5** | |

Lectura:
- **Fallo de retrieval** (2): `j4` y `ch1` sólo recuperaron `f5`; `f6` ("vega mounted in rack R2") quedó bajo
  umbral (score 0.331 < 0.35). El modelo respondió con lo que tenía ("rack unspecified", "datacenter vega").
  Ambas pasan en O → el modelo sí sintetiza cuando tiene los facts.
- **Fallo de síntesis en R** (2, retrieval completo): `a1` y `a3` tenían todos los `needed_facts` en contexto
  y aún fallaron. Aquí el límite es del modelo, no del retrieval.
- **Fallo de síntesis en O** (1): `a1` con contexto oráculo exacto `f1+f2` falló. Este es el hallazgo más
  fuerte: el 1B no hace la aritmética `+1` ni con contexto perfecto.

## Citas textuales de los fallos de síntesis más ilustrativos

### `a1` (puerto de metrics = 7444) — fallo en AMBAS condiciones

Esperado `7444` (gateway 7443 + 1, f2+f1). Needed facts inyectados en ambos casos.

- **O (oráculo, contexto exacto `f1`+`f2`)** → respondió `7443`. Razonamiento textual:
  > "I recall from the previous context that the Aurora API gateway listens on port 7443, and the Aurora
  > metrics service should also be listening on the same port. Therefore, the answer is 7443."

  El modelo lee "the port number immediately after the API gateway port" pero concluye que es el *mismo*
  puerto. **No aplica el `+1` aunque tiene ambos facts.**

- **R (retrieval completo `f2`,`f1`+ruido)** → respondió `4444`. Razonamiento textual:
  > "I recall from the given facts that the Aurora metrics service listens on port 4444, which is immediately
  > after the API gateway port (7443). So the answer is 4444."

  Alucina `4444` (descarta el `7` inicial) y lo justifica circularmente. Mismo fallo de síntesis, agravado
  por ruido.

### `a3` (día de la semana del code freeze = Monday) — fallo de síntesis en R, éxito en O

Esperado keyword `monday` (release every 2nd Thursday `f3`, freeze 3 días antes `f4`).

- **R (retrieval completo `f4`,`f3`+ruido `f12`,`f10`,`f9`)** → respondió:
  > "We do not know for sure; it is 3 days before the production release, which could be any day of the week
  > depending on when that Thursday occurs."

  El modelo **se rehúsa a sintetizar** Thursday − 3 días = Monday. Notable: la **misma pregunta en O**
  (contexto limpio `f3`+`f4`, sin facts extra) **sí** la responde: *"The code freeze begins on a Monday."*
  El ruido de contexto extra en R (con `retrieval_completo=True`) degradó la síntesis respecto a O.

## Salida de ejecución (~15 líneas reales de stdout, de `tmp_sintesis_run.log`)

```
[health] rag-local: True | GET /collections -> 200 ['aurora', 'smoke']
[health] ollama:    True | POST /api/generate -> 200 {'model': 'minicpm5-fable5-thinking', ...
[seed] DELETE /collections/aurora2 -> 502 {'error': 'La colección no existe: "aurora2"'}
[seed] POST /collections aurora2 (14 docs) -> 200
[seed] count aurora2 == 14 (esperado 14)

=== c1 (tier=control) ===
  [R] pass | inyectados=['f1', 'f2', 'f10', 'f9', 'f13'] | retr_compl=True | wall=4.2s | final='7443'
  [O] pass | inyectados=['f1'] | retr_compl=None | wall=3.5s | final='7443'

=== c2 (tier=control) ===
  [R] pass | inyectados=['f8', 'f10', 'f11', 'f3', 'f4'] | retr_compl=True | wall=3.9s | final='The Aurora team lead is Ryn Castellanos.'
  [O] pass | inyectados=['f8'] | retr_compl=None | wall=3.6s | final='The Aurora team lead is Ryn Castellanos.'

=== c3 (tier=control) ===
  [R] pass | inyectados=['f13', 'f14', 'f4', 'f3', 'f9'] | retr_compl=True | wall=4.0s | final='43'
  [O] pass | inyectados=['f13'] | retr_compl=None | wall=3.8s | final='43'
```

Resumen final del run: `cond R: 10/14 (71.4%)`, `cond O: 13/14 (92.9%)`,
`atribucion: {retrieval_fail: 2, sintesis_fail_R: 2, sintesis_fail_O: 1, success: 23}`.

## Conclusión

- **Línea base (control): 100%** en ambas condiciones — el pipeline funciona.
- **Join/cadena**: el 1B sintetiza 2-3 facts cuando el retrieval es completo; sus 2 fallos R son de
  *retrieval* (no de síntesis), confirmado porque ambos pasan en O.
- **Aritmética es el límite duro**: 50% R / 75% O. El fallo `a1` en O (contexto perfecto) muestra que el 1B
  **no opera aritmética simbólica simple** (`+1`) sobre facts leídos; `a3` R muestra que el **ruido de
  contexto extra** lo empuja a rehusar incluso con los facts correctos presentes.
- La brecha R−O (−21.5 pp) se descompone en: 2 fallos atribuibles a retrieval y 1 fallo de síntesis que
  aparece *sólo* en R (`a3`) por ruido — el resto del gap se explica porque O elimina tanto fallos de
  retrieval como degradación por contexto ruidoso.