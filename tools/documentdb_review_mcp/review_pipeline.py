#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, json, math, re, sqlite3, subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Set

EXCLUDE_DIRS={".git","build","dist","node_modules","__pycache__",".cache",".venv","venv"}
TOKEN_RE=re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
URL_RE=re.compile(r"https?://[\w\.-]+")
SERVICE_ENV_RE=re.compile(r"[A-Z0-9_]*(SERVICE|HOST|URL|ENDPOINT)[A-Z0-9_]*")

@dataclass
class Symbol:
    name:str; qualname:str; kind:str; signature:str; decorators:List[str]; bases:List[str]; start_line:int; end_line:int; docstring:str

def _iter_python_files(repo:Path):
    return [p for p in repo.rglob('*.py') if not any(x in EXCLUDE_DIRS for x in p.parts)]

def _expr(n):
    if isinstance(n,ast.Name): return n.id
    if isinstance(n,ast.Attribute): return f"{_expr(n.value)}.{n.attr}"
    if isinstance(n,ast.Call): return _expr(n.func)
    if isinstance(n,ast.Constant): return repr(n.value)
    return '<expr>'

def _sig(fn):
    a=fn.args; b=[x.arg for x in a.args]
    if a.vararg:b.append('*'+a.vararg.arg)
    b.extend(x.arg for x in a.kwonlyargs)
    if a.kwarg:b.append('**'+a.kwarg.arg)
    return '('+', '.join(b)+')'

def _extract(path:Path):
    src=path.read_text(encoding='utf-8',errors='ignore'); tree=ast.parse(src)
    imports=set(); exports=[]; symbols=[]; calls=set(); inherits=set(); svc_calls=[]; svc_envs=set(URL_RE.findall(src)); urls=set(URL_RE.findall(src))
    for t in TOKEN_RE.findall(src):
        if SERVICE_ENV_RE.fullmatch(t): svc_envs.add(t)
    for n in tree.body:
        if isinstance(n,ast.Assign):
            for t in n.targets:
                if isinstance(t,ast.Name) and t.id=='__all__' and isinstance(n.value,(ast.List,ast.Tuple)):
                    exports.extend([e.value for e in n.value.elts if isinstance(e,ast.Constant) and isinstance(e.value,str)])
    class V(ast.NodeVisitor):
        def __init__(self): self.st=[]
        def q(self,n): return '.'.join(self.st+[n]) if self.st else n
        def visit_Import(self,n): imports.update(a.name for a in n.names)
        def visit_ImportFrom(self,n):
            if n.module: imports.add(n.module)
        def visit_ClassDef(self,n):
            q=self.q(n.name); bases=[_expr(b) for b in n.bases]
            for b in bases: inherits.add((q,b))
            symbols.append(Symbol(n.name,q,'class','',[_expr(d) for d in n.decorator_list],bases,n.lineno,getattr(n,'end_lineno',n.lineno),ast.get_docstring(n) or ''))
            self.st.append(n.name); self.generic_visit(n); self.st.pop()
        def _fn(self,n,k):
            q=self.q(n.name)
            symbols.append(Symbol(n.name,q,k,_sig(n),[_expr(d) for d in n.decorator_list],[],n.lineno,getattr(n,'end_lineno',n.lineno),ast.get_docstring(n) or ''))
            for c in ast.walk(n):
                if isinstance(c,ast.Call):
                    callee=_expr(c.func); calls.add((q,callee))
                    if callee in {"requests.get","requests.post","requests.put","requests.delete","httpx.get","httpx.post","httpx.put","httpx.delete","urllib.request.urlopen","urlopen"}:
                        svc_calls.append({"caller":q,"client":callee,"endpoint":_expr(c.args[0]) if c.args else '<dynamic>',"line":c.lineno})
            self.st.append(n.name); self.generic_visit(n); self.st.pop()
        def visit_FunctionDef(self,n): self._fn(n,'function')
        def visit_AsyncFunctionDef(self,n): self._fn(n,'async_function')
    V().visit(tree); symbols.sort(key=lambda x:x.start_line)
    return ast.get_docstring(tree) or '',sorted(imports),sorted(set(exports)),symbols,calls,inherits,svc_calls,sorted(svc_envs),sorted(urls),src

def _db(path:Path):
    c=sqlite3.connect(path)
    c.executescript('''
    create table if not exists files(path text primary key,module_doc text,service_envs text,service_urls text);
    create table if not exists symbols(qualname text primary key,path text,name text,kind text,signature text,start_line int,end_line int,decorators text,bases text,docstring text);
    create table if not exists edges(kind text,src text,dst text,path text);
    create index if not exists idx_edges_kind_dst on edges(kind,dst);
    create table if not exists chunks(id integer primary key,path text,start_line int,end_line int,text text);
    create table if not exists tokens(token text,path text,freq int);
    create index if not exists idx_tokens_token on tokens(token);
    create table if not exists vector_docs(id text primary key,path text,text text);
    ''')
    return c

