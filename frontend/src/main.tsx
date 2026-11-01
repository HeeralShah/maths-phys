import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import './styles.css'

type Unit = { id: string; title: string; ordinal: number; metadata: Record<string, unknown> }
type Section = { id: string; title: string; ordinal: number; metadata: Record<string, unknown>; units: Unit[] }
type Source = { id: string; title: string; metadata: Record<string, unknown>; created_at: string; sections: Section[] }
type Edition = { id: string; unit_id: string; revision: number; content: string; created_at: string } | null
type Check = { id: string; revision_id: string; check_type: string; passed: boolean; detail: string; created_at: string }
type Job = { id: string; job_type: string; entity_id: string; status: string; payload: string; result?: string | null; error?: string | null; created_at: string; updated_at: string }
type View = 'library' | 'reader' | 'graph' | 'problems'
type Evidence = { id: string; source_id: string; locator: string; quote: string; source_ref?: string | null; metadata?: Record<string, unknown> }
type GraphNode = { id: string; source_id: string; node_type: string; label: string; claim: string; metadata: Record<string, unknown>; evidence: Evidence[] }
type GraphEdge = { id: string; from_id: string; to_id: string; relation: string; claim: string; metadata: Record<string, unknown>; evidence: Evidence[] }
type Problem = { id: string; source_id: string; prompt: string; placement: string; placement_ref?: string; subject: string; prerequisites: { problem_id?: string; label?: string }[]; novelty: string; combination: string; workload: string; provenance: Record<string, unknown>; experience: string; difficulty?: { assessment: string; reason: string } | null }
const hintLevels = ['orientation', 'small_hint', 'strong_hint', 'partial_solution', 'full_solution'] as const
type HintLevel = typeof hintLevels[number]

