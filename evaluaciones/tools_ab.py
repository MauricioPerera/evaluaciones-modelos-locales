# -*- coding: utf-8 -*-
"""
tools_ab.py — A/B/C de DECISIÓN de invocación de herramientas.
3 brazos x 16 ítems = 48 evaluaciones. Grading determinista sobre la decisión
+ forma + contenido; NO se ejecutan las tools de verdad.
  Brazo A: 1B (Ollama :11434) + protocolo tags.
  Brazo B: Bonsai 27B (:8942) + protocolo tags.
  Brazo C: Bonsai 27B (:8942) + protocolo nativo (tool_calls).
No toca servidores. No loguea secretos.
"""
import sys
import os
import re
import json
import time
import urllib.request
import urllib.error

# Windows: forzar stdout utf-8 (un print con no-cp1252 rompio una corrida previa)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CWD = os.path.dirname(os.path.abspath(__file__))
ORACLE = os.path.join(CWD, "tools_oracle.json")
RESULTS = os.path.join(CWD, "tools_ab_results.json")
REPORT = os.path.join(CWD, "TOOLS-AB-REPORT.md")

OLLAMA = "http://localhost:11434/api/generate"
OLLAMA_HEALTH = "http://localhost:11434/api/tags"
BONSAI = "http://localhost:8942/v1/chat/completions"
BONSAI_HEALTH = "http://localhost:8942/v1/models"

OLLAMA_MODEL = "minicpm5-fable5-thinking"  # contexto dice minicpm5-fable5-thinking
THINK_END = chr(60) + "/think" + chr(62)   # </think>

TIMEOUT_A = 120
TIMEOUT_B = 900
TIMEOUT_C = 900
RETRIES = 1

# Buffer de stdout real para el "Salida de ejecución" del reporte.
EXEC_LINES = []


def log(msg=""):
    line = str(msg)
    print(line, flush=True)
    EXEC_LINES.append(line)


# ---------- HTTP ----------
def http_json(method, url, payload=None, timeout=120):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode('utf-8', errors='replace')
        status = resp.status
    try:
        parsed = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed = body
    return status, parsed


def health_ollama(attempts=3, gap=10):
    last = None
    for i in range(attempts):
        try:
            st, data = http_json('GET', OLLAMA_HEALTH, timeout=15)
            last = f"GET {OLLAMA_HEALTH} -> {st} {str(data)[:120]}"
            if st == 200:
                return True, last
        except Exception as e:
            last = f"GET {OLLAMA_HEALTH} -> EXC {type(e).__name__}: {e}"
        if i < attempts - 1:
            time.sleep(gap)
    return False, last


def health_bonsai(attempts=3, gap=10):
    last = None
    for i in range(attempts):
        try:
            st, data = http_json('GET', BONSAI_HEALTH, timeout=15)
            last = f"GET {BONSAI_HEALTH} -> {st} {str(data)[:120]}"
            if st == 200:
                return True, last
        except Exception as e:
            last = f"GET {BONSAI_HEALTH} -> EXC {type(e).__name__}: {e}"
        if i < attempts - 1:
            time.sleep(gap)
    return False, last


# ---------- LLM: Brazo A (1B Ollama, tags) ----------
def call_ollama(system, prompt):
    """Devuelve (raw_response, wall, error). 1 reintento por fallo de red."""
    payload = {
        "model": OLLAMA_MODEL,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "top_p": 1.0, "num_predict": 1024},
    }
    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            t0 = time.time()
            st, data = http_json('POST', OLLAMA, payload=payload, timeout=TIMEOUT_A)
            wall = time.time() - t0
            if st == 200 and isinstance(data, dict):
                return data.get("response", "") or "", wall, None
            last_err = f"status={st} body={str(data)[:200]}"
        except Exception as e:
            last_err = f"EXC {type(e).__name__}: {e}"
        if attempt < RETRIES:
            time.sleep(2)
    return "", 0.0, last_err