def _chunks(lines:int,size=180,overlap=40):
    s=1
    while s<=lines:
        e=min(lines,s+size-1); yield s,e
        if e==lines: break
        s=e-overlap+1

def build_index(repo:Path,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    dbp=out/'review_index.db'; conn=_db(dbp); cur=conn.cursor()
    cur.executescript('delete from files; delete from symbols; delete from edges; delete from chunks; delete from tokens; delete from vector_docs;')
    py=_iter_python_files(repo); modmap={str(p.relative_to(repo)):str(p.relative_to(repo)).replace('/','.').removesuffix('.py') for p in py}; mod2f={v:k for k,v in modmap.items()}
    json_payload={"files":{},"graphs":defaultdict(dict)}
    reverse_imports=defaultdict(list); reverse_services=defaultdict(list)
    for p in py:
        rel=str(p.relative_to(repo))
        try: md,imports,exports,syms,calls,inh,svc_calls,svc_envs,urls,src=_extract(p)
        except SyntaxError: continue
        cur.execute('insert into files values (?,?,?,?)',(rel,md,json.dumps(svc_envs),json.dumps(urls)))
        json_payload['files'][rel]={"imports":imports,"exports":exports,"service_calls":svc_calls,"service_urls":urls,"service_envs":svc_envs,"symbols":[asdict(s) for s in syms]}
        for s in syms:
            cur.execute('insert into symbols values (?,?,?,?,?,?,?,?,?,?)',(s.qualname,rel,s.name,s.kind,s.signature,s.start_line,s.end_line,json.dumps(s.decorators),json.dumps(s.bases),s.docstring))
            cur.execute('insert or replace into vector_docs values (?,?,?)',(f"sym:{s.qualname}",rel,f"{s.kind} {s.qualname} {s.signature} {s.docstring}"))
        for i in imports:
            cur.execute('insert into edges values (?,?,?,?)',('import',rel,i,rel))
            tgt=mod2f.get(i)
            if tgt: reverse_imports[tgt].append(rel)
        for a,b in calls: cur.execute('insert into edges values (?,?,?,?)',('call',a,b,rel))
        for c,b in inh: cur.execute('insert into edges values (?,?,?,?)',('inherit',c,b,rel))
        for sc in svc_calls:
            ep=sc['endpoint']; cur.execute('insert into edges values (?,?,?,?)',('service',rel,ep,rel)); reverse_services[ep].append(rel)
        lines=src.splitlines()
        for a,b in _chunks(len(lines)):
            txt='\n'.join(lines[a-1:b]); cur.execute('insert into chunks(path,start_line,end_line,text) values (?,?,?,?)',(rel,a,b,txt))
        for t,f in Counter(x.lower() for x in TOKEN_RE.findall(src)).items():
            cur.execute('insert into tokens values (?,?,?)',(t,rel,f))
        cur.execute('insert or replace into vector_docs values (?,?,?)',(f"file:{rel}",rel,md+'\n'+ ' '.join([x.qualname for x in syms])))
    conn.commit()
    json_payload['graphs']={"reverse_imports":dict(reverse_imports),"reverse_service_dependencies":dict(reverse_services)}
    (out/'python_index.json').write_text(json.dumps(json_payload,indent=2),encoding='utf-8')
    conn.close()

def _run(cmd):
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,check=False)
        return {"cmd":" ".join(cmd),"returncode":p.returncode,"stdout":p.stdout[-2000:],"stderr":p.stderr[-2000:]}
    except FileNotFoundError:
        return {"cmd":" ".join(cmd),"returncode":127,"stdout":"","stderr":"not installed"}

def _diff(repo,base,head):
    return subprocess.run(["git","-C",str(repo),"diff","--unified=0",base,head],capture_output=True,text=True,check=True).stdout

def _parse(diff):
    out=[]; p=None; ln=None
    for line in diff.splitlines():
        if line.startswith('+++ b/'): p=line[6:]; ln=None
        elif line.startswith('@@'): ln=int(line.split('+',1)[1].split(' ',1)[0].split(',')[0])
        elif p and ln is not None:
            if line.startswith('+') and not line.startswith('+++'): out.append((p,ln)); ln+=1
            elif line.startswith('-') and not line.startswith('---'): pass
            else: ln+=1
    return out

