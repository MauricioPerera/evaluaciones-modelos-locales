# Experimento KDD — MiniCPM5-1B Fable5 V1 y V2 como implementadores — VEREDICTO FINAL: AMBOS FAIL

## Setup
Flujo KDD/CCDD: PM (Claude) autora task-contract (validado por `lint_task_contract` del gate real: `ok: true`) + 13 property-tests congelados; implementador = modelo local vía API de Ollama, temperatura 0, máx 3 iteraciones por lanzamiento con la salida real de los tests como feedback; veredicto determinista.

Tarea atómica: `def parse_duration(s: str) -> int` — "2h15m30s" → 8130 s, orden estricto h→m→s, `ValueError` en inválidos. Budget: cyclomatic≤10, nesting≤3, params≤1, lines≤40.

## Fe de erratas del PM (importante)
El oráculo original tenía un bug MÍO: `test_full_combo` esperaba 8115 en vez de **8130** (7200+900+30), contradiciendo al property-test. Lo detectó **V2 en su razonamiento** ("the example says 8115, maybe the example is wrong") y lo confirmó un intento de V1 que produjo 8130 y fue rechazado injustamente. Se corrigió el test y el contrato, y TODOS los veredictos finales de abajo son contra el oráculo corregido. Lección KDD confirmada: la cláusula "PARAR si los tests contradicen la spec" funciona incluso con implementadores de 1B — y el bug del oráculo era del PM, no del gate ni del dev.

## Resultados finales (oráculo corregido)

| Corrida | V1 | V2 |
|---|---|---|
| Sin hint (3 iteraciones) | FAIL — 8 errores idénticos ×3, cero progreso con feedback | FAIL — **nunca emitió código**: thinking sin cerrar ni con 16.384 tokens de presupuesto, ×3 |
| Con hint (regex exacta de la solución) | FAIL — 5 errores ×3: usó la regex pero omitió el `?` del grupo `s` y los `or 0` que el hint daba textualmente | FAIL — 1 iteración sin código; las otras dos con código peor que el hint (regex sin las letras de unidad); 5 y luego 8 errores |

Ajustes de harness durante el experimento (documentados, no alteran el gate): presupuesto de generación 2048→6144→16384 tokens, timeout de request 300→900 s, extracción estricta de código con feedback de formato.

## Diagnóstico comparativo

- **V1**: emite código consistentemente, pero es inmune al feedback — repite el mismo error estructural en todas las iteraciones de todos los lanzamientos, incluso con el `TypeError` textual y la solución literal en el prompt.
- **V2**: su modo de fallo dominante es **no terminar de pensar**: en 4 de 6 iteraciones sin/con poco hint quemó todo el presupuesto dentro del bloque thinking sin emitir código (consistente con el 1,8× de verbosidad medido en el benchmark). Cuando emite, no es mejor que V1. Único punto a favor: detectó el bug del oráculo del PM.
- **Contraste con el benchmark (12/12 coding ambos)**: aquellas eran funciones de 3-5 líneas con 3 asserts; un contrato con validación estricta, unidades opcionales y casos de error excede a ambos. El benchmark de funciones simples NO predice capacidad de implementador KDD.
- **El flujo KDD quedó validado**: lint determinista cazó formato de contrato, los tests congelados cazaron cada implementación rota, el property-test destapó (vía el dev) un bug del propio oráculo, y no hubo ni un falso PASS en ~15 iteraciones de implementación.

## Recomendación
Ninguno de los dos sirve como implementador KDD. Para devs baratos del pipeline: GLM-5.2 (verificado en esta sesión) o Haiku 4.5 como piso. Estos 1B quedan para chat/QA local ligero.

## Artefactos (`kdd-mini/`)
`TASK-CONTRACT.md` (corregido, lint PASS), `test_duration.py` (congelados, corregidos con fe de erratas), `delegate_loop.py` (harness re-ejecutable, modelo por argv), logs completos: `loop2/3.log` (V1 pre-corrección), `loop-v1-fixed.log`, `loop-v1-hint-fixed.log`, `loop-v2-fixed.log`, `loop-v2-hint-fixed.log`.