# ---------- LLM: Bonsai (B/C) ----------
def call_bonsai(messages, tools=None, timeout=TIMEOUT_B):
    """Devuelve (data_dict, wall, error). 1 reintento por fallo de red."""
    payload = {
        "messages": messages,
        "temperature": 0,
        "top_p": 1.0,
        "max_tokens": 4096,
        "stream": False,
    }
    if tools is not None:
        payload["tools"] = tools
    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            t0 = time.time()
            st, data = http_json('POST', BONSAI, payload=payload, timeout=timeout)
            wall = time.time() - t0
            if st == 200 and isinstance(data, dict):
                return data, wall, None
            last_err = f"status={st} body={str(data)[:200]}"
        except Exception as e:
            last_err = f"EXC {type(e).__name__}: {e}"
        if attempt < RETRIES:
            time.sleep(2)
    return None, 0.0, last_err


# ---------- Detección de invocación (tags) ----------
TAG_RE = re.compile(r"\[(CALC|FETCH|MCP):\s*(.*?)\]", re.DOTALL)


def final_text_ollama(raw):
    """Para el 1B: la respuesta post-razonamiento (post '</think>')."""
    if not raw:
        return ""
    if THINK_END in raw:
        return raw.rsplit(THINK_END, 1)[1]
    return raw


def detect_tags(text):
    """Devuelve lista de dicts {tool, content} para cada tag hallado."""
    if not text:
        return []
    out = []
    for m in TAG_RE.finditer(text):
        out.append({"tool": m.group(1).upper(), "content": m.group(2).strip()})
    return out


# ---------- Detección de invocación (nativo, brazo C) ----------
def detect_native(data):
    """Devuelve lista de dicts {tool, content} desde tool_calls.
    tool = nombre original de la función (calculator/http_fetch/...).
    content = argumento relevante ya extraído (expression para calculator,
    'method url' para http_fetch) para que el grading opere igual que en tags."""
    if not isinstance(data, dict):
        return []
    choices = data.get("choices") or []
    if not choices:
        return []
    msg = choices[0].get("message", {}) or {}
    tcs = msg.get("tool_calls") or []
    out = []
    for tc in tcs:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function", {}) or {}
        name = fn.get("name", "")
        args_raw = fn.get("arguments", "")
        # arguments suele venir como string JSON; parsear.
        if isinstance(args_raw, str) and args_raw:
            try:
                args = json.loads(args_raw)
            except Exception:
                args = {}
        elif isinstance(args_raw, dict):
            args = args_raw
        else:
            args = {}
        if name == "calculator":
            content = str(args.get("expression", "") if isinstance(args, dict) else "")
        elif name == "http_fetch":
            method = str(args.get("method", "") if isinstance(args, dict) else "")
            url = str(args.get("url", "") if isinstance(args, dict) else "")
            content = f"{method} {url}".strip() if method else url
        else:
            content = args_raw if isinstance(args_raw, str) else json.dumps(args_raw, ensure_ascii=False)
        out.append({"tool": name, "content": content})
    return out


def native_content(data):
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message", {}) or {}
    c = msg.get("content")
    return c if isinstance(c, str) else ("" if c is None else str(c))


# ---------- Eval SEGURO ----------
_SAFE_RE = re.compile(r'^[\d\s+\-*/().]+$')


def safe_eval(expr):
    """Solo dígitos, + - * / ** ( ) . y espacios. Devuelve (valor, error)."""
    if expr is None:
        return None, "expr vacia"
    e = expr.strip()
    if not e or not _SAFE_RE.match(e):
        return None, "malformed"
    # Rechazar dobles operadores absurdos que eval acceptaria como unarios: lo dejamos
    # pasar a eval; si explota, se reporta eval_error.
    try:
        val = eval(e, {"__builtins__": {}}, {})
    except Exception as ex:
        return None, f"eval_error: {type(ex).__name__}"
    if isinstance(val, bool):  # True/False no son números
        return None, "malformed"
    if not isinstance(val, (int, float)):
        return None, "malformed"
    return val, None


def num_close(val, target, tol=0.01):
    try:
        return abs(float(val) - float(target)) <= tol
    except Exception:
        return False


