"""Source-level contract evaluation; no model import, inference, or API calls."""
import ast, hashlib, json, platform, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def main():
    source=ROOT/'src/backend/app.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    wanted={'normalize_label','label_host','_extract_json','_string_values'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    constants=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCE_SUFFIXES' for t in n.targets)]
    if {n.name for n in nodes}!=wanted or len(constants)!=1:raise RuntimeError('Source definitions changed')
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+constants+nodes,type_ignores=[])
    env={'re':re,'json':json}
    exec(compile(ast.fix_missing_locations(module),'src/backend/app.py','exec'),env)
    cases=json.loads((HERE/'cases.json').read_text(encoding='utf-8'))
    baseline=json.loads((HERE/'baseline/cases.json').read_text(encoding='utf-8'))
    if cases != baseline:
        raise RuntimeError('Original 23 evaluation cases must remain unchanged')
    cases=[dict(c,suite='original') for c in cases]
    cases += [dict(c,suite='regression') for c in json.loads((HERE/'regression-cases.json').read_text(encoding='utf-8'))]
    if len({c['id'] for c in cases}) != len(cases):
        raise RuntimeError('Duplicate case IDs')
    rows=[]
    for c in cases:
        try:actual=env[c['function']](c['input'])
        except Exception as e:actual={'exception':type(e).__name__}
        rows.append({**c,'actual':actual,'status':'PASS' if actual==c['expected'] else 'FAIL'})
    report=dict(scope='source-level pure function contracts, not model/RAG/API/E2E quality',executed_at=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['src/backend/app.py','evaluation/contract-v1/cases.json','evaluation/contract-v1/regression-cases.json','evaluation/contract-v1/run.py']},original_cases_unchanged=True,total=len(rows),passed=sum(r['status']=='PASS' for r in rows),failed=sum(r['status']=='FAIL' for r in rows),suites={s:dict(total=sum(r['suite']==s for r in rows),passed=sum(r['suite']==s and r['status']=='PASS' for r in rows)) for s in ['original','regression']},cases=rows)
    (HERE/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    lines=['# 공개 코드 계약 평가','',f"총 {report['total']}건: PASS {report['passed']}, FAIL {report['failed']}",'','기존 23문항의 입력과 기대값은 유지했다. 제품의 label_host가 복합 작물명을 구분자 경계까지 보존하도록 패치하고, 전체 이름·별칭·대소문자·출처 접미사·유사 접두어 회귀 15문항을 추가했다.','','모델을 로드하지 않고 실제 app.py에서 네 함수를 추출하여 실행했다. 함수 본문을 평가용 코드로 교체하지 않았으며 외부 API와 GPU를 호출하지 않았다. 모델 추론 성능과 서버 통합 동작은 이 결과에 포함되지 않는다.','','| ID | 함수 | 결과 | 기대값 | 실제값 |','|---|---|---|---|---|']
    for r in rows:lines.append(f"| {r['id']} | {r['function']} | {r['status']} | {json.dumps(r['expected'],ensure_ascii=False)} | {json.dumps(r['actual'],ensure_ascii=False)} |")
    lines+=['','수정 전 22/23 결과와 원래 평가셋은 [baseline](baseline/RESULTS.md)에 보존했다. 이전 실패 PD-09가 같은 기대값 napa_cabbage를 반환하는지 재확인한다. 이 평가는 모델 정확도나 농가 외부검증을 대체하지 않으며 기존 B3/Small 점수와 합산하지 않는다.','','재현: `python evaluation/contract-v1/run.py` (저장소 루트). 표준 라이브러리만 사용하며 실패 시 종료 코드 1. fixture, 제품 코드, 실행기 SHA-256과 실행 환경은 results.json에 기록한다.','','평가셋·실행기·패치: Codex(ai-assisted). 개발 회귀이며 독립 블라인드 평가가 아니다. 사람 검토는 대기 중이다.']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:report[k] for k in ('total','passed','failed')}))
    return int(bool(report['failed']))
if __name__=='__main__':sys.exit(main())
