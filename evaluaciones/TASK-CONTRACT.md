---
task: parse-duration-to-seconds
intent: Convertir una duración textual compacta tipo "2h15m30s" (=8130 s) a segundos totales
language: python
target: duration.py
signature: "def parse_duration(s: str) -> int"
tests: test_duration.py
test_command: "python -m unittest test_duration -v"
deps_allowed: []
forbids:
  - "modificar test_duration.py"
  - "imports fuera de la stdlib"
budget:
  cyclomatic: 10
  nesting: 3
  params: 1
  lines: 40
---

## Intent
Convertir una cadena de duración compacta con unidades h/m/s (p.ej. "2h15m30s", "1h30m", "90s") a la cantidad total de segundos como entero.

## Interface
`def parse_duration(s: str) -> int` en `duration.py`. Recibe una cadena de duración compacta con unidades `h`, `m`, `s` y devuelve el total de segundos como entero.

## Invariants
- Retorno = horas*3600 + minutos*60 + segundos, siempre `int` >= 0.
- Unidades opcionales pero en orden estricto h → m → s, cada una a lo sumo una vez, al menos una presente.
- Cada unidad va precedida de un entero decimal no negativo (uno o más dígitos).
- Entrada inválida (cadena vacía, caracteres extraños, orden incorrecto, unidad repetida, unidad sin número) → `ValueError`. Nunca retorna None ni un valor parcial.

## Examples
- "1h" → 3600
- "45m" → 2700
- "90s" → 90
- "2h15m30s" → 8130
- "1h30m" → 5400
- "10m5s" → 605
- "0s" → 0
- "" → ValueError
- "abc" → ValueError
- "h1" → ValueError
- "30s2h" → ValueError
- "1h2h" → ValueError

## Do / Don't
- Do: usar solo la stdlib de Python (re está permitido).
- Do: validar la entrada completa antes de computar.
- Don't: no modificar `test_duration.py` (tests congelados).
- Don't: no imprimir, no leer stdin, no tocar archivos.
- Don't: no agregar más funciones públicas que `parse_duration` (helpers privados _foo permitidos dentro del budget).

## Tests
Tests congelados en `test_duration.py` (mismo directorio). Se ejecutan con `python -m unittest test_duration -v`. Incluyen casos unitarios, un property-test de 200 composiciones aleatorias con oráculo independiente, y casos de error con `assertRaises(ValueError)`. Prohibido editarlos.

## Constraints
- Budget firmado: cyclomatic ≤ 10, nesting ≤ 3, params ≤ 1, lines ≤ 40 (verificable con measure_complexity).
- PARAR y reportar si los tests congelados contradicen esta especificación, si el budget resulta imposible de cumplir, o si se necesita una dependencia fuera de la stdlib.