# ---------- Heurística abstención honesta (fetch) ----------
ABSTAIN_PATTERNS = [
    "cannot access", "can't access", "cant access", "unable to access",
    "no internet", "no network", "don't have access", "do not have access",
    "cannot fetch", "can't fetch", "unable to fetch", "cannot connect",
    "no web access", "not able to access", "cannot retrieve", "unable to retrieve",
    "don't have internet", "do not have internet", "no ability to access",
    "i can't access the", "i cannot access the", "i am unable", "i'm unable",
    "cannot browse", "can't browse", "no browsing", "cannot reach",
]


def declares_no_access(text):
    if not text:
        return False
    low = text.lower()
    return any(p in low for p in ABSTAIN_PATTERNS)


# ---------- GRADING ----------
def _is_calc(tool):
    return bool(tool) and tool.upper() in ("CALC", "CALCULATOR")


def _is_fetch(tool):
    return bool(tool) and tool.upper() in ("FETCH", "HTTP_FETCH")


def grade_calc_item(text, invocations, expr_result):
    """
    expected == call_calc.
    - CALC tag cuya expr evalúa == expr_result (tol 0.01) -> pass.
    - CALC tag presente pero todas malformed/incorrectas -> fail (malformed si ninguna evaluó).
    - Sin invocación CALC pero el texto contiene el número correcto -> pass_directo.
    - Sin invocación CALC y sin número correcto -> fail.
    Devuelve (veredicto, detalle).
    """
    calc_invs = [i for i in invocations if _is_calc(i["tool"])]
    if calc_invs:
        any_ok = False
        any_eval = False
        detail_parts = []
        for inv in calc_invs:
            val, err = safe_eval(inv["content"])
            if err == "malformed":
                detail_parts.append(f"malformed({inv['content']!r})")
                continue
            if err:
                detail_parts.append(f"{err}({inv['content']!r})")
                continue
            any_eval = True
            if num_close(val, expr_result):
                any_ok = True
                detail_parts.append(f"ok({inv['content']}={val})")
            else:
                detail_parts.append(f"wrong({inv['content']}={val} != {expr_result})")
        if any_ok:
            return "pass", "; ".join(detail_parts)
        if not any_eval:
            return "fail", "malformed: " + "; ".join(detail_parts)
        return "fail", "; ".join(detail_parts)
    # Sin invocación CALC -> ¿respondió el número correcto directamente?
    # Acepta separador de miles con coma (ej. "248,171") y decimales con punto.
    pat = r'[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+\.\d+|[-+]?\d+'
    nums = re.findall(pat, text or "")
    for n in nums:
        try:
            v = float(n.replace(",", ""))
        except ValueError:
            continue
        if num_close(v, expr_result):
            return "pass_directo", f"numero directo {v} ~= {expr_result}"
    return "fail", "sin invocacion ni numero correcto"


def grade_fetch_item(text, invocations, url_contains):
    """
    expected == call_fetch.
    - FETCH tag cuya URL contiene url_contains -> pass.
    - Sin invocación FETCH -> fail, salvo abstencion_honesta si declara no poder acceder.
    """
    fetch_invs = [i for i in invocations if _is_fetch(i["tool"])]
    if fetch_invs:
        for inv in fetch_invs:
            if url_contains and url_contains.lower() in inv["content"].lower():
                return "pass", f"fetch url contiene '{url_contains}': {inv['content']!r}"
        return "fail", f"fetch presente pero url sin '{url_contains}': {[i['content'] for i in fetch_invs]!r}"
    # Sin invocación FETCH
    if declares_no_access(text):
        return "abstencion_honesta", f"sin fetch; declara no poder acceder: {text.strip()[:200]!r}"
    return "fail", f"sin fetch y sin abstencion honesta: {text.strip()[:200]!r}"


def grade_no_call_item(text, invocations, keyword):
    """
    expected == no_call.
    - Cualquier invocación (CALC/FETCH/MCP/tool_call) -> fail (falso positivo).
    - Sin invocación: si keyword != None, requiere keyword en texto -> pass/fail.
      Si keyword == None -> pass.
    """
    if invocations:
        return "fail", f"falso positivo: {[i['tool'] for i in invocations]} -> {[i['content'] for i in invocations][:200]!r}"
    if keyword is None:
        return "pass", "sin invocacion (keyword null)"
    if keyword and keyword.lower() in (text or "").lower():
        return "pass", f"sin invocacion; keyword '{keyword}' presente"
    return "fail", f"sin invocacion pero keyword '{keyword}' ausente: {(text or '').strip()[:200]!r}"


