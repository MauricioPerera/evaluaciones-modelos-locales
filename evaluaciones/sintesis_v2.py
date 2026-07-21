#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sintesis_v2.py — Misma medicion que sintesis.py (mismas 14 preguntas de
sintesis_oracle.json, mismo grading, mismas 2 condiciones R/O, mismo system
prompt y options) sobre la coleccion aurora3 creada CON el knowledge contract
de sintesis_oracle_v2.json y los facts_md re-modelados.

Cambios exactos respecto de v1:
  1. Coleccion aurora3 (DELETE previa) creada con contract + facts_md (un doc
     OKF por fact; description = texto del fact TAL CUAL con sus links markdown).
     Se verifica count==14 y que el contrato NO rechazo los facts (rechazo == abort).
  2. Condicion R: query k=5, expand_links:true. Umbral 0.35 SOLO sobre hits
     normales; los docs expanded=true se inyectan SIEMPRE.
  3. Condicion O: needed_facts (con override a1) inyectados a mano, como en v1.
  4. En AMBAS condiciones los links markdown se renderizan a texto plano al
     armar "Facts from memory:" (el modelo no ve sintaxis de links).
  5. Salidas incrementales: sintesis_v2_results.json (schema v1 + campos
     expandidos) y SINTESIS-V2-REPORT.md (espanol, v1 vs v2 lado a lado).
