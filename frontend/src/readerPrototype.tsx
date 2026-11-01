// THROWAWAY PROTOTYPE: three chapter-reader variants on the existing Reader view, selected by ?readerPrototype=A|B|C.
import { useEffect, useState } from 'react'
import './readerPrototype.css'

export type ReaderPrototypeVariant = 'A' | 'B' | 'C'

const variantNames: Record<ReaderPrototypeVariant, string> = {
  A: 'Continuous margin reader',
  B: 'Interwoven editorial sheet',
  C: 'Facsimile + reading lens',
}

const variantOrder: ReaderPrototypeVariant[] = ['A', 'B', 'C']

export function getReaderPrototypeVariant(): ReaderPrototypeVariant | null {
  if (!(import.meta as unknown as { env: { DEV: boolean } }).env.DEV) return null
  const candidate = new URLSearchParams(window.location.search).get('readerPrototype')?.toUpperCase()
  return candidate === 'A' || candidate === 'B' || candidate === 'C' ? candidate : null
}

export function ReaderPrototype({ initialVariant }: { initialVariant: ReaderPrototypeVariant }) {
  const [variant, setVariant] = useState<ReaderPrototypeVariant>(initialVariant)
  const [understood, setUnderstood] = useState(false)

  function selectVariant(next: ReaderPrototypeVariant) {
    setVariant(next)
    const url = new URL(window.location.href)
    url.searchParams.set('readerPrototype', next)
    window.history.replaceState({}, '', url)
  }

  function cycle(direction: -1 | 1) {
    const index = variantOrder.indexOf(variant)
    selectVariant(variantOrder[(index + direction + variantOrder.length) % variantOrder.length])
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.matches('input, textarea, [contenteditable="true"]')) return
      if (event.key === 'ArrowLeft') { event.preventDefault(); cycle(-1) }
      if (event.key === 'ArrowRight') { event.preventDefault(); cycle(1) }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [variant])

  return <section className={`reader-prototype reader-prototype-${variant.toLowerCase()}`}>
    <div className="rp-prototype-notice"><b>Throwaway reader prototype</b><span>Complete fixture only · nothing here saves, queues work, or calls a model</span></div>
    {variant === 'A' && <VariantA understood={understood} setUnderstood={setUnderstood}/>} 
    {variant === 'B' && <VariantB understood={understood} setUnderstood={setUnderstood}/>} 
    {variant === 'C' && <VariantC understood={understood} setUnderstood={setUnderstood}/>} 
    <PrototypeSwitcher variant={variant} onCycle={cycle}/>
  </section>
}

function PrototypeSwitcher({ variant, onCycle }: { variant: ReaderPrototypeVariant; onCycle: (direction: -1 | 1) => void }) {
  return <nav className="rp-switcher" aria-label="Reader prototype variants">
    <button onClick={() => onCycle(-1)} aria-label="Previous reader variant">←</button>
    <div><small>READER PROTOTYPE</small><b>{variant} · {variantNames[variant]}</b></div>
    <button onClick={() => onCycle(1)} aria-label="Next reader variant">→</button>
  </nav>
}

type UnderstandingProps = { understood: boolean; setUnderstood: (next: boolean) => void; compact?: boolean }

function UnderstandingCheck({ understood, setUnderstood, compact = false }: UnderstandingProps) {
  return <label className={`rp-understanding ${understood ? 'is-checked' : ''} ${compact ? 'compact' : ''}`}>
    <input type="checkbox" checked={understood} onChange={event => setUnderstood(event.target.checked)}/>
    <span className="rp-checkbox">{understood ? '✓' : ''}</span>
    <span><b>{understood ? 'Understood' : 'Mark this group understood'}</b><small>{understood ? 'Checked 1 Nov 2026 · local prototype state' : 'Only your action can create this blue state'}</small></span>
  </label>
}