def grade_item(item, invoco, invocations, text, arm):
    """Despacha según expected. Devuelve (veredicto, detalle)."""
    exp = item["expected"]
    if exp == "call_calc":
        return grade_calc_item(text, invocations, item["expr_result"])
    if exp == "call_fetch":
        return grade_fetch_item(text, invocations, item["url_contains"])
    if exp == "no_call":
        return grade_no_call_item(text, invocations, item.get("keyword"))
    return "fail", "expected desconocido"


# ---------- Arm runners ----------
def build_system(prompt_template, ctx):
    return prompt_template.replace("<contexto_factual>", ctx)


def run_arm_A(item, ctx, tags_system):
    """1B + tags."""
    system = build_system(tags_system, ctx)
    raw, wall, err = call_ollama(system, item["q"])
    ft = final_text_ollama(raw)
    invs = detect_tags(ft)
    invoco = len(invs) > 0
    veredicto, detalle = grade_item(item, invoco, invs, ft, "A")
    return {
        "id": item["id"],
        "clase": item["clase"],
        "brazo": "A",
        "question": item["q"],
        "decision_esperada": item["expected"],
        "invoco": bool(invoco),
        "tool": ",".join(i["tool"] for i in invs) if invs else "",
        "contenido_invocacion": [i["content"] for i in invs] if invs else [],
        "veredicto": veredicto,
        "detalle": detalle,
        "respuesta": ft,
        "wall_seconds": round(wall, 3),
        "error": err,
    }


def run_arm_B(item, ctx, tags_system):
    """Bonsai + tags."""
    system = build_system(tags_system, ctx)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": item["q"]},
    ]
    data, wall, err = call_bonsai(messages, tools=None, timeout=TIMEOUT_B)
    content = native_content(data) if data else ""
    invs = detect_tags(content)
    invoco = len(invs) > 0
    veredicto, detalle = grade_item(item, invoco, invs, content, "B")
    return {
        "id": item["id"],
        "clase": item["clase"],
        "brazo": "B",
        "question": item["q"],
        "decision_esperada": item["expected"],
        "invoco": bool(invoco),
        "tool": ",".join(i["tool"] for i in invs) if invs else "",
        "contenido_invocacion": [i["content"] for i in invs] if invs else [],
        "veredicto": veredicto,
        "detalle": detalle,
        "respuesta": content,
        "wall_seconds": round(wall, 3),
        "error": err,
    }


def run_arm_C(item, ctx, native_system, tools):
    """Bonsai + nativo."""
    system = build_system(native_system, ctx)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": item["q"]},
    ]
    data, wall, err = call_bonsai(messages, tools=tools, timeout=TIMEOUT_C)
    content = native_content(data) if data else ""
    invs = detect_native(data)
    invoco = len(invs) > 0
    veredicto, detalle = grade_item(item, invoco, invs, content, "C")
    return {
        "id": item["id"],
        "clase": item["clase"],
        "brazo": "C",
        "question": item["q"],
        "decision_esperada": item["expected"],
        "invoco": bool(invoco),
        "tool": ",".join(i["tool"] for i in invs) if invs else "",
        "contenido_invocacion": [i["content"] for i in invs] if invs else [],
        "veredicto": veredicto,
        "detalle": detalle,
        "respuesta": content,
        "wall_seconds": round(wall, 3),
        "error": err,
    }


