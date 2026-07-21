#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harness de benchmark para Ternary Bonsai 27B servido en :8942 (API OpenAI).

Mismo oraculo (eval_set_50.json) y MISMA calificacion determinista que bench.py.
Unica diferencia: el transporte es /v1/chat/completions en http://127.0.0.1:8942.
El razonamiento llega en message.reasoning_content; la respuesta final limpia en
message.content. Es lento (~4,4 tok/s): timeout 900s por request, 1 reintento.
Escritura incremental: tras cada item reescribe bonsai_results_50.json completo.
"""
import json
import os
import re
import sys
import time
import argparse
import urllib.request
import urllib.error
import subprocess
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

CWD = os.path.dirname(os.path.abspath(__file__))
EVAL_SET = os.path.join(CWD, "eval_set_50.json")
RESULTS_JSON = os.path.join(CWD, "bonsai_results_50.json")

ENDPOINT = "http://127.0.0.1:8942/v1/chat/completions"
HEALTH = "http://127.0.0.1:8942/v1/models"
REQUEST_TIMEOUT = 900
CODE_TIMEOUT = 10
MAX_TOKENS = 6144
CATEGORIES = ["math", "coding", "instruction_following", "knowledge"]


def log(msg=""):
    print(str(msg), flush=True)


def bonsai_alive():
    for attempt in range(3):
        try:
            req = urllib.request.Request(HEALTH, method="GET")
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            return True
        except Exception as e:
            log(f"[bonsai ping intento {attempt+1}/3] error: {e!r}")
            if attempt < 2:
                time.sleep(10)
    return False


def call_bonsai(prompt):
    """Devuelve (data_dict_or_None, wall_or_None, error_str_or_None). 1 reintento."""
    payload = json.dumps({
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "top_p": 1.0,
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }).encode("utf-8")

    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                ENDPOINT,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                body = r.read().decode("utf-8", errors="replace")
            wall = time.time() - t0
            data = json.loads(body)
            return data, wall, None
        except Exception as e:
            last_err = repr(e)
            log(f"  [request error intento {attempt+1}/2] {last_err}")
            if attempt == 0:
                time.sleep(2)
    return None, None, last_err


# ---------- Calificadores (IDENTICOS a bench.py) ----------

def grade_math(answer, expected_number):
    pattern = r'[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+\.\d+|[-+]?\d+'
    matches = re.findall(pattern, answer)
    if not matches:
        return False, None, "sin numero"
    last = matches[-1].replace(",", "")
    try:
        val = float(last)
    except ValueError:
        return False, None, f"no parseable: {last!r}"
    ok = abs(val - float(expected_number)) <= 1e-6
    return ok, val, None


def extract_code(answer):
    fence = re.search(r'```(?:python)?\s*\n?(.*?)```', answer, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1)
    return answer


def grade_coding(answer, tests):
    code = extract_code(answer)
    program = code + "\n\n" + "\n".join(tests) + "\n"
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8", dir=CWD
        ) as tf:
            tmp_path = tf.name
            tf.write(program)
        final_path = os.path.join(CWD, "tmp_code_exec.py")
        os.replace(tmp_path, final_path)
        try:
            proc = subprocess.run(
                [sys.executable, final_path],
                timeout=CODE_TIMEOUT,
                capture_output=True,
                text=True,
            )
            ok = proc.returncode == 0
            return ok, None, (proc.stderr or proc.stdout or "")[:500]
        finally:
            try:
                os.remove(final_path)
            except OSError:
                pass
    except subprocess.TimeoutExpired:
        return False, None, "timeout 10s"
    except Exception as e:
        return False, None, f"exec error: {e!r}"


def grade_instruction(answer, check, expected):
    if check == "one_word_equals":
        s = answer.strip()
        s = re.sub(r'[.,;:!?]+$', '', s).strip()
        words = s.split()
        is_one_word = len(words) == 1
        ok = is_one_word and s.lower() == str(expected).lower()
        return ok, None, None
    elif check == "json_equals":
        s = answer.strip()
        i = s.find("{")
        j = s.rfind("}")
        if i != -1 and j != -1 and j > i:
            s = s[i:j + 1]
        try:
            parsed = json.loads(s)
        except Exception as e:
            return False, None, f"json invalido: {e!r}"
        ok = parsed == expected
        return ok, None, None
    elif check == "n_nonempty_lines":
        lines = [ln for ln in answer.splitlines() if ln.strip() != ""]
        bad = False
        for ln in lines:
            st = ln.strip()
            if re.match(r'\d+\.', st) or st.startswith("-") or st.startswith("*"):
                bad = True
                break
        ok = (len(lines) == int(expected)) and not bad
        return ok, None, ("lista-marker" if bad else None)
    elif check == "exact_stripped":
        ok = answer.strip() == str(expected)
        return ok, None, None
    elif check == "digits_sequence":
        digits = "".join(re.findall(r'\d', answer))
        ok = digits == str(expected)
        return ok, None, None
    else:
        return False, None, f"check desconocido: {check}"


def grade_knowledge(answer, expected_letter):
    m = re.search(r'(?<![A-Za-z])\(?([A-Da-d])\)?\.?(?![A-Za-z])', answer)
    if not m:
        return False, None, "sin letra A-D"
    letter = m.group(1).upper()
    ok = letter == str(expected_letter).upper()
    return ok, letter, None


# ---------- Metricas ----------

def perf_metrics(data, wall):
    """tokens/s del campo timings si viene; fallback a usage.completion_tokens/wall."""
    timings = data.get("timings") if isinstance(data, dict) else None
    if timings:
        tps = timings.get("predicted_per_second")
        if tps is None:
            n = timings.get("predicted_n") or timings.get("predicted_n_tokens")
            ms = timings.get("predicted_ms")
            if n and ms and ms > 0:
                tps = n / (ms / 1000.0)
        if tps is not None:
            return float(tps)
    usage = data.get("usage", {}) if isinstance(data, dict) else {}
    comp = usage.get("completion_tokens")
    if comp and wall and wall > 0:
        return comp / wall
    return None


def reasoning_tail(reasoning_content):
    if not reasoning_content:
        return ""
    return reasoning_content[-300:]


# ---------- Persistencia incremental ----------

def expected_of(item, cat):
    if cat == "math":
        return item["expected_number"]
    if cat == "coding":
        return item["tests"]
    if cat == "instruction_following":
        return item["expected"]
    if cat == "knowledge":
        return item["expected_letter"]
    return None


def aggregate(results):
    agg = {}
    tok_s_list = []
    for cat in CATEGORIES:
        cat_items = [r for r in results if r["category"] == cat]
        aciertos = sum(1 for r in cat_items if r["status"] == "pass")
        total = len(cat_items)
        pct = round(100 * aciertos / total, 2) if total else 0.0
        agg[cat] = {"aciertos": aciertos, "total": total, "porcentaje": pct}
        tok_s_list.extend(r.get("tokens_por_segundo") for r in cat_items)
    g_aciertos = sum(1 for r in results if r["status"] == "pass")
    g_total = len(results)
    g_pct = round(100 * g_aciertos / g_total, 2) if g_total else 0.0
    valid_tps = [t for t in tok_s_list if t is not None]
    avg_tps = round(sum(valid_tps) / len(valid_tps), 4) if valid_tps else 0.0
    global_agg = {"aciertos": g_aciertos, "total": g_total, "porcentaje": g_pct}
    return agg, global_agg, avg_tps


def save_results(results):
    agg, global_agg, avg_tps = aggregate(results)
    out = {
        "config": {
            "endpoint": ENDPOINT,
            "transport": "openai_chat_completions",
            "temperature": 0,
            "top_p": 1.0,
            "max_tokens": MAX_TOKENS,
            "request_timeout_s": REQUEST_TIMEOUT,
        },
        "items": results,
        "agregados_por_categoria": agg,
        "global": global_agg,
        "promedio_tokens_por_segundo": avg_tps,
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="Bench Bonsai 27B (:8942)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Corre solo los primeros N items (smoke).")
    parser.add_argument("--resume", action="store_true",
                        help="Salta items ya presentes en bonsai_results_50.json.")
    args = parser.parse_args()

    if not os.path.exists(EVAL_SET):
        print("BLOQUEADO: eval_set_50.json no existe en el cwd.")
        sys.exit(2)

    if not bonsai_alive():
        print("BLOQUEADO: :8942 no responde al health tras 3 intentos espaciados 10s.")
        sys.exit(2)

    with open(EVAL_SET, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    # lista plana en orden de categorias (mismo orden que bench.py)
    flat = []
    for cat in CATEGORIES:
        for item in eval_set.get(cat, []):
            flat.append((cat, item))

    if args.limit is not None:
        flat = flat[:args.limit]

    # resume: cargar resultados previos, indices ya hechos
    results = []
    done_ids = set()
    if args.resume and os.path.exists(RESULTS_JSON):
        try:
            with open(RESULTS_JSON, "r", encoding="utf-8") as f:
                prev = json.load(f)
            results = list(prev.get("items", []))
            done_ids = {r["id"] for r in results}
            log(f"[resume] {len(done_ids)} items ya presentes, se saltan.")
        except Exception as e:
            log(f"[resume] no se pudo leer previo ({e!r}); arranco limpio.")
            results = []
            done_ids = set()

    log(f"=== BENCH BONSAI START === endpoint={ENDPOINT} timeout={REQUEST_TIMEOUT}s "
        f"items_a_procesar={len(flat)} limit={args.limit} resume={args.resume}")

    for cat, item in flat:
        iid = item["id"]
        if iid in done_ids:
            log(f"[{iid}] ya presente (resume), salto.")
            continue
        prompt = item["prompt"]
        log(f"[{iid}/{cat}] llamando :8942...")
        data, wall, err = call_bonsai(prompt)

        if data is None:
            log(f"[{iid}] ERROR request: {err}")
            results.append({
                "id": iid, "category": cat, "status": "error",
                "expected": expected_of(item, cat),
                "respuesta_calificada": "",
                "raw_content": "",
                "reasoning_tail": "",
                "tokens_por_segundo": None,
                "wall_seconds": None,
                "detail": err,
            })
            save_results(results)
            continue

        # extraer content + reasoning
        msg = (data.get("choices", [{}])[0].get("message", {})
               if isinstance(data, dict) else {})
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        tps = perf_metrics(data, wall)

        # caso: content vacio -> fail con evidencia del thinking
        if not content.strip():
            log(f"[{iid}] content vacio (thinking agoto max_tokens)")
            results.append({
                "id": iid, "category": cat, "status": "fail",
                "expected": expected_of(item, cat),
                "respuesta_calificada": "",
                "raw_content": content,
                "reasoning_tail": reasoning_tail(reasoning),
                "tokens_por_segundo": round(tps, 4) if tps is not None else None,
                "wall_seconds": round(wall, 4),
                "detail": "sin contenido (thinking agotó max_tokens)",
            })
            save_results(results)
            log(f"[{iid}] fail | tok/s={tps if tps is not None else 'NA'} | wall={wall:.2f}s")
            continue

        # calificar (misma logica que bench.py, sobre content)
        detail = None
        if cat == "math":
            ok, _v, detail = grade_math(content, item["expected_number"])
        elif cat == "coding":
            ok, detail, extra = grade_coding(content, item["tests"])
            if extra and not ok:
                detail = (detail or "") + f" | stderr: {extra}"
        elif cat == "instruction_following":
            ok, _v, detail = grade_instruction(content, item["check"], item["expected"])
        elif cat == "knowledge":
            ok, _v, detail = grade_knowledge(content, item["expected_letter"])
        else:
            ok = False

        status = "pass" if ok else "fail"
        log(f"[{iid}] {status} | tok/s={tps if tps is not None else 'NA'} | "
            f"wall={wall:.2f}s | detail={detail}")

        results.append({
            "id": iid,
            "category": cat,
            "status": status,
            "expected": expected_of(item, cat),
            "respuesta_calificada": content[:300],
            "raw_content": content,
            "reasoning_tail": reasoning_tail(reasoning),
            "tokens_por_segundo": round(tps, 4) if tps is not None else None,
            "wall_seconds": round(wall, 4),
            "detail": detail,
        })
        save_results(results)

    # resumen final
    agg, global_agg, avg_tps = aggregate(results)
    log("\n=== RESUMEN ===")
    for cat in CATEGORIES:
        a = agg[cat]
        log(f"{cat}: {a['aciertos']}/{a['total']} = {a['porcentaje']}%")
    log(f"GLOBAL: {global_agg['aciertos']}/{global_agg['total']} = {global_agg['porcentaje']}%")
    log(f"Promedio tok/s: {avg_tps}")
    log(f"Escrito: {RESULTS_JSON}")
    log("=== BENCH BONSAI END ===")


if __name__ == "__main__":
    main()