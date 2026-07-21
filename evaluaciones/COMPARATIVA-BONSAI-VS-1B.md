# Ternary Bonsai 27B vs MiniCPM5-1B — mismo oráculo de 50 ítems

Fecha: 2026-07-21. Mismo oráculo congelado (`eval_set_50.json`), misma calificación determinista, temperatura 0 en ambos. Bonsai servido con el fork de PrismML vía **Vulkan sobre Intel Arc 140T** (iGPU) tras corregir la configuración inicial (ver "Lección de despliegue"); el 1B vía Ollama (Q8_0, CPU/GPU estándar).

## Resultados

| Categoría | MiniCPM5-1B V1 | MiniCPM5-1B V2 | **Bonsai 27B (2-bit ternario)** |
|---|---|---|---|
| Matemática (15) | 15/15 | 15/15 | **15/15** |
| Coding (12, unit tests) | 11/12 | 12/12 | **12/12** |
| Instruction following (12) | 12/12 | 12/12 | **12/12** |
| Conocimiento MCQ (11) | 10/11 | 10/11 | **11/11** |
| **Global** | 48/50 | 49/50 | **50/50** |

## Costo

| Métrica | 1B V1 | Bonsai 27B |
|---|---|---|
| Velocidad de generación | ~48 tok/s | ~4,5 tok/s |
| Wall del bench completo | ~4,5 min | **95 min (21×)** |
| RAM/VRAM residente | ~1,2 GB | ~7,8 GB |
| Latencia típica por respuesta (con thinking) | 1-5 s | 1-6 min |

## Lecturas

1. **Bonsai borra las dos clases de fallo del 1B**: el mapeo respuesta→letra en MCQ (11/11; ambos 1B fallaban con "J"/"I") y el bug de lógica en `word_count`. El claim de la card ("95% de la inteligencia FP16 retenida en 1,71 bits/peso") es consistente con lo observado en este set.
2. **El precio es 21× de tiempo**: cada respuesta pensada toma minutos. Para uso interactivo el 1B sigue ganando; Bonsai es para cuando la corrección marginal justifica la espera (razonamiento no trivial, MCQ confiable, código de una pasada).
3. **Advertencia de harness**: 3 ítems de coding fallaron inicialmente por tope de generación (1400 tokens — el thinking de un 27B en coding los consume enteros). Con 6144 pasaron los 3. Al evaluar modelos thinking, el presupuesto de tokens es parte del protocolo, no un detalle.
4. **Este set tiene techo bajo** (dificultad básica-media): 48-50/50 comprime las diferencias reales. En tareas más duras (AIME-style, código multi-archivo) la brecha 27B vs 1B se abriría mucho más de lo que 2 ítems sugieren.

## Lección de despliegue (la config importa 120×)

| Configuración en la misma máquina (Core Ultra 9 285H + Arc 140T) | Generación |
|---|---|
| CPU 16 threads, modelo en HDD USB vía mmap (config ingenua) | 0,037 tok/s |
| CPU 6 P-cores, modelo en NVMe | 2,28 tok/s |
| **Vulkan sobre Arc 140T (`-ngl 99`)** | **4,4-4,5 tok/s** |

En CPUs híbridas (P/E/LP-E cores) los threads de más envenenan los GEMM sincronizados; el mmap desde disco USB es letal; y el build Vulkan del fork corre el formato ternario en la iGPU aunque la card solo publique cifras CUDA/Metal. Dato inédito: la card no publica throughput CPU/Vulkan x86 — estos números lo documentan.

## Nota sobre el drafter DSpark
`Ternary-Bonsai-27B-dspark-Q4_1.gguf` (1,95 GB) NO es un modelo desplegable: es el drafter de speculative decoding (comparte tokenizer/embeddings con el 27B). Evidencia: llama.cpp estándar no lee sus tensores; el fork lo carga y sirve HTTP pero crashea con `GGML_ASSERT: Tokenizer not initialized` al primer prompt. Solo se usa con `-md` junto al modelo principal, y solo rinde en CUDA.

## Artefactos
`bench_bonsai.py` (harness OpenAI-transport con escritura incremental y --resume), `bonsai_results_50.json` (respuestas y razonamiento crudos por ítem). Referencias 1B: `bench_results_v1_50.json` / `bench_results_v2_50.json`.