# ---------- Agregados ----------
def agregados_arm(eval_items, items_by_id):
    """eval_items: lista de evaluaciones de UN brazo."""
    # Apropiados: 8 items con expected in {call_calc, call_fetch}
    calc = [e for e in eval_items if items_by_id[e["id"]]["clase"] == "calc"]
    fetch = [e for e in eval_items if items_by_id[e["id"]]["clase"] == "fetch"]
    no_call = [e for e in eval_items if e["decision_esperada"] == "no_call"]
    apropiados = [e for e in eval_items if e["decision_esperada"] in ("call_calc", "call_fetch")]

    pass_count = sum(1 for e in apropiados if e["veredicto"] == "pass")
    pass_directo = sum(1 for e in apropiados if e["veredicto"] == "pass_directo")
    abstencion = sum(1 for e in apropiados if e["veredicto"] == "abstencion_honesta")
    apropiados_fail = sum(1 for e in apropiados if e["veredicto"] == "fail")

    total_invocaciones = sum(1 for e in eval_items if e["invoco"])
    # recall = apropiados_correctos / 8 (solo pass cuenta como invocacion correcta)
    recall = pass_count / 8.0
    # precision = apropiados_correctos / total_invocaciones_emitidas
    precision = (pass_count / total_invocaciones) if total_invocaciones else 0.0
    # falsos positivos: no_call con invoco True
    fp = [e for e in no_call if e["invoco"]]
    falsos_positivos = len(fp)
    # no_call correctos (pass)
    no_call_pass = sum(1 for e in no_call if e["veredicto"] == "pass")

    calc_pass = sum(1 for e in calc if e["veredicto"] == "pass")
    calc_pass_directo = sum(1 for e in calc if e["veredicto"] == "pass_directo")
    fetch_pass = sum(1 for e in fetch if e["veredicto"] == "pass")
    fetch_abstencion = sum(1 for e in fetch if e["veredicto"] == "abstencion_honesta")

    # Matriz de confusion a nivel DECISION (invocar vs no invocar)
    # Filas: esperado (invoke=8, no_invoke=8). Cols: predicho (invoke, no_invoke).
    tp = sum(1 for e in apropiados if e["invoco"])           # esperado invoke & pred invoke
    fn = sum(1 for e in apropiados if not e["invoco"])        # esperado invoke & pred no-invoke
    fp_dec = sum(1 for e in no_call if e["invoco"])           # esperado no-invoke & pred invoke
    tn = sum(1 for e in no_call if not e["invoco"])           # esperado no-invoke & pred no-invoke

    return {
        "recall_apropiados_sobre_8": round(recall, 4),
        "apropiados_pass": pass_count,
        "apropiados_total": len(apropiados),
        "pass_directo": pass_directo,
        "abstencion_honesta": abstencion,
        "apropiados_fail": apropiados_fail,
        "precision": round(precision, 4),
        "falsos_positivos_sobre_8": falsos_positivos,
        "no_call_pass": no_call_pass,
        "no_call_total": len(no_call),
        "total_invocaciones_emitidas": total_invocaciones,
        "calc_pass_sobre_4": calc_pass,
        "calc_pass_directo": calc_pass_directo,
        "fetch_pass_sobre_4": fetch_pass,
        "fetch_abstencion_honesta": fetch_abstencion,
        "matriz_confusion_decision": {
            "esperado_invoke_pred_invoke": tp,
            "esperado_invoke_pred_noinvoke": fn,
            "esperado_noinvoke_pred_invoke": fp_dec,
            "esperado_noinvoke_pred_noinvoke": tn,
        },
        "falsos_positivos_detalle": [
            {"id": e["id"], "tool": e["tool"],
             "contenido": e["contenido_invocacion"], "respuesta": e["respuesta"]}
            for e in no_call if e["invoco"]
        ],
    }


