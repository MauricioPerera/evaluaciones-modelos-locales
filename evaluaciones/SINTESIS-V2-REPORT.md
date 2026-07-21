# SINTESIS-V2-REPORT — límite de síntesis multi-hecho del 1B sobre aurora3 (knowledge contract)

Misma medición que `sintesis.py` (mismas 14 preguntas congeladas de `sintesis_oracle.json`, mismo grading, mismas condiciones R/O, mismo system prompt y options temp 0 / top_p 1.0 / num_predict 1024) sobre la colección **aurora3**, creada con el **knowledge contract** de `sintesis_oracle_v2.json` y los **facts_md** re-modelados. Cambios: hechos absolutos con links markdown, `f2` absoluto (port 7444), `f4` en horas, `needed_facts` de **a1** = `[f2]` (override del oráculo v2). En condición R se usa `expand_links:true`; el umbral 0.35 se aplica **solo** a hits normales y los docs `expanded=true` se inyectan **siempre**. En ambas condiciones los links markdown se renderizan a texto plano al armar `Facts from memory:`.

- Colección: `aurora3` — count=14 (create.count=14), esperado 14.
- Contract: max_chars=200, forbid_relative=true, allowed_tags=['aurora2', 'infra', 'people', 'process'], min_links=0. Creación **no rechazada** por el contrato.
- Condición R global: **11/14 (78.6%)**  |  v1: 10/14 (71.4%)
- Condición O global: **14/14 (100.0%)**  |  v1: 13/14 (92.9%)

## Tabla tier × condición — v1 vs v2 (lado a lado)

Números v1 leídos de `sintesis_results.json` (no inventados).

| Tier | Cond | v1 pass/total (pct) | v2 pass/total (pct) | Δ pct | v1 ids-fail | v2 ids-fail |
|------|------|---------------------|---------------------|-------|-------------|-------------|
| control | R | 3/3 (100.0%) | 3/3 (100.0%) | +0.0 | — | — |
| control | O | 3/3 (100.0%) | 3/3 (100.0%) | +0.0 | — | — |
| join | R | 3/4 (75.0%) | 3/4 (75.0%) | +0.0 | j4 | j4 |
| join | O | 4/4 (100.0%) | 4/4 (100.0%) | +0.0 | — | — |
| aritmetica | R | 2/4 (50.0%) | 3/4 (75.0%) | +25.0 | a1, a3 | a3 |
| aritmetica | O | 3/4 (75.0%) | 4/4 (100.0%) | +25.0 | a1 | — |
| cadena | R | 2/3 (66.7%) | 2/3 (66.7%) | +0.0 | ch1 | ch1 |
| cadena | O | 3/3 (100.0%) | 3/3 (100.0%) | +0.0 | — | — |

## Atribución de fallos (v2)

- retrieval_fail (R, faltó algún needed): 2 — ['j4', 'ch1']
- sintesis_fail_R (R, needed completo, no sintetizó): 1 — ['a3']
- sintesis_fail_O (O, contexto oráculo, no sintetizó): 0 — —
- success: 25

Atribución v1 (referencia): retrieval_fail=2, sintesis_fail_R=2, sintesis_fail_O=1, success=23

## Cambios notables (v1 → v2)

### a1 [R]  (tier=aritmetica)

- v1: **fail** | inyectados=['f2', 'f1', 'f10', 'f9', 'f13'] | retr_compl=True | final='4444'
- v2: **pass** | inyectados=['f2', 'f1', 'f9', 'f13', 'f10', 'f8'] | expandidos=['f8'] | retr_compl=True | final='7444'
- needed: v1=['f2', 'f1'] → v2=['f2']

### a1 [O]  (tier=aritmetica)

- v1: **fail** | inyectados=['f2', 'f1'] | retr_compl=None | final='7443'
- v2: **pass** | inyectados=['f2'] | expandidos=[] | retr_compl=None | final='7444'
- needed: v1=['f2', 'f1'] → v2=['f2']

### ch1 [R]  (tier=cadena)

- v1: **fail** | inyectados=['f5'] | retr_compl=False | final='The stormdb database is located in the datacenter named "vega".'
- v2: **fail** | inyectados=['f5', 'f6'] | expandidos=['f6'] | retr_compl=False | final='The stormdb database is located in datacenter R2.'
- needed: v1=['f5', 'f6', 'f7'] → v2=['f5', 'f6', 'f7']

### ch1 [O]  (tier=cadena)

- v1: **pass** | inyectados=['f5', 'f6', 'f7'] | retr_compl=None | final='The stormdb database is located in the Quito datacenter.'
- v2: **pass** | inyectados=['f5', 'f6', 'f7'] | expandidos=[] | retr_compl=None | final='The stormdb database is located in the Quito datacenter.'
- needed: v1=['f5', 'f6', 'f7'] → v2=['f5', 'f6', 'f7']

