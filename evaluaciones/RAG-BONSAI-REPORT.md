# Bonsai 27B como "micro-expert" con rag-local — mismo protocolo que el 1B

Fecha: 2026-07-21. Arquitectura idéntica al experimento ganador del 1B: retrieval host-side vía rag-local (embeddinggemma-300m, umbral 0,35, k=3), prompt estilo micro-expert sin tools, generación temp 0.7. Mismo oráculo congelado (10 hechos Aurora + 2 control + 2 sondas de contaminación). Bonsai servido con el fork PrismML vía Vulkan (Arc 140T) desde `C:\models\`.

## Resultados

| | MiniCPM5-1B + rag-local | **Bonsai 27B + rag-local** |
|---|---|---|
| Preguntas Aurora (10) | 10/10 | **10/10** |
| Control (2) | 2/2* | 2/2* |
| Sondas de contaminación (2) | 2/2, 0 inyecciones | **2/2, 0 inyecciones** |
| Latencia media por respuesta | ~2-3 s | **~56 s (19×)** |
| Total del experimento | ~1 min | 13,1 min |

\* En ambos casos ctl2 se marca "fail" por el mismo artefacto: el modelo responde "H₂O" con subíndice unicode y el keyword `h2o` no matchea. Respuesta correcta; defecto del oráculo, no del modelo (anotado para futura corrección del keyword a variantes unicode).

## Lectura

1. **Empate perfecto en calidad**: con retrieval semántico + umbral, el 1B y el 27B son indistinguibles en lookup de hechos sembrados (q4: "The Aurora team lead is Ryn Castellanos." — idéntica en espíritu en ambos). El retrieval hace todo el trabajo; el tamaño del modelo no aporta en este caso de uso.
2. **La conclusión de arquitectura se refuerza**: para el caso de uso "asistente local de conocimiento curado" (el nicho micro-expert), invertir en el pipeline de retrieval rinde más que invertir en parámetros. Un 1B bien alimentado = un 27B bien alimentado, a 1/19 de la latencia y 1/6 de la RAM.
3. **Dónde SÍ pagaría el 27B**: preguntas que exigen *sintetizar* varios hechos con razonamiento (no lookup directo), MCQ estricto (11/11 vs 10/11 en el bench de 50), o conocimiento general sin memoria. Para el lookup puro que domina el uso real de micro-expert, es sobredimensionado.
4. Bonsai respondió conciso con contexto inyectado (~56 s incluye su thinking corto); sin contexto (sondas) también fue directo. El modo thinking no se disparó a minutos como en coding — el contexto recuperado le ahorra razonamiento.

## Artefactos
`rag_ab_bonsai.py` (harness adaptado: endpoint :8942, max_tokens 4096), `rag_ab_bonsai_results.json` (respuestas crudas + scores + inyecciones por pregunta). Referencia 1B: `rag_ab_results.json`.
