from __future__ import annotations
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];RUNTIME=ROOT/'skills/curate-question-bank/scripts/qbanswer';CLI=ROOT/'skills/curate-question-bank/scripts/qbanswer_cli.py'

def _trees():
    for p in list(RUNTIME.glob('*.py'))+[CLI]:yield p,ast.parse(p.read_text(encoding='utf-8'))

def test_m3_runtime_has_no_network_process_dynamic_exec_or_install_capability():
    forbidden_import_roots={'socket','http','urllib','requests','subprocess','multiprocessing','asyncio','pip','venv'}
    forbidden_calls={'eval','exec','compile','__import__'}
    hits=[]
    for p,t in _trees():
        for n in ast.walk(t):
            if isinstance(n,ast.Import):
                for a in n.names:
                    if a.name.split('.')[0] in forbidden_import_roots:hits.append((p.name,a.name))
            if isinstance(n,ast.ImportFrom) and (n.module or '').split('.')[0] in forbidden_import_roots:hits.append((p.name,n.module))
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in forbidden_calls:hits.append((p.name,n.func.id))
    assert hits==[]

def test_cli_only_routes_through_service_module():
    text=CLI.read_text(encoding='utf-8');assert 'from qbanswer.service import confirm,prepare,recover,reverify' in text
    assert 'from qbanswer.confirmation' not in text and 'from qbanswer.transaction' not in text

def test_runtime_exposes_no_ui_scoring_generation_or_non_single_choice_adapter():
    text='\n'.join(p.read_text(encoding='utf-8') for p in list(RUNTIME.glob('*.py'))+[CLI]).lower()
    forbidden=('flask','fastapi','tkinter','pyqt','score_answer','grade_answer','generate_answer','infer_answer','multiple_choice_adapter','true_false_adapter')
    assert all(token not in text for token in forbidden)
