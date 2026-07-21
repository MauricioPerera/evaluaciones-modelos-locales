# BENCHMARK-REPORT — minicpm5-fable5-thinking

Fecha de corrida: generada por `bench.py`. Oráculo: `eval_set.json` (congelado).

Modelo: `minicpm5-fable5-thinking` (1B, GGUF Q8_0, razonamiento que termina en `</think>`).

Calificación determinista por máquina, sin juicio de LLM. Temperature=0.


## 1. Resultados por categoría

| Categoría | Aciertos | Total | Porcentaje |
|---|---|---|---|
| math | 8 | 8 | 100.0% |
| coding | 5 | 5 | 100.0% |
| instruction_following | 5 | 5 | 100.0% |
| knowledge | 4 | 4 | 100.0% |
| **GLOBAL** | **22** | **22** | **100.0%** |

## 2. Resultados por ítem

| ID | Categoría | Resultado | Respuesta corta |
|---|---|---|---|
| m1 | math | pass |   408 |
| m2 | math | pass |   563 |
| m3 | math | pass |   14 |
| m4 | math | pass |   36 |
| m5 | math | pass |   12 |
| m6 | math | pass |   12 |
| m7 | math | pass |   81 |
| m8 | math | pass |   150 |
| c1 | coding | pass |   ```python def reverse_string(s):     return s[::-1] ``` |
| c2 | coding | pass |   ```python def is_palindrome(s):     # Convert to lowercase… |
| c3 | coding | pass |   Here's the Python function for FizzBuzz:  ```python def fi… |
| c4 | coding | pass |   ```python def sum_evens(nums):     return sum(num for num … |
| c5 | coding | pass |   ```python def factorial(n):     if not isinstance(n, int) … |
| i1 | instruction_following | pass |   Paris |
| i2 | instruction_following | pass |   {"status": "ok"} |
| i3 | instruction_following | pass |   Apple Banana Orange |
| i4 | instruction_following | pass |   YES |
| i5 | instruction_following | pass |   1,2,3,4,5 |
| k1 | knowledge | pass |   B |
| k2 | knowledge | pass |   A |
| k3 | knowledge | pass |   C |
| k4 | knowledge | pass |   B |

## 3. Métricas de velocidad (tokens/s de generación)

- Tokens/s — media: **46.88** | mediana: **47.16**
- Mínimo: 44.27 tok/s | Máximo: 48.19 tok/s
- Promedio tok/s (agregado global): **46.88**
- Ítems con métrica válida: 22 / 22

## 4. Fallos

Sin fallos.

## 5. Decisiones de interpretación (trade-offs)

- **math**: se extrae el último número de la respuesta con regex `[-+]?\d{1,3}(?:,\d{3})+... | [-+]?\d+\.\d+ | [-+]?\d+`; las comas se tratan como separadores de miles (se eliminan) y el punto como decimal. Comparación numérica con tolerancia 1e-6.
- **coding**: se toma el primer bloque dentro de fences ``` (con o sin etiqueta `python`); si no hay fences se usa el texto entero. El código se ejecuta en un subproceso `python` separado con timeout 10s junto con los asserts; pass = exit 0. Nunca se ejecuta código en el proceso principal.
- **knowledge**: primera letra A–D que aparezca *standalone* (no adyacente a otras letras), mayúscula o minúscula, admitiendo paréntesis o punto alrededor. Esto evita falsos positivos de letras dentro de palabras (p.ej. la 'a' de 'Mars').
- **instruction_following / one_word_equals**: se quita puntuación final (.,;:!?) y se exige una sola palabra (sin espacios internos).
- **instruction_following / n_nonempty_lines**: se rechazan líneas que inicien con `dígito+.` , `-` o `*` (marcadores de lista).
- **instruction_following / json_equals**: se recorta al primer `{` y último `}` antes de parsear.
- **tokens/s**: `eval_count / (eval_duration/1e9)` (Ollama reporta `eval_duration` en ns). Promedio global calculado sobre ítems con métrica válida (excluye errores de request).

## 6. Salida de ejecución

Últimas ~20 líneas reales de stdout de la corrida:

```
[i1] llamando Ollama...
[i1] pass | tok/s=48.16819669898366 | wall=3.21s | eval_count=29
[i2] llamando Ollama...
[i2] pass | tok/s=47.653282342203305 | wall=5.76s | eval_count=150
[i3] llamando Ollama...
[i3] pass | tok/s=47.17020821439854 | wall=6.48s | eval_count=185
[i4] llamando Ollama...
[i4] pass | tok/s=46.97782516158414 | wall=4.06s | eval_count=72
[i5] llamando Ollama...
[i5] pass | tok/s=46.72424728003603 | wall=7.59s | eval_count=244

--- knowledge (4 items) ---
[k1] llamando Ollama...
[k1] pass | tok/s=45.43017365036109 | wall=8.43s | eval_count=263
[k2] llamando Ollama...
[k2] pass | tok/s=45.81668236312266 | wall=4.57s | eval_count=90
[k3] llamando Ollama...
[k3] pass | tok/s=46.164479488991724 | wall=4.11s | eval_count=71
[k4] llamando Ollama...
[k4] pass | tok/s=45.97949314605686 | wall=4.64s | eval_count=92
```
