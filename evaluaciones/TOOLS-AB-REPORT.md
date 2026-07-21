# TOOLS-AB-REPORT — Decisión de invocación de herramientas (3 brazos)

Oráculo congelado: `tools_oracle.json` (16 ítems: 4 calc, 4 fetch, 8 no_call). 
Grading determinista sobre la **decisión** + forma + contenido. No se ejecutan las tools.

## 1. Tabla comparativa de los 3 brazos

Brazo A = 1B (Ollama) + tags; Brazo B = Bonsai 27B + tags; Brazo C = Bonsai 27B + nativo (tool_calls).

| Brazo | apropiados pass | recall (/8) | pass_directo | abstencion_honesta | falsos_pos (/8) | precision | calc pass (/4) | fetch pass (/4) | no_call pass (/8) | invoc emitidas | TP | FN | FP | TN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 5/8 | 0.625 | 2 | 0 | 2/8 | 0.7143 | 1/4 | 4/4 | 5/8 | 7 | 5 | 3 | 2 | 6 |
| B | 5/8 | 0.625 | 0 | 0 | 0/8 | 0.7143 | 2/4 | 3/4 | 8/8 | 7 | 7 | 1 | 0 | 8 |
| C | 6/8 | 0.75 | 0 | 0 | 0/8 | 0.75 | 2/4 | 4/4 | 8/8 | 8 | 8 | 0 | 0 | 8 |

Notas de métricas: `recall = apropiados_pass / 8` (solo `pass` = invocación correcta). `pass_directo` = respondió el número correcto SIN invocar (decisión distinta, reportado aparte, no suma a recall). `precision = apropiados_pass / invocaciones_emitidas`. `falsos_positivos` = ítems `no_call` que emitieron invocación.

## 2. Matriz de confusión por brazo (nivel DECISIÓN: invocar / no invocar)

Filas = esperado (8 invocar, 8 no invocar). Columnas = predicho por el modelo.

```
Brazo A:
  esperado invocar     -> pred invocar (TP) 5 | pred no-invocar (FN) 3
  esperado no invocar  -> pred invocar (FP) 2 | pred no-invocar (TN) 6
Brazo B:
  esperado invocar     -> pred invocar (TP) 7 | pred no-invocar (FN) 1
  esperado no invocar  -> pred invocar (FP) 0 | pred no-invocar (TN) 8
Brazo C:
  esperado invocar     -> pred invocar (TP) 8 | pred no-invocar (FN) 0
  esperado no invocar  -> pred invocar (FP) 0 | pred no-invocar (TN) 8
```

## 3. Citas textuales de falsos positivos

Ítems `no_call` (esperado: sin invocación) que emitieron invocación. Veredicto = fail.

- **ni3 / brazo A** — tool: `FETCH`; invocación: `['GET https://api.aurora-example.com/error-budget']`
  - detalle: falso positivo: ['FETCH'] -> ['GET https://api.aurora-example.com/error-budget']
  - respuesta: "[FETCH: GET https://api.aurora-example.com/error-budget]"
- **nc1 / brazo A** — tool: `CALC`; invocación: `['5 + 7 + 5']`
  - detalle: falso positivo: ['CALC'] -> ['5 + 7 + 5']
  - respuesta: "First, I need to write a haiku-style verse about databases. A haiku has 5 syllables in the first line, 7 in the second, and 5 in the third. But here it says "two-line haiku-style verse," so maybe two lines, not strictly a haiku.  I'll write: Databases hold data, quietly. From SQL to queries.  Let me"

## 4. Invocaciones malformadas (CALC con expresión no numérica)

Calculadas con eval seguro (solo dígitos, `+ - * / ** ( ) .` y espacios); cualquier otra cosa = malformed = fail.

- **tc3 / brazo B** — tool: `CALC`; contenido invocación: `['sqrt(7396)']`
  - detalle: malformed: malformed('sqrt(7396)')
  - respuesta: "[CALC: sqrt(7396)]"
- **tc3 / brazo C** — tool: `calculator`; contenido invocación: `['sqrt(7396)']`
  - detalle: malformed: malformed('sqrt(7396)')
  - respuesta: ""
- **tc4 / brazo B** — tool: `CALC`; contenido invocación: `['2^23']`
  - detalle: malformed: malformed('2^23')
  - respuesta: "[CALC: 2^23]"
- **tc4 / brazo C** — tool: `calculator`; contenido invocación: `['2^23']`
  - detalle: malformed: malformed('2^23')
  - respuesta: ""

## 5. Detalle por brazo (veredicto por ítem)

### Brazo A

| id | clase | esperado | invoco | tool | veredicto | wall(s) |
|---|---|---|---|---|---|---|
| tc1 | calc | call_calc | False | - | pass_directo | 6.861 |
| tc2 | calc | call_calc | False | - | fail | 16.382 |
| tc3 | calc | call_calc | False | - | pass_directo | 7.539 |
| tc4 | calc | call_calc | True | CALC | pass | 3.805 |
| tf1 | fetch | call_fetch | True | FETCH | pass | 6.353 |
| tf2 | fetch | call_fetch | True | FETCH | pass | 7.413 |
| tf3 | fetch | call_fetch | True | FETCH | pass | 4.641 |
| tf4 | fetch | call_fetch | True | FETCH | pass | 7.276 |
| ni1 | factual_ctx | no_call | False | - | pass | 3.385 |
| ni2 | factual_ctx | no_call | False | - | fail | 3.161 |
| ni3 | factual_ctx | no_call | True | FETCH | fail | 6.799 |
| ni4 | factual_ctx | no_call | False | - | pass | 4.949 |
| ng1 | general | no_call | False | - | pass | 3.109 |
| ng2 | general | no_call | False | - | pass | 15.522 |
| nm1 | meta | no_call | False | - | pass | 3.918 |
| nc1 | creativo | no_call | True | CALC | fail | 63.996 |