function EquationBridge({ mode = 'full' }: { mode?: 'full' | 'compact' }) {
  return <section className={`rp-equation-bridge ${mode}`} aria-label="Expanded integration by parts manipulation">
    <div className="rp-annotation-kicker">LINE-BY-LINE BRIDGE · INTEGRATION BY PARTS</div>
    <div className="rp-equation">2∫<sub>α</sub><sup>β</sup> ρy′ <span className="rp-term-vary">η′</span> dx</div>
    <div className="rp-equation-arrow"><i>↓</i><span>move the derivative off <em className="rp-term-vary">η</em></span></div>
    <div className="rp-equation"><span className="rp-term-boundary">+ 2[ρy′η]<sub>α</sub><sup>β</sup></span> − 2∫<sub>α</sub><sup>β</sup> <span className="rp-term-operator">(ρy′)′</span> <span className="rp-term-vary">η</span> dx</div>
    <div className="rp-equation-arrow"><i>↓</i><span>fixed endpoints: <em className="rp-term-vary">η(α)=η(β)=0</em></span></div>
    <div className="rp-equation">− 2∫<sub>α</sub><sup>β</sup> <span className="rp-term-operator">(ρy′)′</span> <span className="rp-term-vary">η</span> dx</div>
    <footer><span className="rp-key vary">variation</span><span className="rp-key operator">operator term</span><span className="rp-key boundary">boundary term</span></footer>
  </section>
}

function IssueCorrection({ compact = false }: { compact?: boolean }) {
  return <div className={`rp-issue-correction ${compact ? 'compact' : ''}`}>
    <section className="rp-issue"><div className="rp-annotation-kicker">SOURCE ISSUE · CHECKED AGAINST THE DERIVATION</div><b>The printed endpoint term carries a minus sign.</b><p>The page writes −2[ηρy′]<sub>α</sub><sup>β</sup>. That sign does not follow from integration by parts.</p></section>
    <section className="rp-correction"><div className="rp-annotation-kicker">PROPOSED CORRECTION</div><b>Use +2[ρy′η]<sub>α</sub><sup>β</sup>.</b><p>The downstream eigenvalue equation is unchanged because η vanishes at both fixed endpoints.</p></section>
  </div>
}

function Exercise({ inline = false }: { inline?: boolean }) {
  return <section className={`rp-exercise ${inline ? 'inline' : ''}`}>
    <div className="rp-exercise-mark">EX</div><div><div className="rp-annotation-kicker">READER EXERCISE · NOT ATTEMPTED</div><b>Verify that rescaling y ↦ cy leaves the quotient F[y]/G[y] unchanged.</b><p>Prototype source-exercise slot. Assistance remains hidden until deliberately requested.</p></div><button type="button">Open problem ↗</button>
  </section>
}

function ChapterMasthead({ label }: { label: string }) {
  return <header className="rp-masthead">
    <div><div className="rp-annotation-kicker">B6La · COMPLETE CHAPTER EDITION · PHYSICAL PAGES 29–34</div><h1>7. Variational principles</h1><p>Source-faithful text with the missing mathematics attached exactly where it is used.</p></div>
    <div className="rp-masthead-meta"><span>{label}</span><b>7 annotations</b><b>1 source issue</b><b>1 exercise</b></div>
  </header>
}