"""
import sys
import os
import json
import time
import re
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CWD = os.path.dirname(os.path.abspath(__file__))
ORACLE = os.path.join(CWD, "sintesis_oracle.json")          # 14 preguntas congeladas
ORACLE_V2 = os.path.join(CWD, "sintesis_oracle_v2.json")    # facts_md + contract + overrides
RESULTS_V1 = os.path.join(CWD, "sintesis_results.json")     # numeros v1 (solo lectura)
RESULTS = os.path.join(CWD, "sintesis_v2_results.json")
REPORT = os.path.join(CWD, "SINTESIS-V2-REPORT.md")

RAG = "http://127.0.0.1:8937"
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "minicpm5-fable5-thinking"
COLL = "aurora3"
K = 5
THRESHOLD = 0.35
NUM_PREDICT = 1024
TIMEOUT = 120
RETRIES = 1  # 1 reintento => hasta 2 intentos

# Delimitador de fin de razonamiento del modelo, construido sin literal para
# evitar filtrado de tokens especiales en el pipeline de escritura.
# Equivale al tag de cierre de razonamiento que emite el modelo thinking.
THINK_END = chr(60) + "/think" + chr(62)
SPEC_DELIM = "VIOUS"

DECISIONES = {
    "temperature": "temp 0: se mide capacidad de sintesis, no protocolo previo; anulado el ruido del muestreo.",
    "delimitador_respuesta": (
        "El spec decia razonamiento terminando en 'VIOUS'; el modelo real emite un tag de cierre de "
        "razonamiento (construido via chr). Se extrae la respuesta tras la ultima ocurrencia de ese "
        "tag; si no aparece, se cae a 'VIOUS' y luego a la respuesta cruda. El ultimo numero "
        "extraido coincide en ambos caminos."
    ),
    "keywords_sobre_final": "keywords_all se evaluan sobre el texto final (post-reasoning), consistente con expected_number.",
    "knowledge_contract": (
        "Coleccion aurora3 creada con el contract de sintesis_oracle_v2.json (max_chars=200, "
        "forbid_relative=true, allowed_tags=aurora2/infra/people/process, min_links=0). Si el "
        "contrato rechazara algun fact del oraculo v2 seria abort (bug del oraculo del PM)."
    ),
    "expand_links": (
        "Condicion R: query con expand_links=true. Umbral 0.35 se aplica SOLO a hits normales; "
        "los docs con expanded=true se inyectan SIEMPRE (score=null). Es el feature medido."
    ),
    "render_links": (
        "En ambas condiciones, al armar 'Facts from memory:' los links markdown se renderizan a "
        "texto plano ([vega](f6) -> vega) para que el modelo no vea sintaxis de links."
    ),
    "override_a1": (
        "needed_facts se toman de sintesis_oracle.json salvo a1, donde el override del oraculo v2 "
        "lo cambia a [f2] (f2 ahora absoluto: port 7444). Tier efectivo de a1 pasa de aritmetica a lookup."
    ),
}

# Log capturado para el "Salida de ejecucion" del reporte.
_LOG_LINES = []


def log(msg):
    print(msg, flush=True)
    _LOG_LINES.append(msg)


def http_json(method, url, payload=None, timeout=TIMEOUT):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body
        return e.code, parsed
    try:
        parsed = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed = body
    return status, parsed


def health_rag(attempts=3, gap=10):
    last = None
    for i in range(attempts):
        try:
            st, data = http_json("GET", f"{RAG}/collections", timeout=10)
            last = f"GET /collections -> {st} {str(data)[:120]}"
            if st == 200:
                return True, last
        except Exception as e:
            last = f"GET /collections -> EXC {type(e).__name__}: {e}"
        if i < attempts - 1:
            time.sleep(gap)
    return False, last


def health_ollama(attempts=3, gap=10):
    last = None
    for i in range(attempts):
        try:
            st, data = http_json(
                "POST", OLLAMA,
                payload={"model": MODEL, "prompt": "Reply with the single number 1.",
                         "stream": False, "options": {"temperature": 0, "num_predict": 16}},
                timeout=60,
            )
            last = f"POST /api/generate -> {st} {str(data)[:120]}"
            if st == 200:
                return True, last
        except Exception as e:
            last = f"POST /api/generate -> EXC {type(e).__name__}: {e}"
        if i < attempts - 1:
            time.sleep(gap)
    return False, last


# ---------- RENDER LINKS ----------
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def render_links(text):
    """[vega](f6) -> vega.  El modelo no debe ver sintaxis de links."""
    if not text:
        return text
    return _LINK_RE.sub(r"\1", text)


# ---------- SEMBRADO ----------
def build_doc(fact_id, fact_md):
    """description = texto del fact TAL CUAL con sus links markdown.
    tags vacios: allowed_tags del contrato no incluye 'aurora3'; tags=[] pasa
    kc-tags (no hay tag que validar) y la validacion OKF base (Array)."""
    title = render_links(fact_md).strip().split(":")[-1].strip()[:60] if ":" in fact_md else render_links(fact_md)[:60]
    md = (
        "---\n"
        "type: fact\n"
        f"title: {title}\n"
        f"description: {fact_md}\n"
        "tags: []\n"
        "---\n"
        f"{fact_md}\n"
    )
    return {"id": fact_id, "md": md}


def seed(facts_md, contract):
    st, d = http_json("DELETE", f"{RAG}/collections/{COLL}", timeout=30)
    log(f"[seed] DELETE /collections/{COLL} -> {st} {str(d)[:120]}")
    time.sleep(1)
    docs = [build_doc(fid, fact) for fid, fact in facts_md.items()]
    body = {"name": COLL, "docs": docs, "contract": contract}
    st, data = http_json("POST", f"{RAG}/collections", payload=body, timeout=120)
    log(f"[seed] POST /collections {COLL} ({len(docs)} docs, contract) -> {st}")
    if st != 200:
        log(f"[seed] RESP no-200: {str(data)[:500]}")
    return st, data


def count_collection():
    """Cuenta docs via query k alto (todos los hits distintos)."""
    try:
        st, data = http_json("POST", f"{RAG}/collections/{COLL}/query",
                             payload={"text": "aurora project deploy database team host rack datacenter error budget",
                                      "k": 50}, timeout=30)
        if st == 200 and isinstance(data, list):
            ids = {h.get("id") for h in data if isinstance(h, dict)}
            return len(ids), data
    except Exception as e:
        log(f"[count] EXC {e}")
    return -1, None


# ---------- RETRIEVAL ----------
def query_rag(text):
    st, data = http_json("POST", f"{RAG}/collections/{COLL}/query",
                         payload={"text": text, "k": K, "expand_links": True}, timeout=30)
    if st != 200 or not isinstance(data, list):
        return []
    return data


def build_context(hits):
    """Umbral 0.35 SOLO a hits normales; expanded=true se inyectan siempre.
    Devuelve (contexto, keep) donde keep preserva el orden devuelto por el
    engine (normales filtradas, luego expandidos)."""
    keep = []
    for h in hits:
        if h.get("expanded") is True:
            keep.append(h)
        else:
            if float(h.get("score", 0.0)) >= THRESHOLD:
                keep.append(h)
    if not keep:
        return "", []
    lines = "\n".join(f"- {render_links(h.get('description', ''))}" for h in keep)
    return f"Facts from memory:\n{lines}", keep


# ---------- LLM ----------
def llm_answer(question, context):
    system = (f"{context}\n\nYou are MicroExpert, a helpful AI assistant.\n"
              "IMPORTANT: Use the information above to answer the user.")
    payload = {
        "model": MODEL,
        "prompt": question,
        "system": system,
        "stream": False,
        "options": {"temperature": 0, "top_p": 1.0, "num_predict": NUM_PREDICT},
    }
    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            t0 = time.time()
            st, data = http_json("POST", OLLAMA, payload=payload, timeout=TIMEOUT)
            wall = time.time() - t0
            if st == 200 and isinstance(data, dict):
                return data.get("response", ""), wall, None
            last_err = f"status={st} body={str(data)[:200]}"
        except Exception as e:
            last_err = f"EXC {type(e).__name__}: {e}"
        if attempt < RETRIES:
            time.sleep(2)
    return "", 0.0, last_err


# ---------- GRADING ----------
def final_text(raw):
    if THINK_END in raw:
        return raw.rsplit(THINK_END, 1)[1]
    if SPEC_DELIM in raw:
        return raw.rsplit(SPEC_DELIM, 1)[1]
    return raw


def grade(preg, raw_resp):
    ft = final_text(raw_resp).strip()
    if "expected_number" in preg:
        cleaned = ft.replace(",", "")
        nums = re.findall(r"-?\d+", cleaned)
        if not nums:
            return "fail", ft, None
        got = int(nums[-1])
        return ("pass" if got == preg["expected_number"] else "fail"), ft, got
    if "keywords_all" in preg:
        low = ft.lower()
        ok = all(k.lower() in low for k in preg["keywords_all"])
        return ("pass" if ok else "fail"), ft, preg["keywords_all"]
    return "fail", ft, None


# ---------- MAIN ----------
def main():
    with open(ORACLE, "r", encoding="utf-8") as f:
        oracle = json.load(f)
    with open(ORACLE_V2, "r", encoding="utf-8") as f:
        oracle_v2 = json.load(f)
    preguntas = oracle["preguntas"]
    facts_md = oracle_v2["facts_md"]
    contract = oracle_v2["contract"]
    overrides = oracle_v2.get("needed_facts_overrides", {})

    # needed_facts por pregunta: los de sintesis_oracle.json salvo override v2 (a1).
    def needed_for(pid, preg):
        if pid in overrides:
            return list(overrides[pid])
        return list(preg.get("needed_facts", []))

    ok_rag, ev_rag = health_rag()
    ok_oll, ev_oll = health_ollama()
    log(f"[health] rag-local: {ok_rag} | {ev_rag}")
    log(f"[health] ollama:    {ok_oll} | {ev_oll}")
    if not (ok_rag and ok_oll):
        log("BLOQUEADO: servicio no responde tras 3 intentos.")
        with open(RESULTS, "w", encoding="utf-8") as f:
            json.dump({"bloqueado": True, "ev_rag": ev_rag, "ev_oll": ev_oll}, f, ensure_ascii=False, indent=2)
        sys.exit(2)

    st, data = seed(facts_md, contract)
    # Rechazo de contrato: el oraculo v2 deberia pasar el contrato. Si no pasa,
    # es bug del oraculo del PM -> ABORTAR (documentado).
    rejected = False
    contract_errors = None
    if st != 200:
        err_str = ""
        if isinstance(data, dict):
            err_str = str(data.get("error", ""))
        else:
            err_str = str(data)
        contract_errors = err_str
        if "kc-" in err_str or "Colecci" in err_str or "invalid" in err_str.lower():
            rejected = True
        log(f"[seed] ABORT: creacion de {COLL} rechazada. status={st} error={err_str[:400]}")
        with open(RESULTS, "w", encoding="utf-8") as f:
            json.dump({"bloqueado": True, "motivo": "contrato_rechazo",
                       "status": st, "contract_errors": contract_errors,
                       "contract": contract}, f, ensure_ascii=False, indent=2)
        log(f"BLOQUEADO: el contrato rechazo facts del oraculo v2. {contract_errors[:200]}")
        sys.exit(3)

    count_create = data.get("count") if isinstance(data, dict) else None
    count, count_data = count_collection()
    count_evidence = json.dumps(count_data, ensure_ascii=False)[:800] if count_data else "n/a"
    log(f"[seed] count {COLL} == {count} (create.count={count_create}, esperado 14)")
    assert count == 14, f"count != 14 (got {count})"

    evaluaciones = []
    for preg in preguntas:
        pid = preg["id"]
        tier = preg["tier"]
        needed = needed_for(pid, preg)
        q = preg["q"]
        log(f"\n=== {pid} (tier={tier}) needed={needed} ===")

        for cond in ("R", "O"):
            if cond == "R":
                hits = query_rag(q)
                scores = [{"id": h.get("id"), "score": h.get("score"),
                           "expanded": bool(h.get("expanded")), "via": h.get("via"),
                           "description": h.get("description", "")} for h in hits]
                contexto, keep = build_context(hits)
                injected = [h.get("id") for h in keep]
                expandidos = [h.get("id") for h in keep if h.get("expanded") is True]
            else:
                contexto = "Facts from memory:\n" + "\n".join(
                    f"- {render_links(facts_md[fid])}" for fid in needed if fid in facts_md)
                scores = []
                injected = list(needed)
                expandidos = []

            if cond == "R":
                retrieval_completo = set(needed).issubset(set(injected or []))
            else:
                retrieval_completo = None  # no aplica en O

            raw, wall, err = llm_answer(q, contexto)
            verdict, ft, detail = grade(preg, raw)

            ev = {
                "id": pid,
                "tier": tier,
                "condicion": cond,
                "resultado": verdict,
                "respuesta": raw,
                "respuesta_final": ft,
                "grading_detail": detail,
                "scores": scores,
                "facts_inyectados": injected,
                "expandidos": expandidos,
                "needed_facts": needed,
                "retrieval_completo": retrieval_completo,
                "wall_seconds": round(wall, 2),
            }
            if err:
                ev["error"] = err
            evaluaciones.append(ev)
            log(f"  [{cond}] {verdict} | inyectados={injected} | expandidos={expandidos} | "
                f"retr_compl={retrieval_completo} | wall={wall:.1f}s | final={ft[:80]!r}")

            with open(RESULTS, "w", encoding="utf-8") as f:
                json.dump({"meta": {"modelo": MODEL, "coleccion": COLL, "k": K, "umbral": THRESHOLD,
                                    "expand_links": True, "decisiones": DECISIONES},
                           "count_aurora3": count, "count_create": count_create,
                           "count_evidence": count_evidence,
                           "contract": contract,
                           "evaluaciones": evaluaciones}, f, ensure_ascii=False, indent=2)

    # ---------- AGREGADOS ----------
    tiers = sorted({e["tier"] for e in evaluaciones})
    by_tier_cond = {}
    by_cond = {}
    for t in tiers:
        by_tier_cond[t] = {}
        for c in ("R", "O"):
            sub = [e for e in evaluaciones if e["tier"] == t and e["condicion"] == c]
            p = sum(1 for e in sub if e["resultado"] == "pass")
            by_tier_cond[t][c] = {"pass": p, "total": len(sub),
                                  "pct": round(100 * p / len(sub), 1) if sub else 0}
    for c in ("R", "O"):
        sub = [e for e in evaluaciones if e["condicion"] == c]
        p = sum(1 for e in sub if e["resultado"] == "pass")
        by_cond[c] = {"pass": p, "total": len(sub),
                      "pct": round(100 * p / len(sub), 1) if sub else 0}

    atrib = {"retrieval_fail": [], "sintesis_fail_R": [], "sintesis_fail_O": [], "success": []}
    for e in evaluaciones:
        if e["resultado"] == "pass":
            atrib["success"].append(e["id"])
            continue
        if e["condicion"] == "R":
            if e["retrieval_completo"] is False:
                atrib["retrieval_fail"].append(e["id"])
            else:
                atrib["sintesis_fail_R"].append(e["id"])
        else:
            atrib["sintesis_fail_O"].append(e["id"])
    atrib_counts = {k: len(v) for k, v in atrib.items()}

    agregados = {"by_tier_cond": by_tier_cond, "by_cond": by_cond,
                 "atribucion_fallos_ids": atrib,
                 "atribucion_fallos_counts": atrib_counts}

    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump({"meta": {"modelo": MODEL, "coleccion": COLL, "k": K, "umbral": THRESHOLD,
                            "expand_links": True, "decisiones": DECISIONES},
                   "count_aurora3": count, "count_create": count_create,
                   "count_evidence": count_evidence,
                   "contract": contract,
                   "evaluaciones": evaluaciones,
                   "agregados": agregados}, f, ensure_ascii=False, indent=2)

    log("\n=== RESUMEN ===")
    log(f"count {COLL}: {count}")
    for c in ("R", "O"):
        log(f"cond {c}: {by_cond[c]['pass']}/{by_cond[c]['total']} ({by_cond[c]['pct']}%)")
    log(f"atribucion: {atrib_counts}")

    # ---------- REPORTE ----------
    write_report(agregados, by_tier_cond, by_cond, atrib, atrib_counts, count, count_create, contract)

    sys.exit(0)


def _v1_agregados():
    try:
        with open(RESULTS_V1, "r", encoding="utf-8") as f:
            v1 = json.load(f)
        return v1
    except Exception as e:
        log(f"[report] no se pudo leer sintesis_results.json: {e}")
        return None


def _v1_eval_map(v1):
    m = {}
    if not v1:
        return m
    for e in v1.get("evaluaciones", []):
        m[(e["id"], e["condicion"])] = e
    return m


def write_report(agregados, by_tier_cond, by_cond, atrib, atrib_counts, count, count_create, contract):
    v1 = _v1_agregados()
    v1_agg = v1.get("agregados", {}) if v1 else {}
    v1_by_tier = v1_agg.get("by_tier_cond", {}) if v1_agg else {}
    v1_by_cond = v1_agg.get("by_cond", {}) if v1_agg else {}
    v1_eval = _v1_eval_map(v1)
    v2_eval = json.load(open(RESULTS, encoding="utf-8"))["evaluaciones"]
    v2_map = {(e["id"], e["condicion"]): e for e in v2_eval}

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("# SINTESIS-V2-REPORT — límite de síntesis multi-hecho del 1B sobre aurora3 (knowledge contract)\n\n")
        f.write("Misma medición que `sintesis.py` (mismas 14 preguntas congeladas de `sintesis_oracle.json`, "
                "mismo grading, mismas condiciones R/O, mismo system prompt y options temp 0 / top_p 1.0 / "
                "num_predict 1024) sobre la colección **aurora3**, creada con el **knowledge contract** de "
                "`sintesis_oracle_v2.json` y los **facts_md** re-modelados. Cambios: hechos absolutos con "
                "links markdown, `f2` absoluto (port 7444), `f4` en horas, `needed_facts` de **a1** = `[f2]` "
                "(override del oráculo v2). En condición R se usa `expand_links:true`; el umbral 0.35 se "
                "aplica **solo** a hits normales y los docs `expanded=true` se inyectan **siempre**. "
                "En ambas condiciones los links markdown se renderizan a texto plano al armar "
                "`Facts from memory:`.\n\n")

        f.write(f"- Colección: `{COLL}` — count={count} (create.count={count_create}), esperado 14.\n")
        f.write(f"- Contract: max_chars=200, forbid_relative=true, "
                f"allowed_tags={contract['allowed_tags']}, min_links={contract['min_links']}. "
                f"Creación **no rechazada** por el contrato.\n")
        f.write(f"- Condición R global: **{by_cond['R']['pass']}/{by_cond['R']['total']} "
                f"({by_cond['R']['pct']}%)**  |  v1: "
                f"{v1_by_cond.get('R', {}).get('pass', '?')}/{v1_by_cond.get('R', {}).get('total', '?')} "
                f"({v1_by_cond.get('R', {}).get('pct', '?')}%)\n")
        f.write(f"- Condición O global: **{by_cond['O']['pass']}/{by_cond['O']['total']} "
                f"({by_cond['O']['pct']}%)**  |  v1: "
                f"{v1_by_cond.get('O', {}).get('pass', '?')}/{v1_by_cond.get('O', {}).get('total', '?')} "
                f"({v1_by_cond.get('O', {}).get('pct', '?')}%)\n\n")

        # ---- Tabla tier x condicion v1 vs v2 ----
        f.write("## Tabla tier × condición — v1 vs v2 (lado a lado)\n\n")
        f.write("Números v1 leídos de `sintesis_results.json` (no inventados).\n\n")
        f.write("| Tier | Cond | v1 pass/total (pct) | v2 pass/total (pct) | Δ pct | v1 ids-fail | v2 ids-fail |\n")
        f.write("|------|------|---------------------|---------------------|-------|-------------|-------------|\n")
        tiers_order = ["control", "join", "aritmetica", "cadena"]
        for t in tiers_order:
            for c in ("R", "O"):
                v2c = by_tier_cond.get(t, {}).get(c, {})
                v1c = v1_by_tier.get(t, {}).get(c, {})
                v1pct = v1c.get("pct")
                v2pct = v2c.get("pct")
                delta = ""
                if isinstance(v1pct, (int, float)) and isinstance(v2pct, (int, float)):
                    delta = f"{v2pct - v1pct:+.1f}"
                v1_ids_fail = []
                v2_ids_fail = []
                if v1:
                    for e in v1.get("evaluaciones", []):
                        if e["tier"] == t and e["condicion"] == c and e["resultado"] != "pass":
                            v1_ids_fail.append(e["id"])
                # ids falla v2 por tier/cond
                for e in v2_eval:
                    if e["tier"] == t and e["condicion"] == c and e["resultado"] != "pass":
                        v2_ids_fail.append(e["id"])
                f.write(f"| {t} | {c} | {v1c.get('pass','?')}/{v1c.get('total','?')} "
                        f"({v1c.get('pct','?')}%) | {v2c.get('pass','?')}/{v2c.get('total','?')} "
                        f"({v2c.get('pct','?')}%) | {delta} | {', '.join(v1_ids_fail) or '—'} | "
                        f"{', '.join(v2_ids_fail) or '—'} |\n")

        # ---- Atribucion de fallos ----
        f.write("\n## Atribución de fallos (v2)\n\n")
        f.write(f"- retrieval_fail (R, faltó algún needed): {atrib_counts['retrieval_fail']} — "
                f"{atrib['retrieval_fail'] or '—'}\n")
        f.write(f"- sintesis_fail_R (R, needed completo, no sintetizó): {atrib_counts['sintesis_fail_R']} — "
                f"{atrib['sintesis_fail_R'] or '—'}\n")
        f.write(f"- sintesis_fail_O (O, contexto oráculo, no sintetizó): {atrib_counts['sintesis_fail_O']} — "
                f"{atrib['sintesis_fail_O'] or '—'}\n")
        f.write(f"- success: {atrib_counts['success']}\n")
        if v1_agg:
            v1a = v1_agg.get("atribucion_fallos_counts", {})
            f.write(f"\nAtribución v1 (referencia): retrieval_fail={v1a.get('retrieval_fail')}, "
                    f"sintesis_fail_R={v1a.get('sintesis_fail_R')}, sintesis_fail_O={v1a.get('sintesis_fail_O')}, "
                    f"success={v1a.get('success')}\n")

        # ---- Citas de cambios notables ----
        f.write("\n## Cambios notables (v1 → v2)\n\n")

        def cita(pid, cond):
            e1 = v1_eval.get((pid, cond))
            e2 = v2_map.get((pid, cond))
            if not e1 or not e2:
                return f"### {pid} [{cond}]\n\n(dato faltante en v1 o v2)\n"
            lines = [f"### {pid} [{cond}]  (tier={e2['tier']})\n"]
            lines.append(f"- v1: **{e1['resultado']}** | inyectados={e1['facts_inyectados']} | "
                         f"retr_compl={e1['retrieval_completo']} | final={e1['respuesta_final'][:90]!r}")
            lines.append(f"- v2: **{e2['resultado']}** | inyectados={e2['facts_inyectados']} | "
                         f"expandidos={e2.get('expandidos')} | retr_compl={e2['retrieval_completo']} | "
                         f"final={e2['respuesta_final'][:90]!r}")
            lines.append(f"- needed: v1={e1['needed_facts']} → v2={e2['needed_facts']}\n")
            return "\n".join(lines) + "\n"

        for pid in ("a1", "ch1", "j4", "a3"):
            f.write(cita(pid, "R"))
            f.write(cita(pid, "O"))

        f.write("\n### Nota sobre a1\n\n")
        f.write("a1 cambia de hecho relacional (`f2` = 'puerto inmediatamente después del API gateway', "
                "necesitaba `f2`+`f1` y aritmética 7443+1) a hecho **absoluto** (`f2` = 'port 7444', "
                "override `needed_facts=[f2]`). El tier efectivo pasa de **aritmética** a **lookup**: "
                "lo que en v1 era una síntesis aritmética ahora es una lectura directa. Ese es el efecto "
                "medible del contrato (forbid_relative obligó a re-modelar f2).\n")

        f.write("\n### Nota sobre expand_links en cadenas (ch1, ch2, j4)\n\n")
        f.write("Los facts de cadena usan links markdown (`f5 → f6 → f7`). Con `expand_links:true`, un "
                "hit normal expande (1 salto, `score=null`, `via=hit`) el doc linkeado. El umbral 0.35 "
                "**no** filtra los expandidos: se inyectan siempre. Esto puede completar `needed_facts` "
                "que en v1 quedaban por debajo de umbral o fuera del top-k (p.ej. `f6`/`f7` en ch1, j4).\n")

        # ---- Salida de ejecucion ----
        f.write("\n## Salida de ejecución\n\n")
        f.write("```\n")
        tail = _LOG_LINES[-15:] if len(_LOG_LINES) > 15 else _LOG_LINES
        f.write("\n".join(tail))
        f.write("\n```\n")


if __name__ == "__main__":
    main()