def _symbol(cur,path,line):
    r=cur.execute('select qualname,signature,kind,start_line,end_line from symbols where path=? and ? between start_line and end_line order by (end_line-start_line) asc limit 1',(path,line)).fetchone()
    return None if not r else {"qualname":r[0],"signature":r[1],"kind":r[2]}

def _rag_context(cur,path,query,topk=3):
    toks=[t.lower() for t in TOKEN_RE.findall(query)]
    scores=defaultdict(float)
    for t in toks:
        for p,f in cur.execute('select path,freq from tokens where token=?',(t,)).fetchall():
            scores[p]+=f
    best=sorted(scores.items(),key=lambda x:x[1],reverse=True)[:topk]
    ctx=[]
    for p,_ in best:
        row=cur.execute('select text from chunks where path=? limit 1',(p,)).fetchone()
        if row: ctx.append({"path":p,"preview":row[0][:240]})
    return ctx



def _build_llm_review_input(cur, changed_findings):
    """Build structured context pack intended for direct LLM review."""
    packs = []
    for f in changed_findings:
        path = f["file"]
        line = f["line"]
        chunk = cur.execute(
            'select start_line,end_line,text from chunks where path=? and ? between start_line and end_line limit 1',
            (path, line),
        ).fetchone()
        packs.append({
            "file": path,
            "line": line,
            "symbol": f.get("symbol"),
            "severity": f.get("severity"),
            "impacted": f.get("impacted", {}),
            "code_context": {
                "start_line": chunk[0] if chunk else None,
                "end_line": chunk[1] if chunk else None,
                "text": chunk[2] if chunk else "",
            },
            "rag_context": f.get("rag_context", []),
        })

    system_prompt = (
        "You are a senior code reviewer. Use the provided structured static-analysis context and code snippets "
        "to evaluate correctness, performance, security, and test adequacy. For each finding, provide: "
        "(1) risk explanation, (2) concrete code fix suggestion, (3) test cases to add, and (4) confidence."
    )
    return {"system_prompt": system_prompt, "findings_context": packs}


def review(repo:Path,out:Path,base:str,head:str):
    db=sqlite3.connect(out/'review_index.db'); cur=db.cursor()
    changes=_parse(_diff(repo,base,head))
    tools=[_run(["ruff","check",str(repo)]),_run(["pyright",str(repo)]),_run(["bandit","-r",str(repo),"-q"]),_run(["semgrep","--config=auto",str(repo)])]
    findings=[]
    for path,line in changes:
        if not path.endswith('.py'): continue
        s=_symbol(cur,path,line)
        if not s: continue
        imp=[x[0] for x in cur.execute('select src from edges where kind="call" and dst=?',(s['qualname'],)).fetchall()]
        rimp=[x[0] for x in cur.execute('select src from edges where kind="import" and dst=?',(path.replace('/','.').removesuffix('.py'),)).fetchall()]
        service_eps=[x[0] for x in cur.execute('select dst from edges where kind="service" and src=?',(path,)).fetchall()]
        svc_dep=[]
        for ep in service_eps: svc_dep.extend([x[0] for x in cur.execute('select src from edges where kind="service" and dst=?',(ep,)).fetchall()])
        impacted={"callers":sorted(set(imp)),"imported_dependents":sorted(set(rimp)),"service_dependents":sorted(set(svc_dep))}
        risk=1+sum(len(v) for v in impacted.values()); sev='high' if risk>=6 else 'medium' if risk>=3 else 'low'
        ctx=_rag_context(cur,path,f"{path} {s['qualname']} {s['signature']}")
        findings.append({"file":path,"line":line,"symbol":s['qualname'],"severity":sev,"confidence":min(0.9,0.35+math.log2(risk+1)/4),"impacted":impacted,"rag_context":ctx})
    findings.sort(key=lambda x:({'high':0,'medium':1,'low':2}[x['severity']],-x['confidence']))
    llm_input = _build_llm_review_input(cur, findings)
    report={"base":base,"head":head,"storage":str(out/'review_index.db'),"rag_enabled":True,"deterministic_tools":tools,"findings":findings,"llm_review_input":llm_input}
    (out/'review_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    db.close()

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
    i=sp.add_parser('index'); i.add_argument('--repo',required=True); i.add_argument('--out',required=True)
    r=sp.add_parser('review'); r.add_argument('--repo',required=True); r.add_argument('--out',required=True); r.add_argument('--base',required=True); r.add_argument('--head',required=True)
    a=ap.parse_args(); repo=Path(a.repo).resolve(); out=Path(a.out).resolve()
    if a.cmd=='index': build_index(repo,out); print(f"Index written to {out/'python_index.json'} and {out/'review_index.db'}")
    else: review(repo,out,a.base,a.head); print(f"Review report written to {out/'review_report.json'}")

if __name__=='__main__': main()