function VariantA({ understood, setUnderstood }: UnderstandingProps) {
  return <>
    <ChapterMasthead label="CONTINUOUS DOCUMENT"/>
    <div className="rp-a-layout">
      <nav className="rp-a-outline" aria-label="Prototype chapter outline">
        <span>CHAPTER 7</span>
        <a className="active" href="#rp-a-sl">7.1 Sturm–Liouville problem <i>5</i></a>
        <a href="#rp-a-variation">First variations <i>2</i></a>
        <a href="#rp-a-lowest">Lowest eigenvalue <i>2</i></a>
        <a href="#rp-a-quotient">Vary the quotient <i>1</i></a>
        <div className="rp-layer-key"><b>VISIBLE LAYERS</b><span className="rust">Explanation</span><span className="green">Issue</span><span className="purple">Exercise</span><span className="blue">Your checks</span></div>
      </nav>
      <article className="rp-a-document">
        <div className="rp-page-rule"><span>PRINTED PAGE 29</span><span>§7.1</span></div>
        <section id="rp-a-sl" className="rp-a-source-row">
          <div className="rp-source-copy"><h2>7.1 Sturm–Liouville problem</h2><p>Let ρ(x), σ(x) and w(x) be real functions on α ≤ x ≤ β, with ρ and w positive in the open interval. Consider the real functionals</p><div className="rp-display">F[y] = ∫<sub>α</sub><sup>β</sup> {'{'}ρ(x)(y′)² + σ(x)y²{'}'} dx</div><div className="rp-display">G[y] = ∫<sub>α</sub><sup>β</sup> w(x)y² dx.</div></div>
          <aside className="rp-margin rust"><b>What this sets up</b><p>F behaves like a weighted energy; G fixes the otherwise irrelevant scale of y. The problem is to minimise F subject to G=1.</p></aside>
        </section>
        <section id="rp-a-variation" className="rp-a-source-row">
          <div className="rp-source-copy"><p>Let us consider separately the variations of F and G with respect to a variation of y(x):</p><div className="rp-display rp-source-highlight">δF = 2∫<sub>α</sub><sup>β</sup> η{'{'}−(ρy′)′ + σy{'}'} dx − 2[ηρy′]<sub>α</sub><sup>β</sup></div><div className="rp-display">δG = 2∫<sub>α</sub><sup>β</sup> ηwy dx.</div></div>
          <aside className="rp-margin rust"><b>η is the variation δy</b><p>Differentiate F[y+εη] at ε=0. The derivative term initially produces 2∫ρy′η′ dx; the source has already integrated it by parts.</p><span className="rp-connector">↙</span></aside>
        </section>
        <div className="rp-a-bridge"><EquationBridge/></div>
        <div className="rp-a-wide"><IssueCorrection/></div>
        <section className="rp-a-source-row">
          <div className="rp-source-copy"><p>The boundary term in δF is zero because of the fixed-end boundary conditions, so</p><div className="rp-display">δF/δy = 2ℒy,&nbsp;&nbsp;&nbsp; δG/δy = 2wy,</div><p>where ℒ = −d/dx(ρ(x)d/dx) + σ(x). The Euler–Lagrange equation is therefore</p><div className="rp-display rp-focus-equation">ℒy = λwy. <span>(7.3)</span></div><p>This is an eigenvalue problem, with eigenvalue λ. The function w(x) is called a “weight function”.</p></div>
          <aside className="rp-margin rust"><b>Why an eigenproblem appears</b><p>The constrained stationarity condition δF − λδG = 0 says the two functional gradients must be proportional. That proportionality constant is λ.</p></aside>
        </section>
        <section id="rp-a-lowest" className="rp-a-source-row">
          <div className="rp-source-copy"><h3>The lowest eigenvalue</h3><p>Multiply (7.3) by y and integrate to get</p><div className="rp-display">λG = ∫<sub>α</sub><sup>β</sup> yℒy dx = F − [ρyy′]<sub>α</sub><sup>β</sup>.</div><p>The boundary term is zero, so λ=F/G≥0. The original problem is equivalent to minimising F/G because the scale fixed by the normalization constraint drops out of this ratio.</p></div>
          <aside className="rp-margin green"><b>Boundary condition, not merely “fixed”</b><p>Fixed non-zero endpoint values do not force [ρyy′] to vanish. The Rayleigh-quotient argument needs the homogeneous admissible boundary conditions used by this eigenproblem.</p></aside>
        </section>
        <section id="rp-a-quotient" className="rp-a-source-row">
          <div className="rp-source-copy"><h3>Vary the quotient directly</h3><p>We can solve the problem directly by minimising Λ=F/G without constraint. The functional Λ[y] is stationary when</p><div className="rp-display">0 = δΛ/δy = (2/G)[ℒy − Λwy],</div><p>so the values of Λ at its stationary points are the Sturm–Liouville eigenvalues, and the minimum value of Λ is the lowest eigenvalue.</p></div>
          <aside className="rp-margin rust"><b>Ordinary quotient rule, functional inputs</b><p>δ(F/G)=(GδF−FδG)/G². Substitute δF/δy=2ℒy and δG/δy=2wy, then use Λ=F/G.</p></aside>
        </section>
        <div className="rp-a-wide"><Exercise inline/></div>
        <div className="rp-a-wide"><UnderstandingCheck understood={understood} setUnderstood={setUnderstood}/></div>
        <footer className="rp-document-footer"><span>B6La · chapter fixture</span><span>Source order retained · agent additions visibly layered</span></footer>
      </article>
    </div>
  </>
}