const defaultApi = '/api'
const stamp = () => `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

function App() {
  const [api, setApi] = useState(() => localStorage.getItem('mathsphys-api') || defaultApi)
  const [view, setView] = useState<View>('library')
  const [source, setSource] = useState<Source | null>(null)
  const [sourceId, setSourceId] = useState('')
  const [selectedUnit, setSelectedUnit] = useState<Unit | null>(null)
  const [edition, setEdition] = useState<Edition>(null)
  const [checks, setChecks] = useState<Check[]>([])
  const [content, setContent] = useState('')
  const [actor, setActor] = useState('')
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(false)
  const [apiConnected, setApiConnected] = useState<boolean | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [sourceTitle, setSourceTitle] = useState('')
  const [outline, setOutline] = useState('[{"title":"Chapter 1","units":[{"title":"First concept"}]}]')
  const [sources, setSources] = useState<Pick<Source, 'id'|'title'|'metadata'|'created_at'>[]>([])
  const [graphSource, setGraphSource] = useState('')
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([])
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null)
  const [problemSource, setProblemSource] = useState('')
  const [problemQuery, setProblemQuery] = useState('')
  const [problems, setProblems] = useState<Problem[]>([])
  const [revealed, setRevealed] = useState<Record<string, Partial<Record<HintLevel, string>>>>({})
  const [clarification, setClarification] = useState('')
  const unitLoadSequence = useRef(0)

  const request = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const response = await fetch(`${api.replace(/\/$/, '')}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`
      try { detail = (await response.json()).detail || detail } catch { /* keep status */ }
      throw new Error(detail)
    }
    return response.json() as Promise<T>
  }, [api])

  const refreshJobs = useCallback(async () => {
    try { setJobs(await request<Job[]>('/jobs')); setApiConnected(true) } catch { setApiConnected(false) }
  }, [request])

  useEffect(() => { localStorage.setItem('mathsphys-api', api) }, [api])
  useEffect(() => { void refreshJobs(); const timer = window.setInterval(() => void refreshJobs(), 5000); return () => window.clearInterval(timer) }, [refreshJobs])
  useEffect(() => { void request<typeof sources>('/sources').then(items => { setSources(items); if (items.length) { setGraphSource(v => v || items[0].id); setProblemSource(v => v || items[0].id) } }).catch(() => setSources([])) }, [request])
  useEffect(() => { if (view !== 'graph') return; setSelectedNode(null); setSelectedEdge(null); void request<{nodes: GraphNode[]; edges: GraphEdge[]}>(`/research/graph${graphSource ? `?source_id=${encodeURIComponent(graphSource)}` : ''}`).then(data => { setGraphNodes(data.nodes); setGraphEdges(data.edges) }).catch(e => { setGraphNodes([]); setGraphEdges([]); setError(e instanceof Error ? e.message : 'Unable to load graph') }) }, [view, graphSource, request])
  useEffect(() => { if (view !== 'problems') return; const params = new URLSearchParams(); if (problemSource) params.set('source_id', problemSource); if (problemQuery.trim()) params.set('q', problemQuery.trim()); void request<Problem[]>(`/problems?${params}`).then(setProblems).catch(e => { setProblems([]); setError(e instanceof Error ? e.message : 'Unable to load problems') }) }, [view, problemSource, problemQuery, request])

  const activeSection = useMemo(() => source?.sections.find(s => s.units.some(u => u.id === selectedUnit?.id)) ?? null, [source, selectedUnit])
  const understandingChecks = checks.filter(c => c.check_type === 'understood')
  const understood = understandingChecks.length ? understandingChecks[understandingChecks.length - 1].passed : null
  const latestJob = jobs[jobs.length - 1]

  async function perform(action: () => Promise<void>) {
    setError(''); setMessage(''); setLoading(true)
    try { await action() } catch (e) { setError(e instanceof Error ? e.message : 'Request failed') } finally { setLoading(false) }
  }

  async function openSource(id: string) {
    await perform(async () => {
      const loaded = await request<Source>(`/sources/${encodeURIComponent(id.trim())}`)
      setSource(loaded); setSourceId(loaded.id); setSelectedUnit(null); setEdition(null); setChecks([]); setContent('')
      setView('reader'); setMessage('Source outline loaded. Source registration stores metadata and an outline; it does not ingest or extract PDF content.')
    })
  }

  async function registerSource() {
    await perform(async () => {
      const sections = JSON.parse(outline)
      const created = await request<Source>('/sources', { method: 'POST', body: JSON.stringify({ title: sourceTitle, metadata: { source_type: 'manual', note: 'Metadata and outline only; source content not ingested.' }, sections }) })
      setSource(created); setSourceId(created.id); setView('reader'); setMessage('Source metadata and outline registered. No source content was ingested.')
    })
  }

  async function selectUnit(unit: Unit) {
    const sequence = ++unitLoadSequence.current
    setSelectedUnit(unit); setEdition(null); setChecks([]); setContent(''); setError('')
    try {
      const data = await request<Edition>(`/units/${unit.id}/edition`)
      if (sequence !== unitLoadSequence.current) return
      setEdition(data); setContent(data?.content || '')
      if (data) { const loadedChecks = await request<Check[]>(`/revisions/${data.id}/checks`); if (sequence === unitLoadSequence.current) setChecks(loadedChecks) }
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load saved edition') }
  }

  async function saveEdition(): Promise<NonNullable<Edition>> {
    if (!selectedUnit) throw new Error('Choose a unit first')
    const saved = await request<NonNullable<Edition>>(`/units/${selectedUnit.id}/revisions`, { method: 'PUT', body: JSON.stringify({ content }) })
    setEdition(saved); setChecks(await request<Check[]>(`/revisions/${saved.id}/checks`)); setMessage(`Saved edition ${saved.revision}.`)
    return saved
  }

  async function recordUnderstanding(passed: boolean) {
    await perform(async () => {
      if (!selectedUnit) throw new Error('Choose a unit first')
      const current = !edition || content !== edition.content ? await saveEdition() : edition
      const check = await request<Check>(`/revisions/${current.id}/checks`, { method: 'POST', body: JSON.stringify({ check_type: 'understood', passed, detail: passed ? 'Learner marked this saved edition understood.' : 'Learner marked this saved edition for another review.' }) })
      setChecks([...checks, check]); setMessage(passed ? 'Understanding recorded for this saved edition.' : 'Review status recorded for this saved edition.')
    })
  }

  async function queueJob(jobType: 'prepare' | 'revise') {
    await perform(async () => {
      if (!source) throw new Error('Load a source first')
      let entityId = source.id
      let payload: Record<string, unknown> = { source_id: source.id }
      if (jobType === 'revise') {
        if (!selectedUnit) throw new Error('Choose a unit to revise')
        const saved = edition && content === edition.content ? edition : await saveEdition()
        entityId = selectedUnit.id; payload = { source_id: source.id, unit_id: selectedUnit.id, revision_id: saved.id, clarification: clarification.trim() }
      }
      const job = await request<Job>('/jobs', { method: 'POST', body: JSON.stringify({ job_type: jobType, entity_id: entityId, idempotency_key: stamp(), payload }) })
      setMessage(`${jobType === 'prepare' ? 'Prepare' : 'Revise'} job queued (${job.status}). This UI does not call a model.`); await refreshJobs()
    })
  }

  async function signoffSection(section: Section) {
    await perform(async () => {
      if (!actor.trim()) throw new Error('Enter your name or initials for the section sign-off')
      const job = await request<Job>(`/sections/${section.id}/signoffs`, { method: 'POST', body: JSON.stringify({ actor, scope: '', idempotency_key: stamp() }) })
      setMessage(`Section sign-off recorded; follow-up job ${job.status}. The backend includes only each unit’s latest edition marked understood.`); await refreshJobs()
    })
  }

  const nav = (key: View, label: string, icon: string) => <button className={`nav-item ${view === key ? 'active' : ''}`} onClick={() => setView(key)}><span className="nav-icon">{icon}</span>{label}</button>

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">f.</span><div><b>fieldnotes</b><small>MATHS & PHYSICS</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      {nav('library', 'Library', '▤')}{nav('reader', 'Reader', '◫')}{nav('graph', 'Research graph', '⌘')}{nav('problems', 'Source problems', '∴')}
      <div className="sidebar-bottom"><div className="connection-dot"/><div><b>Local workspace</b><small>No model calls without action</small></div></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="crumb">Workspace <span>/</span> {view === 'graph' ? 'Research graph' : view === 'problems' ? 'Source problems' : view === 'reader' ? 'Reader' : 'Library'}</div><span className={`api-state ${apiConnected === true ? 'online' : apiConnected === false ? 'offline' : ''}`}><i/>{apiConnected === true ? 'Connected' : apiConnected === false ? 'API offline' : 'Connecting'}</span><label className="api-field"><span>API</span><input aria-label="Backend API address" value={api} onChange={e => setApi(e.target.value)} /></label><button className="avatar" title="Local session">L</button></header>
      <div className="content">
        {error && <div className="toast error">{error}<button onClick={() => setError('')}>×</button></div>}
        {message && <div className="toast success">{message}<button onClick={() => setMessage('')}>×</button></div>}
        {view === 'library' && <>
          <div className="page-heading"><div><div className="eyebrow">YOUR STUDY DESK <span className="live-dot"/></div><h1>Good work starts<br/>with a clear source.</h1><p className="subhead">Keep source context close, build a saved study edition, and sign off when you understand it.</p></div><div className="heading-note"><span>✳</span><p>Thoughtful study,<br/>one unit at a time.</p></div></div>
          <div className="section-title"><div><h2>Open a source</h2><p>Load an outline already registered in the local study service.</p></div><span className="eyebrow muted">LIBRARY · 01</span></div>
          <div className="open-source card"><div className="source-glyph">⌕</div><div className="grow"><label className="field-label" htmlFor="source-id">SOURCE ID</label><input id="source-id" value={sourceId} onChange={e => setSourceId(e.target.value)} placeholder="Paste a source ID" onKeyDown={e => e.key === 'Enter' && void openSource(sourceId)} /></div><button className="button dark" onClick={() => void openSource(sourceId)} disabled={loading || !sourceId.trim()}>Open source <span>↗</span></button></div>
          <div className="register-grid">
            <div className="section-title register-title"><div><h2>Register source metadata</h2><p>Create a local source record and outline.</p></div></div>
            <div className="card register-card"><div className="field-row"><div className="grow"><label className="field-label">SOURCE TITLE</label><input value={sourceTitle} onChange={e => setSourceTitle(e.target.value)} placeholder="e.g. Classical Mechanics — lecture notes" /></div><button className="button ochre" onClick={() => void registerSource()} disabled={loading || !sourceTitle.trim()}>Register source</button></div><label className="field-label outline-label">OUTLINE JSON <span>sections with nested units</span></label><textarea className="outline-input" value={outline} onChange={e => setOutline(e.target.value)} spellCheck={false}/><div className="fine-print"><span>ⓘ</span> Registration stores metadata and outline only. It does not read or ingest a PDF.</div></div>
          </div>
          <section className="workflow-strip"><div className="flow-step"><span>01</span><div><b>Choose</b><small>Pick a source and unit</small></div></div><i>→</i><div className="flow-step"><span>02</span><div><b>Study</b><small>Save your own edition</small></div></div><i>→</i><div className="flow-step"><span>03</span><div><b>Sign off</b><small>Record understanding</small></div></div></section>
          <JobShelf job={latestJob} onRefresh={() => void refreshJobs()} />
        </>}

        {view === 'reader' && <>
          <div className="reader-heading"><div><div className="eyebrow">SOURCE READER</div><h1>{source?.title || 'Choose a source'}</h1><p className="subhead">Select a unit to open its latest saved edition.</p></div><button className="button outline" onClick={() => setView('library')}>← Library</button></div>
          {!source ? <div className="empty-card card"><span>⌕</span><h3>No source loaded</h3><p>Open a registered source by ID from your Library.</p><button className="button dark" onClick={() => setView('library')}>Go to Library</button></div> : <div className="reader-layout">
            <aside className="outline-pane"><div className="pane-caption">TABLE OF CONTENTS <span>{source.sections.reduce((n, s) => n + s.units.length, 0)} units</span></div>{source.sections.map((section, i) => <div className="outline-section" key={section.id}><div className="outline-section-title"><span>{String(i + 1).padStart(2, '0')}</span>{section.title}</div>{section.units.map(unit => <button key={unit.id} className={`unit-link ${selectedUnit?.id === unit.id ? 'selected' : ''}`} onClick={() => void selectUnit(unit)}><span className="unit-dot"/>{unit.title}<span className="unit-check">{selectedUnit?.id === unit.id && understood === true ? '✓' : ''}</span></button>)}</div>)}{source.sections.length === 0 && <div className="empty-outline">This source has no sections yet.</div>}
              <div className="source-meta"><span>SOURCE RECORD</span><code>{source.id.slice(0, 8)}…</code><small>{new Date(source.created_at).toLocaleDateString()}</small></div>
            </aside>
            <section className="edition-pane">{!selectedUnit ? <div className="empty-edition"><div className="empty-icon">✳</div><h2>A quieter place to think.</h2><p>Choose a unit in the outline. Your writing is saved as an immutable edition so you can return to what you knew at each point.</p></div> : <>
              <div className="edition-topline"><span>{activeSection?.title || 'UNIT'}</span><span>·</span><span>{edition ? `EDITION ${edition.revision}` : 'NO SAVED EDITION'}</span><span className="draft-pill">{edition ? 'Saved edition' : 'New draft'}</span></div>
              <h2 className="unit-title">{selectedUnit.title}</h2>
              <div className="editor-card"><div className="editor-toolbar"><span>YOUR STUDY EDITION</span><span>Markdown and math preview</span></div><textarea className="edition-editor" value={content} onChange={e => setContent(e.target.value)} placeholder={'Write an explanation in your own words…\n\nUse equations, examples, and source references as needed.'}/><div className="edition-preview"><div className="preview-label">PREVIEW</div><ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{content || '_Your rendered edition will appear here._'}</ReactMarkdown></div><div className="editor-foot"><span>{edition ? `Last saved ${new Date(edition.created_at).toLocaleString()}` : 'Not saved yet'}</span><button className="button dark small" disabled={loading} onClick={() => void perform(async () => { await saveEdition() })}>Save edition <span>↗</span></button></div></div>
              <div className="review-card"><div className="review-copy"><span className={`status-icon ${understood === true ? 'good' : understood === false ? 'revisit' : ''}`}>{understood === true ? '✓' : understood === false ? '↻' : '○'}</span><div><b>{understood === true ? 'You marked this understood' : understood === false ? 'Marked for another pass' : 'Ready for a self-check?'}</b><small>Check records against the current text, saving a new edition first if you changed it.</small></div></div><div className="review-actions"><button className="button soft" disabled={loading} onClick={() => void recordUnderstanding(false)}>Revisit</button><button className="button green" disabled={loading} onClick={() => void recordUnderstanding(true)}>I understand <span>✓</span></button></div></div>
              <div className="signoff-card"><div><div className="eyebrow">SECTION SIGN-OFF</div><h3>{activeSection?.title || 'Current section'}</h3><p>The service includes only units whose latest saved edition is marked understood.</p></div><div className="signoff-controls"><label><span>YOUR NAME / INITIALS</span><input value={actor} onChange={e => setActor(e.target.value)} placeholder="Enter to sign off" /></label><button className="button ochre" disabled={loading || !activeSection || !actor.trim()} onClick={() => activeSection && void signoffSection(activeSection)}>Sign off section ↗</button></div></div>
              <div className="clarification-card"><label className="field-label" htmlFor="clarification">ASK FOR A CLARIFICATION</label><textarea id="clarification" value={clarification} onChange={e => setClarification(e.target.value)} placeholder="What should the next edition explain differently?"/><button className="button ochre" onClick={() => void queueJob('revise')} disabled={loading || !edition || !clarification.trim()}>Submit clarification and queue revision ↗</button><p>Submitting queues a revision job. When it finishes, use Refresh edition to load the new saved revision.</p></div>
              <div className="edition-actions"><button onClick={() => void queueJob('prepare')} disabled={loading || !source}>Prepare edition <span>↗</span></button><button onClick={() => selectedUnit && void perform(async () => { const next = await request<Edition>(`/units/${selectedUnit.id}/edition`); setEdition(next); setContent(next?.content || ''); if (next) setChecks(await request<Check[]>(`/revisions/${next.id}/checks`)); setMessage('Displayed edition refreshed; current checks are loaded for this revision.') })} disabled={loading || !selectedUnit}>Refresh edition <span>↻</span></button></div>
              <p className="action-note">These buttons enqueue explicit jobs. They do not trigger model calls from this interface.</p>
              <JobShelf job={latestJob} onRefresh={() => void refreshJobs()} />
            </>}</section>
          </div>}
        </>}

        {view === 'graph' && <section className="research-page"><div className="research-heading"><div><div className="eyebrow">SOURCE-LINKED RESEARCH</div><h1>Research graph</h1><p className="subhead">Browse saved claims and evidence. Opening the graph is local and read-only.</p></div><label className="filter-field">SOURCE<select value={graphSource} onChange={e => setGraphSource(e.target.value)}><option value="">All sources</option>{sources.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select></label></div>{graphNodes.length === 0 ? <div className="empty-card card"><h3>No saved graph nodes</h3><p>There is no graph data for this selection yet.</p></div> : <div className="graph-layout"><div className="graph-canvas"><svg viewBox={`0 0 800 ${Math.max(470,Math.ceil(graphNodes.length/4)*180+60)}`} role="img" aria-label="Saved evidence graph">{graphEdges.map(edge => { const a=graphNodes.findIndex(n=>n.id===edge.from_id), b=graphNodes.findIndex(n=>n.id===edge.to_id); if(a<0||b<0)return null; const pos=(i:number)=>({x:100+(i%4)*195,y:90+Math.floor(i/4)*180}); const p=pos(a),q=pos(b); return <g key={edge.id} onClick={()=>{setSelectedNode(null);setSelectedEdge(edge)}} className="edge-hit" role="button" tabIndex={0} onKeyDown={e=>e.key==='Enter'&&setSelectedEdge(edge)}><line x1={p.x} y1={p.y} x2={q.x} y2={q.y} className="edge-hitline"/><line x1={p.x} y1={p.y} x2={q.x} y2={q.y} className="graph-edge"/><text x={(p.x+q.x)/2} y={(p.y+q.y)/2-7} className="edge-label">{edge.relation}</text></g>})}{graphNodes.map((node,i)=>{const x=100+(i%4)*195,y=90+Math.floor(i/4)*180; return <g key={node.id} onClick={()=>{setSelectedNode(node);setSelectedEdge(null)}} className={`graph-node ${selectedNode?.id===node.id?'chosen':''}`} role="button" tabIndex={0} onKeyDown={e=>e.key==='Enter'&&setSelectedNode(node)}><circle cx={x} cy={y} r="42"/><text x={x} y={y-4} textAnchor="middle">{node.label.slice(0,22)}</text><text x={x} y={y+13} textAnchor="middle" className="node-type">{node.node_type}</text></g>})}</svg></div><aside className="evidence-panel"><div className="eyebrow">{selectedEdge?'RELATION EVIDENCE':selectedNode?'CLAIM & EVIDENCE':'SELECT A NODE OR EDGE'}</div>{selectedNode?<><h2>{selectedNode.label}</h2><p>{selectedNode.claim}</p>{selectedNode.evidence.map(ev=><EvidenceCard key={ev.id} evidence={ev}/>)}</>:selectedEdge?<><h2>{selectedEdge.relation}</h2><p>{selectedEdge.claim}</p>{selectedEdge.evidence.map(ev=><EvidenceCard key={ev.id} evidence={ev}/>)}</>:<p>Choose a saved node or relation to inspect its evidence.</p>}</aside></div>}</section>}
        {view === 'problems' && <section className="research-page"><div className="research-heading"><div><div className="eyebrow">SOURCE-ONLY PRACTICE</div><h1>Problem library</h1><p className="subhead">Browse problems linked to sources. Assistance appears only after you choose a level.</p></div><div className="problem-filters"><label className="filter-field">SOURCE<select value={problemSource} onChange={e=>setProblemSource(e.target.value)}><option value="">All sources</option>{sources.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></label><input aria-label="Search problems" placeholder="Filter problem text" value={problemQuery} onChange={e=>setProblemQuery(e.target.value)}/></div></div>{problems.length===0?<div className="empty-card card"><h3>No source problems found</h3><p>Try another source or filter.</p></div>:<div className="problem-list">{problems.map(p=><article className="problem-card" key={p.id}><div className="problem-meta"><span>{p.placement.replace('_',' ')}</span><span>{p.subject}</span><span>Novelty · {p.novelty}</span><span>Workload · {p.workload}</span></div><div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{p.prompt}</ReactMarkdown></div><div className="problem-details"><span>Ideas: {p.combination}</span><span>Experience: {p.experience}</span>{p.difficulty&&<span>Difficulty: {p.difficulty.assessment} — {p.difficulty.reason}</span>}<span>Prerequisites: {p.prerequisites.map(x=>x.label||x.problem_id).join(', ')||'None listed'}</span></div><details className="provenance"><summary>Source provenance</summary><EvidenceCard evidence={{id:p.id,source_id:p.source_id,locator:String(p.provenance.locator||''),quote:String(p.provenance.quote||''),source_ref:String(p.provenance.source_ref||'')}}/></details><div className="hint-controls"><span>REVEAL ONE ASSISTANCE LEVEL</span>{hintLevels.map(level=><button key={level} className="button soft" disabled={loading||!!revealed[p.id]?.[level]} onClick={()=>void perform(async()=>{const result=await request<{problem_id:string;level:HintLevel;content:string}>(`/problems/${p.id}/reveal`,{method:'POST',body:JSON.stringify({level})});setRevealed(old=>({...old,[p.id]:{...old[p.id],[result.level]:result.content}}))})}>{level.replace('_',' ')}</button>)}</div>{hintLevels.filter(level=>revealed[p.id]?.[level]).map(level=><section className="revealed-hint" key={level}><b>{level.replace('_',' ')}</b><div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{revealed[p.id]?.[level]||''}</ReactMarkdown></div></section>)}</article>)}</div>}</section>}
      </div>
    </main>
  </div>
}

function JobShelf({ job, onRefresh }: { job?: Job; onRefresh: () => void }) {
  return <section className="job-shelf"><div className="job-heading"><div><div className="eyebrow">BACKGROUND WORK</div><b>Job status</b></div><button onClick={onRefresh} aria-label="Refresh job status">↻</button></div>{job ? <div className="job-row"><span className={`job-status ${job.status}`}>{job.status}</span><b>{job.job_type}</b><code>{job.id.slice(0, 8)}…</code><small>{new Date(job.updated_at).toLocaleTimeString()}</small></div> : <p>No jobs recorded yet.</p>}<small className="job-footnote">Status refreshes every 5 seconds. Queued jobs remain queued until a worker is separately installed and configured.</small></section>
}

function EvidenceCard({ evidence }: { evidence: Evidence }) {
  return <blockquote className="evidence-card"><p>{evidence.quote || 'No quoted passage saved.'}</p><footer>{evidence.locator || 'Location not recorded'}{evidence.source_ref ? ` · ${evidence.source_ref}` : ''}<code>{evidence.source_id.slice(0,8)}…</code></footer></blockquote>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