### j4 [R]  (tier=join)

- v1: **fail** | inyectados=['f5'] | retr_compl=False | final='The stormdb database runs on host **vega** and in an unspecified rack.'
- v2: **fail** | inyectados=['f5'] | expandidos=[] | retr_compl=False | final='The stormdb database runs on host **vega** and in an unspecified rack.'
- needed: v1=['f5', 'f6'] → v2=['f5', 'f6']

### j4 [O]  (tier=join)

- v1: **pass** | inyectados=['f5', 'f6'] | retr_compl=None | final='The stormdb database runs on the host **vega** in rack **R2**.'
- v2: **pass** | inyectados=['f5', 'f6'] | expandidos=[] | retr_compl=None | final='The stormdb database runs on the host **vega** in rack **R2**.'
- needed: v1=['f5', 'f6'] → v2=['f5', 'f6']

### a3 [R]  (tier=aritmetica)

- v1: **fail** | inyectados=['f4', 'f12', 'f3', 'f10', 'f9'] | retr_compl=True | final='We do not know for sure; it is 3 days before the production release, which could be any da'
- v2: **fail** | inyectados=['f4', 'f12', 'f3', 'f10', 'f9', 'f8'] | expandidos=['f8'] | retr_compl=True | final='The Aurora code freeze begins on a Tuesday.'
- needed: v1=['f3', 'f4'] → v2=['f3', 'f4']

### a3 [O]  (tier=aritmetica)

- v1: **pass** | inyectados=['f3', 'f4'] | retr_compl=None | final='The code freeze begins on a Monday.'
- v2: **pass** | inyectados=['f3', 'f4'] | expandidos=[] | retr_compl=None | final='We are told: "Aurora production releases happen every second Thursday" and "The Aurora cod'
- needed: v1=['f3', 'f4'] → v2=['f3', 'f4']


### Nota sobre a1

a1 cambia de hecho relacional (`f2` = 'puerto inmediatamente después del API gateway', necesitaba `f2`+`f1` y aritmética 7443+1) a hecho **absoluto** (`f2` = 'port 7444', override `needed_facts=[f2]`). El tier efectivo pasa de **aritmética** a **lookup**: lo que en v1 era una síntesis aritmética ahora es una lectura directa. Ese es el efecto medible del contrato (forbid_relative obligó a re-modelar f2).

### Nota sobre expand_links en cadenas (ch1, ch2, j4)

Los facts de cadena usan links markdown (`f5 → f6 → f7`). Con `expand_links:true`, un hit normal expande (1 salto, `score=null`, `via=hit`) el doc linkeado. El umbral 0.35 **no** filtra los expandidos: se inyectan siempre. Esto puede completar `needed_facts` que en v1 quedaban por debajo de umbral o fuera del top-k (p.ej. `f6`/`f7` en ch1, j4).

## Salida de ejecución

```
  [O] pass | inyectados=['f13'] | expandidos=[] | retr_compl=None | wall=3.6s | final='86'

=== ch1 (tier=cadena) needed=['f5', 'f6', 'f7'] ===
  [R] fail | inyectados=['f5', 'f6'] | expandidos=['f6'] | retr_compl=False | wall=4.9s | final='The stormdb database is located in datacenter R2.'
  [O] pass | inyectados=['f5', 'f6', 'f7'] | expandidos=[] | retr_compl=None | wall=5.8s | final='The stormdb database is located in the Quito datacenter.'

=== ch2 (tier=cadena) needed=['f6', 'f7'] ===
  [R] pass | inyectados=['f5', 'f6', 'f7'] | expandidos=[] | retr_compl=True | wall=4.7s | final='The host vega lives in the Quito datacenter.'
  [O] pass | inyectados=['f6', 'f7'] | expandidos=[] | retr_compl=None | wall=3.9s | final='Quito'

=== ch3 (tier=cadena) needed=['f5', 'f6'] ===
  [R] pass | inyectados=['f5', 'f6', 'f7'] | expandidos=[] | retr_compl=True | wall=3.3s | final='Rack R2'
  [O] pass | inyectados=['f5', 'f6'] | expandidos=[] | retr_compl=None | wall=3.6s | final='Rack R2'

=== RESUMEN ===
count aurora3: 14
cond R: 11/14 (78.6%)
cond O: 14/14 (100.0%)
atribucion: {'retrieval_fail': 2, 'sintesis_fail_R': 1, 'sintesis_fail_O': 0, 'success': 25}
```
