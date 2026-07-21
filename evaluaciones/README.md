# Evaluaciones — MiniCPM5-1B-Claude-Opus-Fable5-Thinking (GGUF)

> Repo publicado: [github.com/MauricioPerera/evaluaciones-modelos-locales](https://github.com/MauricioPerera/evaluaciones-modelos-locales)

Jornada de evaluación completa del modelo [`GnLOLot/MiniCPM5-1B-Claude-Opus-Fable5-Thinking-GGUF`](https://huggingface.co/GnLOLot/MiniCPM5-1B-Claude-Opus-Fable5-Thinking-GGUF) (Q8_0, ~1B params) realizada el 2026-07-20. Metodología: PM (Claude) autora oráculos congelados y verifica; implementación delegada a devs GLM-5.2 efímeros; calificación 100% por máquina.

## 1. Análisis del repositorio

| Archivo | Resultado clave |
|---|---|
| [ANALISIS-REPORT.md](ANALISIS-REPORT.md) | Técnicamente coherente (fine-tune de MiniCPM5-1B de OpenBMB, 128K ctx, Apache-2.0), pero procedencia de datos opaca: "Fable 5 traces" nunca definido, "Claude-Opus" solo en el nombre, cero benchmarks publicados. 178k descargas. |

## 2. Benchmark V1 vs V2 (calificación determinista, temperatura 0)

| Archivo | Resultado clave |
|---|---|
| [BENCHMARK-REPORT-v1.md](BENCHMARK-REPORT-v1.md) | V1, 22 ítems: **21/22 (95,5%)**. Único fallo: MCQ respondió "J" (inicial de Jupiter) en vez de la letra "B". ~48 tok/s. |
| [BENCHMARK-REPORT-v2.md](BENCHMARK-REPORT-v2.md) | V2, 22 ítems: **22/22** — pero 2,4× más tokens de razonamiento. |
| [COMPARATIVA-V1-V2.md](COMPARATIVA-V1-V2.md) | 22 ítems: V2 gana por 1 ítem al costo de +76% de latencia. |
| [COMPARATIVA-V1-V2-50.md](COMPARATIVA-V1-V2-50.md) | 50 ítems: **V1 48/50, V2 49/50**. Hallazgo: el fallo "inicial en vez de letra de opción" lo tienen AMBOS (V2 falló k7 con "I" de India). Matemática 15/15 e instrucciones 12/12 en ambos. |
| `eval_set.json` / `eval_set_50.json` | Oráculos congelados (22 y 50 ítems: matemática, coding con unit tests, instruction following, MCQ). |
| `bench.py` | Harness re-ejecutable (requiere Ollama en :11434 con los modelos importados). |
| `bench_results_*.json` | Respuestas crudas y métricas por ítem de las 4 corridas. |

## 3. Experimento KDD (¿sirve como implementador con contrato + tests congelados?)

| Archivo | Resultado clave |
|---|---|
| [KDD-EXPERIMENTO-REPORT.md](KDD-EXPERIMENTO-REPORT.md) | **FAIL ambos** (V1 y V2, 3 lanzamientos, ~15 iteraciones). V1: inmune al feedback de tests (repite el mismo error). V2: no termina de razonar (thinking sin cerrar ni con 16k tokens). Bonus: V2 detectó un bug real del oráculo del PM (8115 → 8130), validando la cláusula de honestidad KDD. El 12/12 en coding del benchmark NO predice capacidad de implementador. |
| `TASK-CONTRACT.md` | Contrato KDD (lint del gate CCDD: PASS). |
| `test_duration.py` | Tests congelados (13 tests, property-test de 200 casos, con fe de erratas aplicada). |
| `delegate_loop.py` | Loop de delegación re-ejecutable (modelo por argv). |

## 4. CTT en micro-expert (¿la memoria compensa el tamaño?)

| Archivo | Resultado clave |
|---|---|
| [CTT-AB-REPORT.md](CTT-AB-REPORT.md) | A/B con 10 hechos ficticios sembrados: **0/10 sin memoria → 6/10 con memoria** (control 2/2). La tesis CTT se sostiene; los fallos eran formato de tool espurio, no recall. |
| `ctt_oracle.json` | Oráculo (hechos "proyecto Aurora" + keywords). |
| `ctt_ab.py` | Harness A/B (requiere micro-expert serve en :3333). |
| `ctt_ab_results.json` | Baseline: respuestas crudas de las 24 evaluaciones. |
| `rag_focused_results.json` | Con `recallTemplate: rag_focused`: 5/10 — no mejora. |
| `fixed_results.json` | Con fix 1 (mandato MCP condicional): 5/10, respuestas ya en lenguaje natural. |
| `builtin_off_run2.json` / `builtin_off_results.txt` | Con fix 1+2 (`builtinTools: false`): 5/10 estable ×2, **cero artefactos de tool en 24 respuestas**. Los ~5/10 restantes son el techo real del 1B en uso de memoria. |

## 5. Retrieval semántico con rag-local (¿el techo era del modelo o del recall?)

| Archivo | Resultado clave |
|---|---|
| [RAG-AB-REPORT.md](RAG-AB-REPORT.md) | Mismo oráculo y modelo, retrieval vía [rag-local](https://github.com/MauricioPerera/rag-local) (embeddinggemma-300m, umbral 0,35 a priori): **10/10** (vs 5-6/10 con RepoMemory) y **0 inyecciones** en preguntas generales — contaminación eliminada ("France → Paris"). Los fallos restantes eran del retrieval, no del modelo. |
| `rag_ab.py` / `rag_ab_results.json` | Harness (requiere rag-local :8937 + llama-server :8940) y respuestas crudas con scores por pregunta. |

## 6. Head-to-head: Ternary Bonsai 27B vs MiniCPM5-1B

| Archivo | Resultado clave |
|---|---|
| [COMPARATIVA-BONSAI-VS-1B.md](COMPARATIVA-BONSAI-VS-1B.md) | Bonsai 27B (2-bit ternario, Vulkan/Arc 140T): **50/50** vs 48-49/50 de los 1B — borra los fallos de MCQ y coding, a 21× el tiempo (95 min vs 4,5). Incluye la lección de despliegue (config correcta = 120× de velocidad) y el desenmascaramiento del drafter DSpark. |
| `bench_bonsai.py` / `bonsai_results_50.json` | Harness OpenAI-transport (incremental, --resume) y respuestas+razonamiento crudos. |

## 7. Bonsai 27B + rag-local (¿el tamaño aporta al caso de uso micro-expert?)

| Archivo | Resultado clave |
|---|---|
| [RAG-BONSAI-REPORT.md](RAG-BONSAI-REPORT.md) | **10/10 — empate perfecto con el 1B** a 19× la latencia (56 s vs 3 s por respuesta). El retrieval hace todo el trabajo en lookup factual: un 1B bien alimentado = un 27B bien alimentado. El 27B solo pagaría en síntesis multi-hecho, MCQ estricto o conocimiento sin memoria. |
| `rag_ab_bonsai.py` / `rag_ab_bonsai_results.json` | Harness adaptado y respuestas crudas. |

## 8. Límite de síntesis multi-hecho del 1B

| Archivo | Resultado clave |
|---|---|
| [SINTESIS-REPORT.md](SINTESIS-REPORT.md) | Con contexto perfecto el 1B SÍ sintetiza: **10/11 (91%)** — joins 4/4 y cadenas A→B→C 3/3; único fallo duro la aritmética implícita ("el puerto siguiente a 7443" → responde 7443 o 4444). Con retrieval real cae a **7/11 (64%)** por dos mecanismos: recall multi-hecho incompleto y ruido de contexto que degrada el razonamiento (a3 pasa con 2 hechos, falla con 5). Modo de fallo peligroso detectado: ante hechos faltantes a veces confabula fusiones ("datacenter named vega") en vez de admitir el hueco. |
| `sintesis_oracle.json` / `sintesis.py` / `sintesis_results.json` | Oráculo de 4 tiers × 2 condiciones (R/O), harness y 28 evaluaciones crudas con atribución retrieval-vs-síntesis. |

## 9. Knowledge contract en rag-local + re-validación de síntesis

| Archivo | Resultado clave |
|---|---|
| [SINTESIS-V2-REPORT.md](SINTESIS-V2-REPORT.md) | Con hechos bajo contrato (absolutos + links) y expansión de 1 salto: **O 14/14 (techo perfecto)** y R 8/11 de síntesis (73%, vs 64% v1) — mejora real pero bajo la predicción de ~90%. El gap restante, descompuesto forensicamente: (1) bug de interfaz umbral/expansión — el engine no expande docs que ya están entre los k crudos sub-umbral y el cliente los descarta (j4: f6 a 0,335 vs umbral 0,35); (2) cadenas de 3 necesitan 2 saltos (ch1); (3) la aritmética del 1B se degrada con ruido (a3: Thursday−72h = "Tuesday" con 6 hechos; correcto con 2). |
| `sintesis_oracle_v2.json` / `sintesis_v2.py` / `sintesis_v2_results.json` | Oráculo re-modelado bajo contrato, harness y 28 evaluaciones crudas. |

Features implementadas en rag-local (rama `feat/knowledge-contract`, 110/110 tests): validación de contrato por colección (reglas `kc-*`: max_chars, anti-referencias-relativas, tags, min_links; persistido dentro del bundle JVSB) + expansión de links opt-in en query. El contrato rechazó en vivo el hecho relacional que causaba el fallo a1.

**Iteración final** (`threshold` server-side + `hops` multi-salto, [PR #1 de rag-local](https://github.com/MauricioPerera/rag-local/pull/1)): **R 10/11 (91%)** — j4 y ch1 resueltos; el único fallo restante es techo del modelo (aritmética con ruido, pasa en condición O). Evidencia: `sintesis_v3_R_results.json`. Trayectoria completa: 64% → 73% → 91% con O en 100%.

**Coda — Bonsai 27B sobre el mismo retrieval final**: **14/14 (100%)**, incluido a3 ("Monday" correcto con el contexto ruidoso donde el 1B dice "Tuesday") — el último 9% es techo de parámetros, no de sistema. Costo: ~93 s por respuesta (vs 3-10 s del 1B). Evidencia: `sintesis_bonsai_R_results.json`. Regla operativa final: 1B para lookup y síntesis simple (91%), Bonsai cuando la síntesis con aritmética debe ser infalible.

## 10. ¿Herramientas? Precisión/recall de invocación — 1B vs Bonsai, tags vs nativo

| Archivo | Resultado clave |
|---|---|
| [TOOLS-AB-REPORT.md](TOOLS-AB-REPORT.md) | 16 ítems (8 tool-apropiados, 8 no) × 3 brazos. **Bonsai: CERO falsos positivos en ambos protocolos (16/16 no_call limpios)** vs 1B con 2/8 FP (inventó `[FETCH:]` a una URL inexistente teniendo el dato en contexto, e inventó un tool `[ROUND:]` que no existe). Recall: Bonsai nativo 6/8 — y los 2 fails son de dialecto de expresión (`sqrt(7396)`, `2^23`: decisión correcta, sintaxis fuera del contrato del calculador), no de juicio. Regla final: **1B responde, Bonsai actúa** — con tools nativos y descripciones que especifiquen el dialecto de expresiones. |
| `tools_oracle.json` / `tools_ab.py` / `tools_ab_results.json` | Oráculo congelado con grading matizado (pass_directo, abstención honesta), harness de 3 brazos y 48 evaluaciones crudas. |

## Código derivado (mergeado en GitHub)

- [PR #4](https://github.com/MauricioPerera/micro-expert/pull/4): gates de tool-format + opción `builtinTools` + 16 tests. **Mergeado.**
- [PR #6](https://github.com/MauricioPerera/micro-expert/pull/6): tests herméticos de agent-loop. **Mergeado** (cierra #5).
- [PR #7](https://github.com/MauricioPerera/micro-expert/pull/7): opción `relevanceThreshold` — inyección de recall gateada por score + 7 tests. **Mergeado** (cierra #3).
- Issues abiertos con diagnóstico: [#1](https://github.com/MauricioPerera/micro-expert/issues/1) (lifecycle `ask`/auto-mining), [#2](https://github.com/MauricioPerera/micro-expert/issues/2) (export pierde memorias).

## Veredicto global del modelo

Bueno para chat/QA local ligero (95-98% en tareas básicas, honesto ante lo que no sabe, ~48 tok/s en CPU); **no apto** como implementador de código con contrato (inmune a feedback / razonamiento que no termina) ni confiable en mapeo a formato MCQ estricto. Como asistente de conocimiento sembrado alcanza **10/10** cuando el retrieval es semántico y con umbral de relevancia (rag-local); los 5-6/10 previos eran techo del recall de RepoMemory, no del modelo.

## Veredicto final: ¿qué modelo para micro-expert?

**MiniCPM5-1B, sin ambigüedad.** La evidencia decisiva: con el retrieval bien hecho (rag-local o `relevanceThreshold` de PR #7), **ambos modelos sacan 10/10** en lookup de conocimiento sembrado — el caso de uso central de micro-expert — y a igualdad de calidad el 1B gana en todo lo demás:

| Criterio (uso micro-expert) | MiniCPM5-1B (Q8) | Bonsai 27B (ternario) |
|---|---|---|
| Lookup factual con buen retrieval | 10/10 | 10/10 (empate) |
| Latencia por respuesta | **~3 s** | ~56 s (19×) |
| RAM residente | **~1,2 GB** | ~7,8 GB |
| Honestidad sin datos | Verificada | Verificada |
| Encaje con la filosofía del framework (sub-1B, edge) | **Exacto** | La excede 4× |
| Stack de despliegue | llama-server estándar | Fork PrismML + Vulkan |

**Cuándo reconsiderar a Bonsai** (queda listo en `C:\models\`): síntesis multi-hecho con razonamiento, MCQ/formato estricto confiable (11/11 vs 10/11), o conocimiento general sin memoria — aceptando ~1 min por respuesta.

**Config recomendada final** (toda medida): micro-expert + MiniCPM5-1B V1 + `builtinTools: false` + `relevanceThreshold` calibrado (o rag-local host-side para retrieval semántico completo) = 10/10 con 0 contaminación a 3 s por respuesta.
