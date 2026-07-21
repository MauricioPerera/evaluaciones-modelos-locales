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
| knowledge | 3 | 4 | 75.0% |
| **GLOBAL** | **21** | **22** | **95.45%** |

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
| c2 | coding | pass |   ```python def is_palindrome(s):     s_lower = s.lower()   … |
| c3 | coding | pass |   ```python def fizzbuzz(n):     result = []     for i in ra… |
| c4 | coding | pass |   ```python def sum_evens(nums):     return sum(num for num … |
| c5 | coding | pass |   ```python def factorial(n):     result = 1     for i in ra… |
| i1 | instruction_following | pass |   Paris |
| i2 | instruction_following | pass |   {"status": "ok"} |
| i3 | instruction_following | pass |   apple   banana   orange |
| i4 | instruction_following | pass |   YES |
| i5 | instruction_following | pass |   1,2,3,4,5 |
| k1 | knowledge | fail |   J |
| k2 | knowledge | pass |   A |
| k3 | knowledge | pass |   C |
| k4 | knowledge | pass |   B |

## 3. Métricas de velocidad (tokens/s de generación)

- Tokens/s — media: **48.29** | mediana: **48.21**
- Mínimo: 45.88 tok/s | Máximo: 51.28 tok/s
- Promedio tok/s (agregado global): **48.29**
- Ítems con métrica válida: 22 / 22

## 4. Fallos


### k1 (knowledge) — fail
- Esperado: `"B"`
- Detalle: sin letra A-D
- Respuesta calificada (textual, truncada 300):
```


J
```

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
[i1] pass | tok/s=46.93282625694814 | wall=3.80s | eval_count=62
[i2] llamando Ollama...
[i2] pass | tok/s=48.139636002236166 | wall=5.20s | eval_count=124
[i3] llamando Ollama...
[i3] pass | tok/s=48.28653151760767 | wall=5.25s | eval_count=127
[i4] llamando Ollama...
[i4] pass | tok/s=48.317098213130166 | wall=3.01s | eval_count=28
[i5] llamando Ollama...
[i5] pass | tok/s=48.59014215095668 | wall=3.47s | eval_count=49

--- knowledge (4 items) ---
[k1] llamando Ollama...
[k1] fail | tok/s=47.47933110414943 | wall=3.62s | eval_count=54
[k2] llamando Ollama...
[k2] pass | tok/s=48.073297223965554 | wall=4.75s | eval_count=109
[k3] llamando Ollama...
[k3] pass | tok/s=49.63824684638406 | wall=4.21s | eval_count=86
[k4] llamando Ollama...
[k4] pass | tok/s=48.08920547615828 | wall=3.83s | eval_count=64
```
