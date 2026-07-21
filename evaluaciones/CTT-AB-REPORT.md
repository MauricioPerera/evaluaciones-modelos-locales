# CTT-AB-REPORT — Efecto de la memoria (CTT) sobre el desempeño

## Resumen

Experimento A/B sobre MicroExpert (modelo local MiniCPM5-1B Q8, llama-server CPU). 
FASE A: baseline sin memoria (userId `eval-nomem`, virgen). 
FASE B: con memoria CTT (userId `eval-mem`, 10 facts del proyecto ficticio Aurora sembrados). 
Grading: el keyword del oraculo aparece (case-insensitive) en la respuesta final del assistant. 
12 preguntas por fase (10 de Aurora + 2 de control). Sin ajustar el grading para favorecer resultado.

**Aciertos totales:** FASE A = 1/12 | FASE B = 8/12

**Aurora (10):** A = 0/10 | B = 6/10

**Control (2):** A = 1/2 | B = 2/2

**Latencia media:** A = 1.66s | B = 2.638s

## Tabla comparativa A vs B por pregunta

| ID | Pregunta | Keyword | Fase A | Fase B | t(A) s | t(B) s |
|----|----------|---------|--------|--------|--------|--------|
| q1 | What is the deploy command for project Aurora? | `aurora ship` | fail | fail | 0.85 | 2.5 |
| q2 | What port does the Aurora API gateway listen on? | `7443` | fail | pass | 0.813 | 3.363 |
| q3 | What is the name of Aurora's primary database? | `stormdb` | fail | fail | 0.808 | 1.467 |
| q4 | Who is the Aurora team lead? | `castellanos` | fail | fail | 0.432 | 0.866 |
| q5 | How often do Aurora releases go out? | `thursday` | fail | fail | 1.19 | 2.573 |
| q6 | Where do Aurora error logs live? | `/var/log/aurora` | fail | pass | 5.022 | 5.054 |
| q7 | What is the Aurora staging URL? | `staging.aurora-internal.dev` | fail | pass | 2.015 | 3.813 |
| q8 | What tool manages Aurora feature flags? | `flagpole` | fail | pass | 0.566 | 1.843 |
| q9 | Which runbook page documents the Aurora on-call rotation? | `rb-114` | fail | pass | 1.328 | 1.28 |
| q10 | What is the name of the runner pool where Aurora CI runs? | `borealis` | fail | pass | 2.382 | 1.674 |
| ctl1 | What is 12 + 15? Answer with just the number. | `27` | pass | pass | 2.532 | 4.448 |
| ctl2 | What is the chemical symbol for water? | `h2o` | fail | pass | 1.978 | 2.773 |

## Agregados

```json
{
  "fase_A": {
    "aciertos": 1,
    "total": 12
  },
  "fase_B": {
    "aciertos": 8,
    "total": 12
  },
  "preguntas_aurora_A": {
    "aciertos": 0,
    "total": 10
  },
  "preguntas_aurora_B": {
    "aciertos": 6,
    "total": 10
  },
  "control_A": {
    "aciertos": 1,
    "total": 2
  },
  "control_B": {
    "aciertos": 2,
    "total": 2
  },
  "latencia_media_A_seg": 1.66,
  "latencia_media_B_seg": 2.638
}
```

## Latencias

| Fase | Latencia media (s) |
|------|---------------------|
| A (sin memoria) | 1.66 |
| B (con memoria) | 2.638 |

Latencias por pregunta (s):

| ID | A | B |
|----|---|---|
| q1 | 0.85 | 2.5 |
| q2 | 0.813 | 3.363 |
| q3 | 0.808 | 1.467 |
| q4 | 0.432 | 0.866 |
| q5 | 1.19 | 2.573 |
| q6 | 5.022 | 5.054 |
| q7 | 2.015 | 3.813 |
| q8 | 0.566 | 1.843 |
| q9 | 1.328 | 1.28 |
| q10 | 2.382 | 1.674 |
| ctl1 | 2.532 | 4.448 |
| ctl2 | 1.978 | 2.773 |

## Fallos y respuestas notables

### Fallos de FASE B (con memoria)

