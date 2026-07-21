# RAG-AB-REPORT — Retrieval + umbral vs. recall nativo de micro-expert

Fecha: 2026-07-20. Servicios verificados vivos: rag-local `:8937`, llama-server (MiniCPM5-1B Q8, `--reasoning off`) `:8940`.
Config: `k=3`, umbral de inyección `score >= 0.35`, `temperature=0.7`, `top_p=0.9`, `max_tokens=512`. Colección `aurora` sembrada con los 10 facts del oráculo (count verificado **== 10**).

## Resumen ejecutivo

| Bucket | Resultado | Detalle |
|---|---|---|
| **Aurora** (recall de facts en memoria) | **10/10** | supera la referencia |
| **Control** (conocimiento nativo, 0 inyección) | 1/2 | fallo por artefacto de grading Unicode, no de retrieval |
| **Sondas de contaminación** (0 inyección esperada) | 2/2 | **0 facts inyectados** en ambos |
| **Inyecciones en no-aurora** | **0** | el umbral filtra correctamente |

**Conclusión:** el retrieval de rag-local + umbral `0.35` mejora al modelo frente al recall nativo. La referencia previa de micro-expert era 5-6/10 en preguntas aurora (con contaminación en preguntas generales). Aquí aurora sube a **10/10** y, crucialmente, las preguntas ajenas al dominio reciben **cero** inyecciones, eliminando la contaminación.

### Comparación contra la referencia previa

| Métrica | Baseline RepoMemory | Post-fixes | **Este experimento (RAG+umbral)** |
|---|---|---|---|
| Aurora | 6/10 (formato corrupto) | 5/10 estable | **10/10** |
| Contaminación en preguntas generales | sí | (parcial) | **ninguna — 0 inyecciones** |
| Separación hecho/irrelevante | no medida | no medida | **hecho 0.75–0.87 vs irrelevante <0.12** |

## Tabla por pregunta

| id | tipo | keyword | pass | facts iny. | score top-1 | wall (s) |
|---|---|---|---|---|---|---|
| q1 | aurora | aurora ship | ✅ | 3 | 0.8377 | 0.836 |
| q2 | aurora | 7443 | ✅ | 3 | 0.8292 | 0.791 |
| q3 | aurora | stormdb | ✅ | 3 | 0.7741 | 1.109 |
| q4 | aurora | castellanos | ✅ | 3 | 0.7551 | 0.753 |
| q5 | aurora | thursday | ✅ | 3 | 0.8332 | 0.709 |
| q6 | aurora | /var/log/aurora | ✅ | 3 | 0.7928 | 0.965 |
| q7 | aurora | staging.aurora-internal.dev | ✅ | 3 | 0.8499 | 0.927 |
| q8 | aurora | flagpole | ✅ | 3 | 0.8508 | 0.846 |
| q9 | aurora | rb-114 | ✅ | 3 | 0.8657 | 0.955 |
| q10 | aurora | borealis | ✅ | 3 | 0.8402 | 0.921 |
| ctl1 | control | 27 | ✅ | 0 | 0.1141 | 0.398 |
| ctl2 | control | h2o | ❌ | 0 | 0.1023 | 0.347 |
| sonda_paris | sonda | paris | ✅ | 0 | 0.1081 | 0.272 |
| sonda_nacl | sonda | nacl | ✅ | 0 | 0.0442 | 0.264 |

Cada pregunta aurora inyectó los 3 hits (`k=3`, los 3 ≥ 0.35). Las 4 preguntas no-aurora inyectaron **0**: todos sus scores quedan bajo 0.12, muy por debajo del umbral 0.35.

## Tabla de scores — separación hecho vs. irrelevante

| bucket | rango score top-1 | ¿inyectado? |
|---|---|---|
| Aurora (q1–q10) | **0.7551 – 0.8657** | sí (todos ≥ 0.35) |
| Control + sondas | **0.0442 – 0.1141** | no (todos < 0.35) |

Brecha mínima entre el peor hit aurora (q4, 0.7551) y el mejor hit no-aurora (ctl1, 0.1141): **~0.64**. El umbral 0.35 cae en una zona despejada del espectro — no hay caso ambiguo. La separación medida en el contexto (~0.76–0.82 para hecho correcto, <0.09 irrelevante) se confirma y aquí los hits correctos llegan a 0.85+.

## REGLA DE ORO — sondas y controles

| id | tipo | facts inyectados | esperado |
|---|---|---|---|
| ctl1 | control | 0 | 0 ✅ |
| ctl2 | control | 0 | 0 ✅ |
| sonda_paris | sonda | 0 | 0 ✅ |
| sonda_nacl | sonda | 0 | 0 ✅ |

**Inyecciones totales en no-aurora: 0.** El umbral funciona: ninguna pregunta fuera del dominio Aurora recibe contexto espurio. Esto ataca directamente el problema de contaminación observado en la referencia.

