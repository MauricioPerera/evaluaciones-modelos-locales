# Evaluaciones — MiniCPM5-1B-Claude-Opus-Fable5-Thinking (GGUF)

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

## Código derivado (mergeado en GitHub)

- [PR #4](https://github.com/MauricioPerera/micro-expert/pull/4): gates de tool-format + opción `builtinTools` + 16 tests. **Mergeado.**
- [PR #6](https://github.com/MauricioPerera/micro-expert/pull/6): tests herméticos de agent-loop. **Mergeado** (cierra #5).
- Issues abiertos con diagnóstico: [#1](https://github.com/MauricioPerera/micro-expert/issues/1) (lifecycle `ask`/auto-mining), [#2](https://github.com/MauricioPerera/micro-expert/issues/2) (export pierde memorias), [#3](https://github.com/MauricioPerera/micro-expert/issues/3) (umbral de relevancia del recall).

## Veredicto global del modelo

Bueno para chat/QA local ligero (95-98% en tareas básicas, honesto ante lo que no sabe, ~48 tok/s en CPU); **no apto** como implementador de código con contrato (inmune a feedback / razonamiento que no termina) ni confiable en mapeo a formato MCQ estricto. Como asistente de conocimiento sembrado alcanza **10/10** cuando el retrieval es semántico y con umbral de relevancia (rag-local); los 5-6/10 previos eran techo del recall de RepoMemory, no del modelo.
