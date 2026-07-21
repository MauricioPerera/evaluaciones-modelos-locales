"""Loop KDD: delega la implementación del contrato al modelo local y valida con los tests congelados."""
import json
import os
import re
import subprocess
import sys
import urllib.request

MODEL = sys.argv[1] if len(sys.argv) > 1 else "minicpm5-fable5-thinking"
API = "http://localhost:11434/api/generate"
MAX_ITER = 3
HERE = os.path.dirname(os.path.abspath(__file__))

CONTRACT = open(os.path.join(HERE, "TASK-CONTRACT.md"), encoding="utf-8").read()


def call_model(prompt):
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0, "top_p": 1.0, "num_predict": 16384},
    }).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)["response"]


def extract_code(text):
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    for b in reversed(blocks):
        if "def parse_duration" in b:
            return b
    return None


def run_frozen_tests():
    p = subprocess.run(
        [sys.executable, "-m", "unittest", "test_duration", "-v"],
        cwd=HERE, capture_output=True, text=True, timeout=60,
    )
    return p.returncode, (p.stdout + p.stderr)


base_prompt = (
    "You are a Python implementer. Implement EXACTLY the following task contract.\n\n"
    + CONTRACT
    + "\n\nKeep your reasoning brief. Return ONLY the complete content of duration.py "
    "inside a single python code block. No explanations outside the code block. Do not include tests."
)

if os.path.exists(os.path.join(HERE, "HINT.txt")):
    base_prompt += "\n\nHINT: " + open(os.path.join(HERE, "HINT.txt"), encoding="utf-8").read()

prompt = base_prompt
for i in range(1, MAX_ITER + 1):
    print(f"=== ITERACION {i} ===", flush=True)
    resp = call_model(prompt)
    code = extract_code(resp)
    if code is None:
        print("--- SIN BLOQUE DE CODIGO VALIDO (fallo de formato) ---")
        print(resp[-500:])
        prompt = (
            base_prompt
            + "\n\nIMPORTANT: your previous reply contained NO python code block with "
            "'def parse_duration'. Keep your reasoning SHORT and always end with the full "
            "duration.py inside ```python fences."
        )
        continue
    open(os.path.join(HERE, "duration.py"), "w", encoding="utf-8").write(code)
    print(f"--- codigo escrito ({len(code)} chars) ---")
    print(code)
    rc, out = run_frozen_tests()
    print(f"--- tests exit={rc} ---")
    print(out[-2000:])
    if rc == 0:
        print(f"VEREDICTO_TESTS: PASS en iteracion {i}")
        sys.exit(0)
    prompt = (
        base_prompt
        + "\n\nYour previous implementation FAILED the frozen tests. Previous code:\n```python\n"
        + code
        + "\n```\nTest output:\n"
        + out[-1500:]
        + "\nFix the implementation. Return ONLY the corrected duration.py in a python code block."
    )

print("VEREDICTO_TESTS: FAIL tras 3 iteraciones")
sys.exit(1)
