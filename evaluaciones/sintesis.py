#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sintesis.py — Mide el limite de sintesis multi-hecho del 1B (MiniCPM5-1B) via RAG-local.

2 condiciones por pregunta:
  R = retrieval real (rag-local aurora2, k=5, umbral 0.35)
  O = contexto oraculo (exactamente needed_facts, sin retrieval)
Grading determinista segun oraculo (expected_number / keywords_all).
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
ORACLE = os.path.join(CWD, "sintesis_oracle.json")
RESULTS = os.path.join(CWD, "sintesis_results.json")

RAG = "http://127.0.0.1:8937"
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "minicpm5-fable5-thinking"
COLL = "aurora2"
K = 5
THRESHOLD = 0.35
NUM_PREDICT = 1024
TIMEOUT = 120
RETRIES = 1  # 1 reintento => hasta 2 intentos

# Delimitador de fin de razonamiento del modelo, construido sin literal para
# evitar filtrado de tokens especiales en el pipeline de escritura.
THINK_END = chr(60) + "/think" + chr(62)  # "</think>"
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
}


def log(msg):
    print(msg, flush=True)


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


# ---------- SEMBRADO ----------
def build_doc(fact_id, fact):
    title = (fact.split(":")[-1].strip() if ":" in fact else fact)[:60]
    md = (
        "---\n"
        "type: fact\n"
        f"title: {title}\n"
        f"description: {fact}\n"
        "tags:\n"
        f"  - {COLL}\n"
        "---\n"
        f"{fact}\n"
    )
    return {"id": fact_id, "md": md}


def seed(facts):
    st, d = http_json("DELETE", f"{RAG}/collections/{COLL}", timeout=30)
    log(f"[seed] DELETE /collections/{COLL} -> {st} {str(d)[:120]}")
    time.sleep(1)
    docs = [build_doc(fid, fact) for fid, fact in facts.items()]
    body = {"name": COLL, "docs": docs}
    st, data = http_json("POST", f"{RAG}/collections", payload=body, timeout=60)
    log(f"[seed] POST /collections {COLL} ({len(docs)} docs) -> {st}")
    if st != 200:
        log(f"[seed] RESP: {str(data)[:300]}")
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
                         payload={"text": text, "k": K}, timeout=30)
    if st != 200 or not isinstance(data, list):
        return []
    return data


def build_context(hits):
    keep = [h for h in hits if float(h.get("score", 0.0)) >= THRESHOLD]
    if not keep:
        return "", []
    lines = "\n".join(f"- {h.get('description', '')}" for h in keep)
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
    facts = oracle["facts"]
    preguntas = oracle["preguntas"]

    ok_rag, ev_rag = health_rag()
    ok_oll, ev_oll = health_ollama()
    log(f"[health] rag-local: {ok_rag} | {ev_rag}")
    log(f"[health] ollama:    {ok_oll} | {ev_oll}")
    if not (ok_rag and ok_oll):
        log("BLOQUEADO: servicio no responde tras 3 intentos.")
        with open(RESULTS, "w", encoding="utf-8") as f:
            json.dump({"bloqueado": True, "ev_rag": ev_rag, "ev_oll": ev_oll}, f, ensure_ascii=False, indent=2)
        sys.exit(2)

    seed(facts)
    count, count_data = count_collection()
    count_evidence = json.dumps(count_data, ensure_ascii=False)[:800] if count_data else "n/a"
    log(f"[seed] count {COLL} == {count} (esperado 14)")
    assert count == 14, f"count != 14 (got {count})"

    evaluaciones = []
    for preg in preguntas:
        pid = preg["id"]
        tier = preg["tier"]
        needed = preg.get("needed_facts", [])
        q = preg["q"]
        log(f"\n=== {pid} (tier={tier}) ===")

        for cond in ("R", "O"):
            if cond == "R":
                hits = query_rag(q)
                scores = [{"id": h.get("id"), "score": h.get("score"),
                           "description": h.get("description", "")} for h in hits]
                contexto, keep = build_context(hits)
                injected = [h.get("id") for h in keep]
            else:
                contexto = "Facts from memory:\n" + "\n".join(f"- {facts[fid]}" for fid in needed)
                scores = []
                injected = list(needed)

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
                "needed_facts": needed,
                "retrieval_completo": retrieval_completo,
                "wall_seconds": round(wall, 2),
            }
            if err:
                ev["error"] = err
            evaluaciones.append(ev)
            log(f"  [{cond}] {verdict} | inyectados={injected} | "
                f"retr_compl={retrieval_completo} | wall={wall:.1f}s | final={ft[:80]!r}")

            with open(RESULTS, "w", encoding="utf-8") as f:
                json.dump({"meta": {"modelo": MODEL, "coleccion": COLL, "k": K, "umbral": THRESHOLD,
                                    "decisiones": DECISIONES},
                           "count_aurora2": count, "count_evidence": count_evidence,
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

    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump({"meta": {"modelo": MODEL, "coleccion": COLL, "k": K, "umbral": THRESHOLD,
                            "decisiones": DECISIONES},
                   "count_aurora2": count, "count_evidence": count_evidence,
                   "evaluaciones": evaluaciones,
                   "agregados": {"by_tier_cond": by_tier_cond, "by_cond": by_cond,
                                 "atribucion_fallos_ids": atrib,
                                 "atribucion_fallos_counts": atrib_counts}},
                  f, ensure_ascii=False, indent=2)

    log("\n=== RESUMEN ===")
    log(f"count {COLL}: {count}")
    for c in ("R", "O"):
        log(f"cond {c}: {by_cond[c]['pass']}/{by_cond[c]['total']} ({by_cond[c]['pct']}%)")
    log(f"atribucion: {atrib_counts}")
    sys.exit(0)


if __name__ == "__main__":
    main()