- **q1** (keyword `aurora ship`):
  > [MCP: curl -X POST --data '{"action": "deploy", "project": "aurora", "version": "1.0"}]

- **q3** (keyword `stormdb`):
  > [MCP: aurora] aurora

- **q4** (keyword `castellanos`):
  > [MCP: aurora - AI assistant]

- **q5** (keyword `thursday`):
  > [MCP: aurora_releases]

### Aciertos ilustrativos

- **q2** (fase B, keyword `7443`):
  > [MCP: port 7443]

- **q6** (fase B, keyword `/var/log/aurora`):
  > [MCP: tool_name curl] curl -o /var/log/aurora/error.log --write /var/log/aurora/error.log

- **q7** (fase B, keyword `staging.aurora-internal.dev`):
  > [MCP: https://staging.aurora-internal.dev]

## Evidencia de sembrado

Import (POST /v1/memories/import?userId=eval-mem):

```json
{
  "imported": 10,
  "skipped": 0,
  "errors": 0,
  "skills": 0
}
```

El import confirma **10 memorias almacenadas** (imported=10, errors=0).

Verificacion via export (GET /v1/memories/export?userId=eval-mem): count = 8 (esperado 10).

> **Bug del server (no del experimento):** el endpoint `/v1/memories/export` usa 
> `listPaginated` que undercuenta de forma no deterministica. El usuario `local` del 
> server tiene 243 memorias (segun `/health`) pero el export devuelve 0; en este 
> experimento el export devolvio 8 de 10 (en corridas previas devolvio 5). El import 
> confirmo 10 almacenadas (imported=10, errors=0); ese resultado se uso como evidencia 
> primaria de almacenamiento y no se aborto (el import no devolvio error). La 
> verificacion via export exigida por el diseno no es cumplible por este bug del server.

Sonda de recall sobre q1 (fact **ausente** del export, keyword `aurora ship`):

- resultado: **fail**
- respuesta: `[MCP: aurora deploy -p staging]`
- q1 ausente del export; recall NO reprodujo el keyword exacto (modelo infiel). Esta sonda no prueba de forma limpia que recall accede a memorias ausentes del export; la evidencia de que las memorias fueron almacenadas es el import (10/0).

Evidencia limpia de recall independiente del export: en FASE B pasaron q6 (facts **ausentes** del export, keyword presente en la respuesta).

Primeras entradas del export (de las 8 que lista):

```json
[
  {
    "content": "The Aurora on-call rotation is documented in the runbook page RB-114",
    "category": "fact",
    "tags": [
      "aurora",
      "ctt-ab"
    ]
  },
  {
    "content": "The Aurora API gateway listens on port 7443",
    "category": "fact",
    "tags": [
      "aurora",
      "ctt-ab"
    ]
  },
  {
    "content": "Aurora feature flags are managed with the tool called flagpole",
    "category": "fact",
    "tags": [
      "aurora",
      "ctt-ab"
    ]
  }
]
```

## Trade-offs y decisiones de interpretacion

- **Grading no modificado**: pass = keyword (case-insensitive) en la respuesta final 
  devuelta por la API (post-procesamiento de tool tags). No se ajusto para favorecer resultado.
- **System prompt por defecto**: no se envio `system_prompt` (solo `user` y `stream:false`), 
  para mantener el A/B limpio (unica diferencia entre fases = el userId/memoria).
- **Confound de tool tags**: el system prompt por defecto siempre incluye instrucciones 
  `[CALC: expr]` y `[FETCH: GET url]`. Los tags `[FETCH:...]` se ejecutan siempre y se reemplazan 
  por el resultado/error; los `[MCP:...]` solo se procesan si hay cliente MCP (no configurado), 
  por lo que se devuelven intactos. Si el modelo envuelve una respuesta (p.ej. una URL) en un 
  `[FETCH: GET <url>]`, la ejecucion puede reemplazar el keyword por un error/HTML y degradar el 
  grading aun cuando la memoria fue recordada. Esto es parte del comportamiento real del sistema 
  y se reporta tal cual, sin corregir.
- **Auto-mining habilitado en el server**: cada turno se guarda como sesion y se auto-mina. 
  En FASE A esto podria crear memorias a partir de las respuestas del modelo, pero como el 
  modelo no conoce los facts de Aurora sin memoria, no puede sembrarlos; el baseline se mantiene 
  efectivamente sin los facts. Se uso un unico userId `eval-nomem` para toda la FASE A segun el 
  diseno.
- **Auto-mining durante FASE B (confound)**: el server auto-mina cada turno de FASE B para 
  `eval-mem`, creando memorias a partir de las respuestas del modelo. Las preguntas Aurora que 
  pasan generan memorias con el fact correcto que pueden ser recordadas por preguntas 
  posteriores de FASE B, inflando parcialmente el resultado. Export post-FASE-B de `eval-mem`: 
  count=8, de las cuales **3 son auto-minadas** (no sembradas), p.ej.:

  - `The user asked for water's chemical symbol`
  - `I answer with H2O`
  - `The assistant provided H2O`

  Esto es comportamiento real del sistema (el diseno no pidio deshabilitar auto-mining); 
  para aislar el efecto puro de los 10 facts sembrados habria que deshabilitar el auto-mining, 
  lo cual queda fuera del alcance pedido.
- **Sin historial entre preguntas**: cada request contiene un unico mensaje user (sin `history`), 
  evitando contaminacion cruzada via el array de mensajes.
- **Timeout/reintento**: 180s por request, 1 reintento ante excepcion de red/timeout.

## Salida de ejecucion (ultimas ~15 lineas de stdout)

```
    pass | 1.28s | kw=rb-114 | err=None
    resp: [MCP: RB-114]
[B] q10 -> What is the name of the runner pool where Aurora CI runs?
    pass | 1.67s | kw=borealis | err=None
    resp: [MCP: runner_pool: borealis]
[B] ctl1 -> What is 12 + 15? Answer with just the number.
    pass | 4.45s | kw=27 | err=None
    resp: 27
[B] ctl2 -> What is the chemical symbol for water?
    pass | 2.77s | kw=h2o | err=None
    resp: H2O
[post-FASE-B] export userId=eval-mem -> count=8 (incluye auto-minadas)

[resultados] escritos en C:\Users\Administrador\AppData\Local\Temp\claude\D--Repo-model\14179e1e-e981-43ff-b5db-db2100d0ea43\scratchpad\micro-expert\ctt_ab_results.json
[agregados] {"fase_A": {"aciertos": 1, "total": 12}, "fase_B": {"aciertos": 8, "total": 12}, "preguntas_aurora_A": {"aciertos": 0, "total": 10}, "preguntas_aurora_B": {"aciertos": 6, "total": 10}, "control_A": {"aciertos": 1, "total": 2}, "control_B": {"aciertos": 2, "total": 2}, "latencia_media_A_seg": 1.66, "latencia_media_B_seg": 2.638}
```
