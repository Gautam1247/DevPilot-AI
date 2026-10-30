import {useEffect, useRef, useState} from 'react';
import {ArrowDownToLine, ArrowRight, Box, Braces, Check, CheckCheck, ChevronRight, CircleAlert, Clock3, Code2, FileArchive, FileCode2, GitBranch, History, Info, LayoutDashboard, LoaderCircle, Plus, RefreshCw, ShieldCheck, Sparkles, Terminal, UploadCloud, X} from 'lucide-react';
import {api} from './api';
import type {Health, Result, Session, TestRun} from './types';

const phases = [['queued','Queued'], ['running_baseline','Running baseline tests'], ['analyzing_failure','Analyzing failure'], ['generating_patch','Generating patch'], ['validating_patch','Validating patch'], ['running_verification','Running verification tests']];
const terminal = (r: Result) => r.phase === 'completed' || r.phase === 'failed';
const label = (status: string) => status.toLowerCase().replaceAll('_',' ');

function Badge({result}:{result:Result}) { return <span className={`badge ${result.status.toLowerCase()}`}>{result.status === 'VERIFIED' ? <ShieldCheck size={13}/> : <span className="status-dot"/>}{label(result.status)}</span>; }

function TestSummary({title, run}:{title:string; run:TestRun|null}) {
  const count = (status:string) => Object.values(run?.tests || {}).filter(v => v === status).length;
  return <div className="test-summary"><div className="section-label">{title}<span>{run ? `${run.duration.toFixed(1)}s` : '—'}</span></div>{run ? <><div className="test-count"><strong className="green">{count('passed')}</strong><span>passed</span><strong className="red">{count('failed')}</strong><span>failed</span><strong>{count('skipped')}</strong><span>skipped</span></div><p>{run.collected.length} collected · exit {run.exit_code}{!run.complete && ' · incomplete'}</p></> : <p className="muted py-5">Awaiting test execution</p>}</div>;
}