function VariantB({ understood, setUnderstood }: UnderstandingProps) {
  return <>
    <ChapterMasthead label="EDITORIAL INTERWEAVE"/>
    <nav className="rp-b-tabs"><button className="active">7.1 Setup</button><button>First variation</button><button>Eigenproblem</button><button>Rayleigh quotient</button><span>Annotations always sit in the reading stream</span></nav>
    <article className="rp-b-sheet">
      <header><span>ORIGINAL SOURCE · PRINTED PAGE 29</span><h2>7.1 Sturm–Liouville problem</h2></header>
      <div className="rp-b-source"><p>Let ρ(x), σ(x) and w(x) be real functions of x, defined for α≤x≤β, such that both ρ and w are positive for α&lt;x&lt;β. Consider</p><div className="rp-b-formula-pair"><span>F[y] = ∫ {'{'}ρ(y′)²+σy²{'}'} dx</span><span>G[y] = ∫ wy² dx.</span></div></div>
      <aside className="rp-b-insert intuition"><span>INTUITION</span><b>Energy divided by weighted amplitude</b><p>F penalises variation and amplitude; G removes arbitrary scale. Their quotient can therefore identify a shape rather than a chosen normalisation.</p></aside>
      <div className="rp-b-source"><p>Let us consider separately the variations of F and G with respect to a variation of y(x):</p><div className="rp-display">δF = 2∫η{'{'}−(ρy′)′+σy{'}'}dx − 2[ηρy′]<sub>α</sub><sup>β</sup></div><div className="rp-display">δG = 2∫ηwy dx.</div></div>
      <div className="rp-b-insert bridge"><EquationBridge mode="compact"/></div>
      <div className="rp-b-insert issue"><IssueCorrection compact/></div>
      <div className="rp-b-source callout-source"><p>The boundary term in δF is zero because of the fixed-end boundary conditions, so</p><div className="rp-display">δF/δy=2ℒy,&nbsp;&nbsp; δG/δy=2wy,</div><p>where ℒ=−d/dx(ρd/dx)+σ. The Euler–Lagrange equation is therefore</p><div className="rp-display rp-focus-equation">ℒy=λwy.</div></div>
      <aside className="rp-b-insert reason"><span>WHY THIS FOLLOWS</span><div><b>Constrained stationarity</b><p>δF/δy−λδG/δy=0</p></div><i>→</i><div><b>Substitute the two gradients</b><p>2ℒy−2λwy=0</p></div><i>→</i><div><b>Divide by 2</b><p>ℒy=λwy</p></div></aside>
      <div className="rp-b-source"><h3>The lowest eigenvalue as a quotient</h3><p>Multiply by y and integrate:</p><div className="rp-display">λG = ∫yℒy dx = F−[ρyy′]<sub>α</sub><sup>β</sup>.</div><p>With the admissible homogeneous boundary condition, λ=F/G. Rescaling y changes F and G by the same factor, so the quotient does not change.</p></div>
      <aside className="rp-b-insert rust-line"><span>ONE-LINE CHECK</span><p>y↦cy gives F[cy]=c²F[y] and G[cy]=c²G[y]; hence F[cy]/G[cy]=F[y]/G[y].</p></aside>
      <div className="rp-b-source"><h3>Direct quotient variation</h3><div className="rp-display">δΛ/δy = (1/G)[δF/δy−(F/G)δG/δy] = (2/G)[ℒy−Λwy].</div><p>The stationary quotient values are the eigenvalues; its minimum selects the lowest one.</p></div>
      <Exercise/>
      <UnderstandingCheck understood={understood} setUnderstood={setUnderstood}/>
      <footer><span>End of prepared chapter fixture</span><span>7 source anchors · 7 annotations · 1 open issue</span></footer>
    </article>
  </>
}

type Focus = 'variation' | 'issue' | 'eigenproblem' | 'quotient' | 'exercise'