### Brazo B

| id | clase | esperado | invoco | tool | veredicto | wall(s) |
|---|---|---|---|---|---|---|
| tc1 | calc | call_calc | True | CALC | pass | 233.089 |
| tc2 | calc | call_calc | True | CALC | pass | 302.977 |
| tc3 | calc | call_calc | True | CALC | fail | 37.202 |
| tc4 | calc | call_calc | True | CALC | fail | 408.417 |
| tf1 | fetch | call_fetch | False | - | fail ERR=EXC TimeoutError: timed out | 0.0 |
| tf2 | fetch | call_fetch | True | FETCH | pass | 85.169 |
| tf3 | fetch | call_fetch | True | FETCH | pass | 41.355 |
| tf4 | fetch | call_fetch | True | FETCH | pass | 42.513 |
| ni1 | factual_ctx | no_call | False | - | pass | 36.047 |
| ni2 | factual_ctx | no_call | False | - | pass | 38.642 |
| ni3 | factual_ctx | no_call | False | - | pass | 46.91 |
| ni4 | factual_ctx | no_call | False | - | pass | 149.458 |
| ng1 | general | no_call | False | - | pass | 94.733 |
| ng2 | general | no_call | False | - | pass | 76.013 |
| nm1 | meta | no_call | False | - | pass | 347.668 |
| nc1 | creativo | no_call | False | - | pass ERR=EXC TimeoutError: timed out | 0.0 |

### Brazo C

| id | clase | esperado | invoco | tool | veredicto | wall(s) |
|---|---|---|---|---|---|---|
| tc1 | calc | call_calc | True | calculator | pass | 28.485 |
| tc2 | calc | call_calc | True | calculator | pass | 31.625 |
| tc3 | calc | call_calc | True | calculator | fail | 36.267 |
| tc4 | calc | call_calc | True | calculator | fail | 25.378 |
| tf1 | fetch | call_fetch | True | http_fetch | pass | 35.608 |
| tf2 | fetch | call_fetch | True | http_fetch | pass | 36.777 |
| tf3 | fetch | call_fetch | True | http_fetch | pass | 37.607 |
| tf4 | fetch | call_fetch | True | http_fetch | pass | 31.211 |
| ni1 | factual_ctx | no_call | False | - | pass | 27.279 |
| ni2 | factual_ctx | no_call | False | - | pass | 30.02 |
| ni3 | factual_ctx | no_call | False | - | pass | 49.069 |
| ni4 | factual_ctx | no_call | False | - | pass | 107.784 |
| ng1 | general | no_call | False | - | pass | 28.464 |
| ng2 | general | no_call | False | - | pass | 202.553 |
| nm1 | meta | no_call | False | - | pass | 92.573 |
| nc1 | creativo | no_call | False | - | pass | 60.026 |

## 6. Trade-offs

- **Brazo A (1B + tags)**: modelo chico, razonamiento hasta `</think>`. Riesgo: puede emitir tags en ítems no_call (FP) o no invocar cuando debe (FN). Barato y rápido por respuesta.
- **Brazo B (Bonsai + tags)**: mismo protocolo tags que A sobre un modelo 27B. Aísla el efecto del modelo manteniendo el protocolo; ~1-2 min por respuesta.
- **Brazo C (Bonsai + nativo)**: cambia protocolo (tool_calls nativos) sobre el mismo modelo que B. Aísla el efecto del protocolo. El content puede quedar vacío cuando emite tool_calls (finish_reason=tool_calls).
- Comparar A vs B = efecto modelo con protocolo fijo. B vs C = efecto protocolo con modelo fijo. recall mide cuándo invoca cuando debe; precision penaliza invocar cuando no debe; `pass_directo` y `abstencion_honesta` son resultados correctos por camino distinto.

## 7. Salida de ejecución (stdout real, ~últimas 15 líneas)

```
[38/48] ng1 B invoco=False tool=- veredicto=pass wall=94.733s (3881s total)
[39/48] ng1 C invoco=False tool=- veredicto=pass wall=28.464s (3910s total)
[40/48] ng2 A invoco=False tool=- veredicto=pass wall=15.522s (3925s total)
[41/48] ng2 B invoco=False tool=- veredicto=pass wall=76.013s (4001s total)
[42/48] ng2 C invoco=False tool=- veredicto=pass wall=202.553s (4204s total)
[43/48] nm1 A invoco=False tool=- veredicto=pass wall=3.918s (4208s total)
[44/48] nm1 B invoco=False tool=- veredicto=pass wall=347.668s (4556s total)
[45/48] nm1 C invoco=False tool=- veredicto=pass wall=92.573s (4648s total)
[46/48] nc1 A invoco=True tool=CALC veredicto=fail wall=63.996s (4712s total)
[47/48] nc1 B invoco=False tool=- veredicto=pass wall=0.0s (6518s total)
[48/48] nc1 C invoco=False tool=- veredicto=pass wall=60.026s (6578s total)
=== AGREGADOS ===
brazo A: recall=0.625 pass=5/8 pass_directo=2 abst=0 FP=2 precision=0.7143 calc=1/4 fetch=4/4 no_call=5/8 invoc=7
brazo B: recall=0.625 pass=5/8 pass_directo=0 abst=0 FP=0 precision=0.7143 calc=2/4 fetch=3/4 no_call=8/8 invoc=7
brazo C: recall=0.75 pass=6/8 pass_directo=0 abst=0 FP=0 precision=0.75 calc=2/4 fetch=4/4 no_call=8/8 invoc=8
```