export default function App() {
  const [page, setPage] = useState('dashboard');
  const [health, setHealth] = useState<Health|null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string|null>(null);
  const [file, setFile] = useState<File|null>(null);
  const [busy, setBusy] = useState(false);
  const [uploadPhase, setUploadPhase] = useState('');
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const [pollPaused, setPollPaused] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const submission = useRef(false);
  const current = sessions.find(s => s.project.project_id === activeId);
  const result = current?.project;
  const running = sessions.some(s => !terminal(s.project) && s.project.phase !== 'ready');
  const done = sessions.filter(s => terminal(s.project));
  const verified = done.filter(s => s.project.status === 'VERIFIED').length;
  const changes = done.filter(s => s.project.approved).length;
  const update = (project:Result) => setSessions(old => old.map(s => s.project.project_id === project.project_id ? {...s, project} : s));
  const refreshHealth = () => api.health().then(setHealth).catch(() => setError('Backend unavailable. Start the FastAPI server on port 8000.'));
  useEffect(() => {void refreshHealth();}, []);

  const polling = sessions.find(s => !terminal(s.project) && s.project.phase !== 'ready');
  useEffect(() => {
    if (!polling || pollPaused) return;
    let cancelled = false;
    let timer:ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api.results(polling.project.project_id, polling.capability_token);
        if (cancelled) return;
        update(next);
        if (!terminal(next)) timer = setTimeout(poll, 1000);
      } catch (e) { if (!cancelled) {setError((e as Error).message); setPollPaused(true);} }
    };
    timer = setTimeout(poll, 500);
    return () => {cancelled = true; clearTimeout(timer);};
  }, [polling?.project.project_id, pollPaused]);

  function choose(next?:File) {
    setError('');
    if (!next) return;
    if (!next.name.toLowerCase().endsWith('.zip')) {setError('Choose a Python project packaged as a .zip file.'); return;}
    if (next.size > (health?.max_upload_bytes || 5*1024*1024)) {setError('This ZIP exceeds the upload size limit.'); return;}
    if (!/^[A-Za-z0-9_ .-]+$/.test(next.name)) {setError('Rename the ZIP using letters, numbers, spaces, dots, underscores or hyphens.'); return;}
    setFile(next);
  }

  async function start() {
    if (!file || submission.current || running) return;
    submission.current = true; setBusy(true); setError(''); setUploadPhase('Uploading and validating project');
    let created:Session|undefined;
    try {
      created = await api.upload(file);
      setSessions(old => [created!, ...old]); setActiveId(created.project.project_id); setPage('analysis');
      setUploadPhase('Starting sandbox');
      update(await api.analyze(created.project.project_id, created.capability_token));
      setPollPaused(false); setFile(null);
    } catch (e) {setError((e as Error).message);}
    finally {setBusy(false); setUploadPhase(''); submission.current = false;}
  }

  async function act(action: 'approve'|'reject'|'download'|'retry') {
    if (!current || busy) return;
    setBusy(true); setError('');
    try {
      const {project,capability_token:token} = current;
      if (action === 'download') await api.download(project.project_id,token);
      else if (action === 'retry') {update(await api.analyze(project.project_id, token)); setPollPaused(false);}
      else update(await api.approve(project.project_id,token,action === 'approve'));
    } catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }

  const upload = <section className="panel upload-panel"><div className="panel-heading"><div className="flex items-center gap-3"><div className="icon-tile"><Plus size={18}/></div><div><h2>Start a new analysis</h2><p>One project. A clear path from failure to fix.</p></div></div><span className="small-tag">PYTHON + PYTEST</span></div>
    <div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={e => {e.preventDefault(); if (!busy && !running) setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={e => {e.preventDefault(); setDragging(false); if (!busy && !running) choose(e.dataTransfer.files[0]);}}>
      <div className="upload-icon">{file ? <FileArchive size={29}/> : <UploadCloud size={29}/>}</div><h3>{file ? file.name : 'Drop your Python project here'}</h3><p>{file ? `${(file.size/1024).toFixed(1)} KB · ZIP archive ready` : 'A small codebase, its tests, and a bug worth fixing.'}</p>
      <input ref={input} type="file" accept=".zip,application/zip" className="sr-only" aria-label="Choose ZIP project" disabled={busy || running} onChange={e => {choose(e.target.files?.[0]); e.target.value='';}}/>
      <button className="button secondary" disabled={busy || running} onClick={() => input.current?.click()}>{file ? 'Choose another file' : 'Browse files'}<ChevronRight size={15}/></button>
      <span className="drop-hint">.zip only <span>·</span> up to {Math.round((health?.max_upload_bytes || 5242880)/1024/1024)} MB <span>·</span> no dependency installation</span>
    </div>
    <div className="upload-footer"><span><ShieldCheck size={15}/> Code runs in an isolated Docker sandbox</span><div className="flex gap-2">{file && <button className="button ghost" disabled={busy || running} onClick={() => setFile(null)}>Clear</button>}<button className="button primary" onClick={start} disabled={!file || busy || running || !health?.docker_available || !health?.ai_ready}>{busy ? <LoaderCircle size={16} className="spin"/> : <Sparkles size={16}/>} {uploadPhase || 'Analyze project'}{!busy && <ArrowRight size={16}/>}</button></div></div>
  </section>;

  const history = <section className="panel history-panel"><div className="panel-heading"><div><h2>Recent analyses</h2><p>Your debugging activity in this session.</p></div><span className="small-tag">{sessions.length} PROJECT{sessions.length !== 1 ? 'S' : ''}</span></div>{sessions.length ? <div className="history-list">{sessions.map(s => <button className="history-row" key={s.project.project_id} onClick={() => {setActiveId(s.project.project_id);setPage('analysis');setError('');}}><FileCode2 size={20}/><span className="history-name"><strong>{s.project.name}</strong><small>{new Date(s.project.created_at*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} {s.project.mock_generated && '· MOCK'}</small></span><Badge result={s.project}/><ChevronRight size={16}/></button>)}</div> : <div className="empty"><div className="empty-icon"><GitBranch size={25}/></div><h3>Your next fix starts here</h3><p>Upload a project to see its diagnosis, test evidence,<br/>and proposed patch in one place.</p></div>}</section>;

  return <div className="app-shell"><aside className="sidebar"><a href="#" className="brand" onClick={e => {e.preventDefault();setPage('dashboard');}}><div className="brand-mark"><Braces size={24}/></div><span>DevPilot<span className="brand-ai">AI</span></span></a><div className="workspace-label"><span className="status-dot"/> LOCAL WORKSPACE</div><span className="nav-label">WORKSPACE</span><nav>{[{id:'dashboard',name:'Dashboard',icon:LayoutDashboard},{id:'new',name:'New analysis',icon:Plus},{id:'history',name:'Recent analyses',icon:History}].map(item => <button className={page === item.id ? 'active' : ''} key={item.id} onClick={() => {setPage(item.id);setError('');}}><item.icon size={18}/>{item.name}{item.id === 'history' && <span className="nav-count">{sessions.length}</span>}</button>)}</nav><div className="sidebar-bottom"><div className="principle"><ShieldCheck size={20}/><strong>Evidence before confidence.</strong><p>AI proposes. Tests verify.<br/>You approve.</p></div><button className={`about-link ${page === 'about' ? 'active' : ''}`} onClick={() => setPage('about')}><Info size={17}/> About DevPilot <ArrowRight size={14}/></button><div className="local-profile"><div className="avatar"><Terminal size={17}/></div><div><strong>Local developer</strong><small>Private development session</small></div><span className="online-dot"/></div></div></aside>
  <div className="main-shell"><header className="topbar"><div><span className="muted">Workspace</span><ChevronRight size={13}/><span>{page === 'analysis' ? 'Analysis results' : page === 'new' ? 'New analysis' : page === 'history' ? 'Recent analyses' : page === 'about' ? 'About' : 'Dashboard'}</span></div><div className="topbar-status"><span className={`status-dot ${health?.docker_available ? 'green-bg' : ''}`}/>{health?.docker_available ? 'Sandbox connected' : 'Sandbox offline'}<span className="topbar-divider"/><span className="version">MVP / v0.1</span></div></header>
  <main><div className="page-heading"><div><div className="eyebrow">INTELLIGENT PYTHON DEBUGGING</div><h1>{page === 'analysis' ? 'From failure to evidence.' : page === 'new' ? 'Let’s investigate.' : page === 'history' ? 'Your debugging trail.' : page === 'about' ? 'Built on verifiable results.' : 'Less debugging. More building.'}</h1><p>{page === 'analysis' ? result?.name : 'Find the root cause, review a focused fix, and verify it against your tests.'}</p></div><span className="session-tag"><span className="online-dot"/> Local session</span></div>
  {error && <div className="alert error" role="alert"><CircleAlert size={18}/><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
  {health?.mock_ai && <div className="mock-banner"><div className="flex items-center gap-2"><Box size={16}/><strong>MOCK AI MODE</strong><span>Deterministic benchmark patches. Test execution still requires Docker.</span></div><span className="small-tag">NO API CALLS</span></div>}
  {(!health?.docker_available || !health.ai_ready) && <div className="alert warning"><CircleAlert size={18}/><span>{!health ? 'Checking local services…' : !health.docker_available ? health.message : 'Gemini is not configured. Add a backend API key or enable mock mode.'}</span><button className="text-button" onClick={() => void refreshHealth()}><RefreshCw size={14}/> Recheck</button></div>}
  {page === 'dashboard' && <><div className="metrics"><div className="metric"><div><span>Analyses completed</span><Code2 size={17}/></div><strong>{done.length.toString().padStart(2,'0')}</strong><small>Completed in this session</small></div><div className="metric"><div><span>Verified improvements</span><ShieldCheck size={17}/></div><strong>{verified.toString().padStart(2,'0')}<span className="metric-accent">verified</span></strong><small>Target passes, no detected regressions</small></div><div className="metric"><div><span>Patches approved</span><CheckCheck size={17}/></div><strong>{changes.toString().padStart(2,'0')}</strong><small>Reviewed and approved by you</small></div></div><div className="dashboard-grid"><div>{upload}{history}</div><aside className="right-column"><section className="workflow panel"><span className="section-kicker">THE WORKFLOW</span><h2>A fix you can inspect.</h2>{[{icon:Terminal,title:'Reproduce the failure',text:'Run your existing pytest suite inside a restricted container.'},{icon:Sparkles,title:'Understand the cause',text:'Get a focused diagnosis and a patch to one source file.'},{icon:ShieldCheck,title:'Verify with evidence',text:'Compare the target test and full suite before and after.'},{icon:CheckCheck,title:'Keep the final say',text:'Review the diff. Approve it. Download your patched project.'}].map((item,i) => <div className="workflow-step" key={item.title}><div className="step-icon"><item.icon size={17}/></div><div><small>0{i+1}</small><h3>{item.title}</h3><p>{item.text}</p></div></div>)}</section><section className="tip-card"><div className="flex items-center gap-2"><GitBranch size={17}/><h3>Have a reproducible bug?</h3></div><p>Include your source and pytest tests. The three bundled benchmarks are a good place to start.</p><button className="text-button" onClick={() => setPage('about')}>View project requirements <ArrowRight size={14}/></button></section></aside></div></>}
  {page === 'new' && upload}{page === 'history' && <>{history}<p className="footnote">Session capabilities stay in memory. Refreshing this page clears access to recent projects.</p></>}
  {page === 'about' && <section className="panel about-panel"><ShieldCheck className="accent" size={30}/><h2>AI proposes. Deterministic validation verifies. You approve.</h2><p>DevPilot accepts small, UTF-8 Python projects with pytest tests. It never installs uploaded dependencies and never runs uploaded Python on the host. Tests execute in a non-root Docker container with no network, resource limits, and a read-only project mount.</p><h3>Prepare your project</h3><p>Include .py files and optional README.md, README.txt, LICENSE, requirements.txt or pyproject.toml. Hidden files, binaries, secrets and links are rejected. Metadata is never installed or used as pytest configuration. Tests use pytest defaults; conftest.py and third-party pytest plugins are disabled in this MVP.</p><h3>Try a benchmark</h3><pre>Compress-Archive -Path .\benchmarks\discount_bug\* -DestinationPath .\discount_bug.zip</pre><p>Upload the ZIP. Mock mode supports the discount, off-by-one and sorting benchmarks. It provides a labeled deterministic proposal; actual verification still runs in Docker.</p><h3>What “verified” means</h3><p>The previously failing target passes in both a targeted run and the complete suite, the collected tests stay the same, and previously passing tests remain passing. Other existing failures may remain; full-suite success is reported separately.</p><h3>Local MVP boundaries</h3><p>Capability tokens expire after two hours by default and stay only in browser memory. Restarting the backend clears session access. Docker limits mitigate risk but do not make this a public multi-tenant execution service. Test evidence assumes the uploaded project is not actively trying to forge pytest reports. Review any patch before using it.</p></section>}
  {page === 'analysis' && result && <>{!terminal(result) && <section className="panel progress-panel" aria-live="polite"><div className="flex items-center gap-3"><LoaderCircle className="spin accent" size={22}/><div><h2>{uploadPhase || phases.find(p => p[0] === result.phase)?.[1] || 'Ready for analysis'}</h2><p>Live backend state · no estimated percentages</p></div></div><div className="progress-steps">{phases.slice(1).map(([id,title],i) => {const index = phases.findIndex(p => p[0] === result.phase)-1; return <div className={i <= index ? 'reached' : ''} key={id}><span>{i < index ? <Check size={12}/> : i+1}</span>{title}</div>;})}</div>{pollPaused && <button className="button secondary" onClick={() => {setPollPaused(false);setError('');}}>Resume status updates</button>}{result.phase === 'ready' && <button className="button primary" disabled={busy} onClick={() => void act('retry')}>Start analysis</button>}</section>}
    {terminal(result) && <section className={`outcome ${result.status.toLowerCase()}`}><div className="flex gap-3 items-start">{result.status === 'VERIFIED' ? <ShieldCheck size={27}/> : <CircleAlert size={27}/>}<div><Badge result={result}/><h2>{result.status === 'VERIFIED' ? result.full_suite_success ? 'Verified improvement. All collected tests pass.' : 'Verified improvement. Review remaining test outcomes.' : result.status === 'NO_BASELINE_FAILURE' ? 'No failing baseline to repair.' : result.status === 'FAILED' ? 'The patch did not satisfy verification.' : 'Analysis needs your attention.'}</h2><p>{result.message}</p></div></div><div className="result-meta"><span><Clock3 size={14}/>{result.duration.toFixed(1)}s</span><span><Box size={14}/>{result.model}</span>{result.mock_generated && <strong>MOCK PROPOSAL</strong>}</div></section>}
    <div className="results-grid"><section className="panel diagnosis"><div className="panel-heading"><h2 className="flex items-center gap-2"><Sparkles size={17}/> Diagnosis</h2>{result.patch && <span className="small-tag">ONE FILE</span>}</div><div className="panel-body">{result.patch ? <><h3>{result.patch.root_cause}</h3><p>{result.patch.explanation}</p><div className="file-chip"><FileCode2 size={15}/>{result.patch.target_file}</div><p className="footnote">Model confidence is not verification evidence.</p></> : <p className="muted">{terminal(result) ? 'No validated proposal is available.' : 'Diagnosis will appear after a baseline failure is captured.'}</p>}</div></section><section className="panel evidence"><TestSummary title="BASELINE" run={result.baseline}/><TestSummary title="CANDIDATE · FULL SUITE" run={result.candidate}/></section></div>
    {result.diff && <section className="panel diff-panel"><div className="panel-heading"><h2 className="flex items-center gap-2"><GitBranch size={17}/> Proposed change</h2><span className="mono muted">{result.patch?.target_file}</span></div><pre className="diff" aria-label="Unified code diff">{result.diff.split('\n').map((line,i) => <div key={i} className={line.startsWith('+') && !line.startsWith('+++') ? 'added' : line.startsWith('-') && !line.startsWith('---') ? 'removed' : line.startsWith('@@') ? 'hunk' : ''}><span className="line-number">{i+1}</span><code>{line || ' '}</code></div>)}</pre><div className="review-bar"><div><ShieldCheck size={17}/><span>{result.approved ? 'Approved. Your verified candidate is ready to download.' : result.rejected ? 'Patch rejected. Download access is disabled.' : 'Your original project stays unchanged. Review before approving.'}</span></div><div className="flex flex-wrap gap-2">{terminal(result) && <button className="button secondary" disabled={busy || result.rejected} onClick={() => void act('reject')}><X size={15}/>Reject</button>}{result.approved ? <button className="button primary" disabled={busy} onClick={() => void act('download')}><ArrowDownToLine size={16}/>Download ZIP</button> : <button className="button primary" disabled={busy || result.status !== 'VERIFIED'} onClick={() => void act('approve')}><Check size={16}/>Approve patch</button>}</div></div></section>}
    <section className="panel logs-panel"><details><summary><Terminal size={17}/> Test evidence & technical logs <span className="muted">Expand to inspect</span></summary><div className="panel-body">{result.target_test && <p className="mono">Target: {result.target_test}</p>}{[['Baseline',result.baseline],['Targeted verification',result.targeted],['Full verification',result.candidate]].map(([title,run]) => {const r=run as TestRun|null; return r && <div key={title as string} className="log-block"><h3>{title as string}</h3><ul>{Object.entries(r.tests).map(([name,status]) => <li key={name}><span className={status === 'passed' ? 'green' : status === 'failed' ? 'red' : 'muted'}>{status}</span><code>{name}</code></li>)}</ul>{r.errors.map((e,i) => <p className="red" key={i}>{e}</p>)}<pre>{r.logs || 'No text log captured.'}</pre></div>;})}</div></details></section>
  </>}
  <footer><span><Braces size={14}/> DevPilot AI</span><span>Local execution. Observable results. Developer control.</span><span>Python + pytest</span></footer></main></div></div>;
}