def write_results(out):
    with open(RESULTS, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


# ---------- Reporte ----------
def build_report(out):
    ag = out["agregados"]
    evs = out["evaluaciones"]

    def arm_rows(label):
        a = ag[label]
        mc = a["matriz_confusion_decision"]
        return (
            f"| {label} | {a['apropiados_pass']}/8 | {a['recall_apropiados_sobre_8']} | "
            f"{a['pass_directo']} | {a['abstencion_honesta']} | {a['falsos_positivos_sobre_8']}/8 | "
            f"{a['precision']} | {a['calc_pass_sobre_4']}/4 | {a['fetch_pass_sobre_4']}/4 | "
            f"{a['no_call_pass']}/8 | {a['total_invocaciones_emitidas']} | "
            f"{mc['esperado_invoke_pred_invoke']} | {mc['esperado_invoke_pred_noinvoke']} | "
            f"{mc['esperado_noinvoke_pred_invoke']} | {mc['esperado_noinvoke_pred_noinvoke']} |"
        )

    lines = []
    lines.append("# TOOLS-AB-REPORT — Decisión de invocación de herramientas (3 brazos)")
    lines.append("")
    lines.append("Oráculo congelado: `tools_oracle.json` (16 ítems: 4 calc, 4 fetch, 8 no_call). ")
    lines.append("Grading determinista sobre la **decisión** + forma + contenido. No se ejecutan las tools.")
    lines.append("")
    lines.append("## 1. Tabla comparativa de los 3 brazos")
    lines.append("")
    lines.append("Brazo A = 1B (Ollama) + tags; Brazo B = Bonsai 27B + tags; Brazo C = Bonsai 27B + nativo (tool_calls).")
    lines.append("")
    lines.append("| Brazo | apropiados pass | recall (/8) | pass_directo | abstencion_honesta | "
                "falsos_pos (/8) | precision | calc pass (/4) | fetch pass (/4) | no_call pass (/8) | "
                "invoc emitidas | TP | FN | FP | TN |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for lab in ("A", "B", "C"):
        lines.append(arm_rows(lab))
    lines.append("")
    lines.append("Notas de métricas: `recall = apropiados_pass / 8` (solo `pass` = invocación correcta). "
                 "`pass_directo` = respondió el número correcto SIN invocar (decisión distinta, "
                 "reportado aparte, no suma a recall). `precision = apropiados_pass / invocaciones_emitidas`. "
                 "`falsos_positivos` = ítems `no_call` que emitieron invocación.")
    lines.append("")
    lines.append("## 2. Matriz de confusión por brazo (nivel DECISIÓN: invocar / no invocar)")
    lines.append("")
    lines.append("Filas = esperado (8 invocar, 8 no invocar). Columnas = predicho por el modelo.")
    lines.append("")
    lines.append("```")
    lines.append("Brazo A:")
    lines.append("  esperado invocar     -> pred invocar (TP) {} | pred no-invocar (FN) {}".format(
        ag["A"]["matriz_confusion_decision"]["esperado_invoke_pred_invoke"],
        ag["A"]["matriz_confusion_decision"]["esperado_invoke_pred_noinvoke"]))
    lines.append("  esperado no invocar  -> pred invocar (FP) {} | pred no-invocar (TN) {}".format(
        ag["A"]["matriz_confusion_decision"]["esperado_noinvoke_pred_invoke"],
        ag["A"]["matriz_confusion_decision"]["esperado_noinvoke_pred_noinvoke"]))
    lines.append("Brazo B:")
    lines.append("  esperado invocar     -> pred invocar (TP) {} | pred no-invocar (FN) {}".format(
        ag["B"]["matriz_confusion_decision"]["esperado_invoke_pred_invoke"],
        ag["B"]["matriz_confusion_decision"]["esperado_invoke_pred_noinvoke"]))
    lines.append("  esperado no invocar  -> pred invocar (FP) {} | pred no-invocar (TN) {}".format(
        ag["B"]["matriz_confusion_decision"]["esperado_noinvoke_pred_invoke"],
        ag["B"]["matriz_confusion_decision"]["esperado_noinvoke_pred_noinvoke"]))
    lines.append("Brazo C:")
    lines.append("  esperado invocar     -> pred invocar (TP) {} | pred no-invocar (FN) {}".format(
        ag["C"]["matriz_confusion_decision"]["esperado_invoke_pred_invoke"],
        ag["C"]["matriz_confusion_decision"]["esperado_invoke_pred_noinvoke"]))
    lines.append("  esperado no invocar  -> pred invocar (FP) {} | pred no-invocar (TN) {}".format(
        ag["C"]["matriz_confusion_decision"]["esperado_noinvoke_pred_invoke"],
        ag["C"]["matriz_confusion_decision"]["esperado_noinvoke_pred_noinvoke"]))
    lines.append("```")
    lines.append("")
    lines.append("## 3. Citas textuales de falsos positivos")
    lines.append("")
    lines.append("Ítems `no_call` (esperado: sin invocación) que emitieron invocación. Veredicto = fail.")
    lines.append("")
    any_fp = False
    for lab in ("A", "B", "C"):
        for e in evs:
            if e["brazo"] == lab and e["decision_esperada"] == "no_call" and e["invoco"]:
                any_fp = True
                resp = (e["respuesta"] or "").replace("\n", " ").strip()
                lines.append(f"- **{e['id']} / brazo {lab}** — tool: `{e['tool']}`; "
                              f"invocación: `{e['contenido_invocacion']}`")
                lines.append(f"  - detalle: {e['detalle']}")
                lines.append(f"  - respuesta: \"{resp[:300]}\"")
    if not any_fp:
        lines.append("- (sin falsos positivos en ningún brazo)")
    lines.append("")
    lines.append("## 4. Invocaciones malformadas (CALC con expresión no numérica)")
    lines.append("")
    lines.append("Calculadas con eval seguro (solo dígitos, `+ - * / ** ( ) .` y espacios); "
                 "cualquier otra cosa = malformed = fail.")
    lines.append("")
    any_mal = False
    for e in evs:
        if "malformed" in (e.get("detalle") or ""):
            any_mal = True
            resp = (e["respuesta"] or "").replace("\n", " ").strip()
            lines.append(f"- **{e['id']} / brazo {e['brazo']}** — tool: `{e['tool']}`; "
                         f"contenido invocación: `{e['contenido_invocacion']}`")
            lines.append(f"  - detalle: {e['detalle']}")
            lines.append(f"  - respuesta: \"{resp[:300]}\"")
    if not any_mal:
        lines.append("- (sin invocaciones malformadas)")
    lines.append("")
    lines.append("## 5. Detalle por brazo (veredicto por ítem)")
    lines.append("")
    for lab in ("A", "B", "C"):
        lines.append(f"### Brazo {lab}")
        lines.append("")
        lines.append("| id | clase | esperado | invoco | tool | veredicto | wall(s) |")
        lines.append("|---|---|---|---|---|---|---|")
        for e in evs:
            if e["brazo"] != lab:
                continue
            err = f" ERR={e['error']}" if e.get("error") else ""
            lines.append(f"| {e['id']} | {e['clase']} | {e['decision_esperada']} | "
                        f"{e['invoco']} | {e['tool'] or '-'} | {e['veredicto']}{err} | {e['wall_seconds']} |")
        lines.append("")
    lines.append("## 6. Trade-offs")
    lines.append("")
    lines.append("- **Brazo A (1B + tags)**: modelo chico, razonamiento hasta `</think>`. "
                 "Riesgo: puede emitir tags en ítems no_call (FP) o no invocar cuando debe (FN). "
                 "Barato y rápido por respuesta.")
    lines.append("- **Brazo B (Bonsai + tags)**: mismo protocolo tags que A sobre un modelo 27B. "
                 "Aísla el efecto del modelo manteniendo el protocolo; ~1-2 min por respuesta.")
    lines.append("- **Brazo C (Bonsai + nativo)**: cambia protocolo (tool_calls nativos) sobre el mismo "
                 "modelo que B. Aísla el efecto del protocolo. El content puede quedar vacío cuando "
                 "emite tool_calls (finish_reason=tool_calls).")
    lines.append("- Comparar A vs B = efecto modelo con protocolo fijo. B vs C = efecto protocolo con "
                 "modelo fijo. recall mide cuándo invoca cuando debe; precision penaliza invocar cuando "
                 "no debe; `pass_directo` y `abstencion_honesta` son resultados correctos por camino distinto.")
    lines.append("")
    lines.append("## 7. Salida de ejecución (stdout real, ~últimas 15 líneas)")
    lines.append("")
    lines.append("```")
    tail = EXEC_LINES[-15:] if len(EXEC_LINES) >= 15 else EXEC_LINES[:]
    for ln in tail:
        lines.append(ln)
    lines.append("```")
    lines.append("")
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


# ---------- main ----------
def main():
    log("=== HEALTH ===")
    ok_a, ev_a = health_ollama()
    ok_c, ev_c = health_bonsai()
    log(f"ollama :11434 -> {ok_a} | {ev_a}")
    log(f"bonsai :8942  -> {ok_c} | {ev_c}")
    if not (ok_a and ok_c):
        # Documentar y abortar
        blocked = {
            "blocked": True,
            "reason": "health check fallo tras 3 intentos espaciados 10s",
            "ollama_health": ev_a,
            "bonsai_health": ev_c,
        }
        with open(RESULTS, 'w', encoding='utf-8') as f:
            json.dump(blocked, f, ensure_ascii=False, indent=2)
        with open(REPORT, 'w', encoding='utf-8') as f:
            f.write("# TOOLS-AB-REPORT — BLOQUEADO\n\n")
            f.write(f"ollama :11434: `{ev_a}`\n\n")
            f.write(f"bonsai :8942: `{ev_c}`\n\n")
            f.write("BLOQUEADO — health check fallo tras 3 intentos espaciados 10s.\n")
        log("BLOQUEADO — health check fallo tras 3 intentos espaciados 10s")
        sys.exit(2)

    # Oráculo
    with open(ORACLE, 'r', encoding='utf-8') as f:
        oracle = json.load(f)
    ctx = oracle["contexto_factual"]
    items = oracle["items"]
    tags_system = oracle["protocolo_tags"]["system_prompt"]
    native_system = oracle["protocolo_nativo"]["system_prompt"]
    tools = oracle["protocolo_nativo"]["tools"]
    items_by_id = {it["id"]: it for it in items}

    out = {
        "meta": {
            "oracle": "tools_oracle.json",
            "items": len(items),
            "brazos": ["A", "B", "C"],
            "ollama_model": OLLAMA_MODEL,
            "nota": "Grading sobre decisión+forma+contenido; no se ejecutan tools.",
        },
        "evaluaciones": [],
        "agregados": {},
    }
    write_results(out)

    log("=== EVAL (48 evaluaciones: 16 items x 3 brazos) ===")
    t_global = time.time()
    n = 0
    for it in items:
        # Brazo A
        n += 1
        t0 = time.time()
        eA = run_arm_A(it, ctx, tags_system)
        out["evaluaciones"].append(eA)
        write_results(out)
        log(f"[{n:02d}/48] {it['id']} A invoco={eA['invoco']} tool={eA['tool'] or '-'} "
            f"veredicto={eA['veredicto']} wall={eA['wall_seconds']}s "
            f"({time.time()-t_global:.0f}s total)")
        # Brazo B
        n += 1
        t0 = time.time()
        eB = run_arm_B(it, ctx, tags_system)
        out["evaluaciones"].append(eB)
        write_results(out)
        log(f"[{n:02d}/48] {it['id']} B invoco={eB['invoco']} tool={eB['tool'] or '-'} "
            f"veredicto={eB['veredicto']} wall={eB['wall_seconds']}s "
            f"({time.time()-t_global:.0f}s total)")
        # Brazo C
        n += 1
        t0 = time.time()
        eC = run_arm_C(it, ctx, native_system, tools)
        out["evaluaciones"].append(eC)
        write_results(out)
        log(f"[{n:02d}/48] {it['id']} C invoco={eC['invoco']} tool={eC['tool'] or '-'} "
            f"veredicto={eC['veredicto']} wall={eC['wall_seconds']}s "
            f"({time.time()-t_global:.0f}s total)")

    # Agregados
    log("=== AGREGADOS ===")
    for lab, runner_items in (("A", "A"), ("B", "B"), ("C", "C")):
        evs_arm = [e for e in out["evaluaciones"] if e["brazo"] == lab]
        out["agregados"][lab] = agregados_arm(evs_arm, items_by_id)
        a = out["agregados"][lab]
        log(f"brazo {lab}: recall={a['recall_apropiados_sobre_8']} "
            f"pass={a['apropiados_pass']}/8 pass_directo={a['pass_directo']} "
            f"abst={a['abstencion_honesta']} FP={a['falsos_positivos_sobre_8']} "
            f"precision={a['precision']} calc={a['calc_pass_sobre_4']}/4 "
            f"fetch={a['fetch_pass_sobre_4']}/4 no_call={a['no_call_pass']}/8 "
            f"invoc={a['total_invocaciones_emitidas']}")
    write_results(out)

    # Reporte
    build_report(out)
    log(f"=== FIN === resultados: {RESULTS} | reporte: {REPORT} | "
        f"evaluaciones: {len(out['evaluaciones'])} | total: {time.time()-t_global:.0f}s")
    sys.exit(0)


if __name__ == "__main__":
    main()