function VariantC({ understood, setUnderstood }: UnderstandingProps) {
  const [focus, setFocus] = useState<Focus>('variation')
  return <>
    <ChapterMasthead label="FACSIMILE + REFLOW"/>
    <div className="rp-c-toolbar"><span><b>Source page 29</b> / chapter pages 28–34</span><div><button>−</button><b>100%</b><button>＋</button></div><span>Click a coloured source anchor to focus its explanation</span></div>
    <div className="rp-c-layout">
      <section className="rp-c-facsimile" aria-label="Source facsimile prototype">
        <div className="rp-c-page-number">− 29 −</div>
        <h2>7.1 Sturm–Liouville problem</h2>
        <p>Let ρ(x), σ(x) and w(x) be real functions of x, defined for α≤x≤β, such that both ρ and w are positive in the open interval, and consider the real functionals</p>
        <div className="rp-c-print-formula">F[y]=∫<sub>α</sub><sup>β</sup>{'{'}ρ(x)(y′)²+σ(x)y²{'}'}dx,&nbsp;&nbsp; G[y]=∫<sub>α</sub><sup>β</sup>w(x)y²dx.</div>
        <p>The problem is to find the function that minimises F[y] subject to G[y]=1. Let us consider separately the variations of F and G:</p>
        <button className={`rp-c-anchor rust ${focus==='variation'?'active':''}`} onClick={() => setFocus('variation')}><span>1</span><div className="rp-c-print-formula">δF=2∫η{'{'}−(ρy′)′+σy{'}'}dx−2[ηρy′]<sub>α</sub><sup>β</sup></div></button>
        <button className={`rp-c-anchor green ${focus==='issue'?'active':''}`} onClick={() => setFocus('issue')}><span>2</span><p>The boundary term in δF is zero because of the fixed-end boundary conditions.</p></button>
        <button className={`rp-c-anchor rust ${focus==='eigenproblem'?'active':''}`} onClick={() => setFocus('eigenproblem')}><span>3</span><div className="rp-c-print-formula">ℒy=λwy. <i>(7.3)</i></div></button>
        <p>This is an eigenvalue problem, with eigenvalue λ. The function w(x) is called a “weight function”.</p>
        <button className={`rp-c-anchor rust ${focus==='quotient'?'active':''}`} onClick={() => setFocus('quotient')}><span>4</span><p>Multiply both sides of (7.3) by y and integrate to get λG=∫yℒy dx=F−[ρyy′].</p></button>
        <p>Notice that F/G is still a functional. We can solve the problem directly by minimising Λ=F/G without constraint.</p>
        <button className={`rp-c-anchor purple ${focus==='exercise'?'active':''}`} onClick={() => setFocus('exercise')}><span>EX</span><p>Verify that the quotient is unchanged by an overall rescaling of y.</p></button>
      </section>
      <aside className="rp-c-lens">
        <header><div><span>READING LENS</span><b>Anchor {focus === 'exercise' ? 'EX' : ({variation:1,issue:2,eigenproblem:3,quotient:4} as Record<Exclude<Focus,'exercise'>,number>)[focus as Exclude<Focus,'exercise'>]}</b></div><small>Agent additions are reflowed; source remains untouched on the left.</small></header>
        <section className={`rp-c-note ${focus==='variation'?'active':''}`} onClick={() => setFocus('variation')}><span>1 · MISSING MANIPULATION</span><h3>Where the differential operator comes from</h3><EquationBridge mode="compact"/></section>
        <section className={`rp-c-note ${focus==='issue'?'active':''}`} onClick={() => setFocus('issue')}><span>2 · SOURCE ISSUE + CORRECTION</span><IssueCorrection compact/></section>
        <section className={`rp-c-note ${focus==='eigenproblem'?'active':''}`} onClick={() => setFocus('eigenproblem')}><span>3 · CONCEPTUAL BRIDGE</span><h3>Constraint gradient → eigenvalue equation</h3><p>At a constrained stationary point, the gradient of F is parallel to the gradient of G. Substitution gives 2ℒy=2λwy, hence ℒy=λwy.</p><div className="rp-c-mini-flow"><b>δF</b><i>∥</i><b>δG</b><i>→</i><strong>eigenpair (λ,y)</strong></div></section>
        <section className={`rp-c-note ${focus==='quotient'?'active':''}`} onClick={() => setFocus('quotient')}><span>4 · INTUITION + ASSUMPTION</span><h3>The Rayleigh quotient removes scale</h3><p>F and G both grow like c² under y↦cy. Their ratio depends only on the shape of y. The boundary contribution vanishes only for the admissible homogeneous conditions, not for arbitrary fixed non-zero endpoints.</p></section>
        <section className={`rp-c-note exercise ${focus==='exercise'?'active':''}`} onClick={() => setFocus('exercise')}><span>EX · SOURCE EXERCISE</span><Exercise inline/></section>
        <UnderstandingCheck compact understood={understood} setUnderstood={setUnderstood}/>
      </aside>
    </div>
  </>
}
