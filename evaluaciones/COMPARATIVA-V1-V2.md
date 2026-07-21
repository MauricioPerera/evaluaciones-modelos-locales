# Comparativa V1 vs V2 — MiniCPM5-1B-Claude-Opus-Fable5-Thinking (Q8_0)

Mismo oráculo congelado (22 ítems, verificado byte-idéntico salvo `config.model`), mismo harness `bench.py`, temperatura 0, misma máquina, misma cuantización Q8_0 (~1,15 GB ambos).

## Precisión

| Categoría | V1 | V2 |
|---|---|---|
| Matemática (8) | 8/8 | 8/8 |
| Coding (5, unit tests) | 5/5 | 5/5 |
| Instruction following (5) | 5/5 | 5/5 |
| Conocimiento MCQ (4) | 3/4 | **4/4** |
| **Global** | **21/22 (95,5%)** | **22/22 (100%)** |

Único ítem que cambió: **k1** (planeta más grande, MCQ). V1 razonó bien pero respondió "J" (inicial de Jupiter); V2 respondió "B" (la letra de opción correcta). El resto de los 21 ítems: idéntico veredicto en ambos.

## Costo de generación (mismo hardware)

| Métrica | V1 | V2 |
|---|---|---|
| tok/s media (mediana) | 48,3 (48,2) | 46,9 (47,2) |
| Tokens generados en los 22 ítems | 2.299 | **5.607 (2,4×)** |
| Wall time total del benchmark | 103,0 s | **181,2 s (1,76×)** |

## Lectura

- **V2 es marginalmente más preciso en este set** (arregla el único fallo de V1, justamente de mapeo respuesta→opción en MCQ), pero la diferencia real es 1 ítem — con 22 casos no da para afirmar superioridad general.
- **V2 piensa mucho más largo**: 2,4× más tokens para las mismas preguntas a temperatura 0, lo que se traduce en ~76% más de latencia total a velocidad por token similar. Para uso interactivo local, V1 es más ágil; V2 gasta más cómputo por respuesta.
- Velocidad por token equivalente (~47-48 tok/s ambos): el peso y la arquitectura son iguales; la diferencia de costo viene solo de la verbosidad del razonamiento.

## Reproducibilidad
- V1: corrida del dev GLM reproducida por el PM de forma independiente (21/22 en ambas).
- V2: corrida única del PM, exit 0, 22/22 ítems calificados.
- Artefactos: `bench_results_v1.json`, `bench_results_v2.json`, `bench.py`, `eval_set.json` (restaurado a V1 tras la corrida).