## Sección de fallos (citas textuales)

Único fallo: **ctl2** — `q="What is the chemical symbol for water?"`, keyword `h2o`.
- Respuesta del assistant: `"H₂O"`
- El modelo acierta el símbolo nativamente (no hubo inyección: scores 0.10/0.08/0.08). El `fail` es **artefacto de grading**: la respuesta usa el carácter Unicode subíndice `₂` (U+2082), por lo que la cadena ASCII `h2o` no aparece como substring. No es un fallo de retrieval ni de conocimiento.
- **No se ajustó el grading** para favorecer el resultado: queda registrado como `fail` honesto, con la causa documentada.

No hubo fallos en preguntas aurora ni en sondas.

## Trade-offs

- **A favor del umbral 0.35:** separación amplia (~0.64) — zona cómoda, robusta a pequeñas derivas del embedding. Cero contaminación en este oráculo.
- **Riesgo del umbral fijo:** este oráculo tiene un dominio muy cohesionado (todo "Aurora") vs. preguntas claramente ajenas. En un dominio más difuso, un umbral 0.35 podría dejar pasar hits边际. Con los scores observados, bajarlo a ~0.20 seguiría sin inducir contaminación aquí; subirlo a ~0.50 seguiría inyectando los 10 aurora. 0.35 es seguro en este experimento, pero no es una recomendación universal — es un dato, no un tuning oculto.
- **k=3 inyecta todo lo que supera el umbral:** en aurora siempre fueron 3/3 porque los 3 vecinos quedan ≥ 0.35. En no-aurora, 0/3. El umbral hace el trabajo de corte; `k` solo acota la búsqueda.
- **Costo:** cada pregunta aurora hace 1 query RAG + 1 call LLM (~0.7–1.1 s de wall por ítem). Sondas/control ~0.3 s (sin inyección, contexto vacío).
- **Grading determinista por substring:** barato y reproducible, pero ciego a variantes tipográficas (Unicode, mayúsculas dentro de fórmulas). ctl2 lo demuestra. Aceptable para un A/B de retrieval; no para evaluación de calidad de respuesta.

## Salida de ejecución (~15 líneas reales de stdout)

```
=== HEALTH ===
rag-local: True | GET http://127.0.0.1:8937/health -> 200 {'ok': True, 'hostConnected': True}
llama-server: True | GET http://127.0.0.1:8940/health -> 200 {'status': 'ok'}
=== SEED ===
[seed] POST /collections aurora (10 docs) -> 200
[seed] count aurora == 10 (esperado 10)
=== EVAL ===
[eval] q1 (aurora) pass=True iny=3 scores=[0.8377, 0.5694, 0.4916] wall=0.836s
[eval] q4 (aurora) pass=True iny=3 scores=[0.7551, 0.5134, 0.4934] wall=0.753s
[eval] q9 (aurora) pass=True iny=3 scores=[0.8657, 0.5025, 0.5011] wall=0.955s
[eval] ctl1 (control) pass=True iny=0 scores=[0.1141, 0.0827, 0.0799] wall=0.398s
[eval] ctl2 (control) pass=False iny=0 scores=[0.1023, 0.0842, 0.0836] wall=0.347s
[eval] sonda_paris (sonda) pass=True iny=0 scores=[0.1081, 0.092, 0.0876] wall=0.272s
[eval] sonda_nacl (sonda) pass=True iny=0 scores=[0.0442, 0.0258, 0.0081] wall=0.264s
=== RESUMEN ===
aurora: 10/10
control: 1/2
sondas: 2/2
inyecciones en no-aurora: 0
count aurora: 10
```

## Evidencia de count == 10

Query `POST /collections/aurora/query` con `k=50` devolvió 10 hits con ids `{f1..f10}`. Muestra pegada (primeros 2 hits, truncado):

```json
[{"id": "f1", "score": 0.6509745778144859, "title": "aurora ship --stage prod", "type": "fact", "tags": [], "description": "The deploy command for project Aurora is: aurora ship --stage prod", "md": "---\\ntype: fact\\ntitle: aurora ship --stage prod\\ndescription: The deploy command for project Aurora is: aurora ship --stage prod\\ntags:\\n  - aurora\\n---\\nThe deploy command for project Aurora is: aurora ship --stage prod\\n"}, {"id": "f3", "score": 0.5712913853315696, "title": "Aurora's primary database is called stormdb and runs Postgre", ...}]
```

`count_aurora == 10` confirmado; aserción `assert count == 10` pasada. Colección `smoke` preexistente ignorada (no se tocó).

## Archivos generados

- `rag_ab.py` — harness (health → seed → eval → JSON).
- `rag_ab_results.json` — 14 evaluaciones + agregados.
- `RAG-AB-REPORT.md` — este reporte.

No se modificó `ctt_oracle.json` ni los directorios `rag-local/`, `micro-expert/`, `kdd-mini/`.