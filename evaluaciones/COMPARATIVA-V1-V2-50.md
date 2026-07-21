# Comparativa ampliada V1 vs V2 — 50 ítems (Q8_0, temperatura 0)

Oráculo ampliado de 22 → 50 ítems (los 22 originales intactos + 28 nuevos de mayor dificultad). Mismo harness `bench.py`, misma máquina, misma cuantización Q8_0.

## Precisión

| Categoría | V1 | V2 |
|---|---|---|
| Matemática (15) | 15/15 | 15/15 |
| Coding (12, unit tests) | 11/12 | **12/12** |
| Instruction following (12) | 12/12 | 12/12 |
| Conocimiento MCQ (11) | 10/11 | 10/11 |
| **Global** | **48/50 (96%)** | **49/50 (98%)** |

## Los 3 ítems donde difieren (todos los demás: pass en ambos)

| Ítem | V1 | V2 | Qué pasó |
|---|---|---|---|
| c10 `word_count` | fail | pass | V1 filtró las palabras no-minúsculas (`if w.islower()`) en vez de normalizarlas con `.lower()` — bug real de lógica; V2 lo hizo bien. |
| k1 planeta más grande (MCQ) | fail | pass | V1 respondió **"J"** (inicial de Jupiter) en vez de "B". Reproduce el fallo del set de 22. |
| k7 país más poblado (MCQ) | pass | fail | V2 respondió **"I"** (inicial de India) en vez de "A". El MISMO modo de fallo que k1 de V1, en otro ítem. |

**Hallazgo clave:** el modo de fallo "inicial de la respuesta en vez de letra de opción" NO está arreglado en V2 — está presente en ambos modelos y aparece de forma inconsistente según el ítem. En ambos casos el modelo sabía la respuesta correcta (el razonamiento lo dice explícito) y falló solo el mapeo al formato MCQ.

## Costo de generación

| Métrica | V1 | V2 |
|---|---|---|
| Tokens generados (50 ítems) | 6.581 | **11.821 (1,8×)** |
| Wall time total | 269 s | **383 s (1,42×)** |
| tok/s media | 48,1 | 48,5 |

## Lectura

- Con 50 ítems la brecha sigue siendo mínima: **1 ítem** (98% vs 96%). La ventaja real de V2 es el fix de c10 (bug de lógica en coding); en MCQ ambos comparten el mismo defecto de formato.
- Matemática 15/15 en ambos (incluye descuento inverso, fracciones, promedio, decimales, edades) e instruction following 12/12 en ambos (JSON anidado con lista incluido) — muy sólido para 1B.
- V2 mantiene su verbosidad: 1,8× tokens y +42% de latencia total para casi el mismo resultado.
- Conclusión: **V2 marginalmente mejor en coding, igual en el resto, más caro de correr.** Para chat/latencia local: V1. Para coding: V2. El claim de la card de V2 ("enhanced tool-calling") no se midió aquí.

## Artefactos
`eval_set_50.json` (oráculo ampliado), `bench_results_v1_50.json`, `bench_results_v2_50.json`, logs `v1-50-run.log` / `v2-50-run.log`. Corridas de 22 ítems previas conservadas (`*_v1.json`, `*_v2.json`).
