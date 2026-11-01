---
type: proof
tags:
  - proof
  - area/physics
  - status/seed
parent_index: "[[02 Atlas/09 Quantum Field Theory/02 Canonical Quantization/01 Canonical Quantization Index]]"
status: seed
---

# Summary

The equal-time canonical commutation relations are the field-theory version of the canonical algebra $[q^i,p_j]=i\delta^i{}_j$. Their spatial delta function is the continuum kernel of the identity map on field variations. Classical Hamiltonian field theory supplies the corresponding Poisson-bracket kernel; canonical quantization postulates the operator algebra by the usual Poisson-bracket/commutator correspondence. The latter step is a quantization rule, not a deduction from classical mechanics alone.

# Classical bracket kernel

Let $\phi^a(\mathbf{x})$ and $\pi_a(\mathbf{x})$ be canonical data on a fixed time slice. For functionals $F[\phi,\pi]$ and $G[\phi,\pi]$, the canonical field Poisson bracket is

$$
\{F,G\}=\int d^3z\left(
\frac{\delta F}{\delta\phi^a(\mathbf z)}
\frac{\delta G}{\delta\pi_a(\mathbf z)}
-\frac{\delta F}{\delta\pi_a(\mathbf z)}
\frac{\delta G}{\delta\phi^a(\mathbf z)}
\right),
$$

with repeated field-component labels summed. Apply it to the evaluation functionals $F=\phi^a(\mathbf{x})$ and $G=\pi_b(\mathbf{y})$. Their functional derivatives are

$$
\frac{\delta\phi^a(\mathbf x)}{\delta\phi^c(\mathbf z)}
=\delta^a{}_c\delta^{(3)}(\mathbf x-\mathbf z),\qquad
\frac{\delta\pi_b(\mathbf y)}{\delta\pi_c(\mathbf z)}
=\delta_b{}^c\delta^{(3)}(\mathbf y-\mathbf z),
$$

and the cross derivatives vanish. Substitution therefore gives

$$
\{\phi^a(\mathbf x),\pi_b(\mathbf y)\}
=\delta^a{}_b\delta^{(3)}(\mathbf x-\mathbf y),\qquad
\{\phi^a(\mathbf x),\phi^b(\mathbf y)\}=0,\qquad
\{\pi_a(\mathbf x),\pi_b(\mathbf y)\}=0.
$$

The delta distribution is the continuum analogue of the Kronecker delta: when integrated against a test function, it evaluates that function at the matching point. It makes the field-momentum pairing local on the chosen slice.

# Quantization step

Canonical quantization represents the canonical variables by operators and uses the correspondence

$$
\{F,G\}_{\rm PB}\quad\longmapsto\quad \frac{1}{i\hbar}[\hat F,\hat G]
$$

for canonical pairs, with the displayed simple relation understood as the quantization prescription (and $\hbar=1$ below). Thus one imposes

$$
[\hat\phi^a(\mathbf x,t),\hat\pi_b(\mathbf y,t)]
=i\delta^a{}_b\delta^{(3)}(\mathbf x-\mathbf y),
$$

and the equal-time field-field and momentum-momentum commutators vanish. This is the field analogue of imposing $[\hat q^i,\hat p_j]=i\delta^i{}_j$ in ordinary canonical quantization. Tong states this finite-dimensional-to-field replacement and the resulting algebra in §2.1, printed p. 21 (Eq. 2.2; local PDF p. 27).

The classical bracket motivates the form and normalization of the canonical algebra, but does not by itself derive a quantum theory. In general there is no automatic map sending every classical Poisson bracket to an operator commutator while preserving all algebraic relations. The CCRs are input to canonical quantization; further choices are needed to define a representation, Hamiltonian operator, domains, regularization, and (where applicable) constraints.

# Distributional meaning

Point-labelled fields in a continuum theory are formal operator-valued distributions. Interpret the relations by smearing with test functions. For smooth rapidly decreasing functions $f,g$, define

$$
\hat\phi^a(f,t)=\int d^3x\,f(\mathbf x)\hat\phi^a(\mathbf x,t),\qquad
\hat\pi_b(g,t)=\int d^3y\,g(\mathbf y)\hat\pi_b(\mathbf y,t).
$$

Then the mixed relation means

$$
[\hat\phi^a(f,t),\hat\pi_b(g,t)]
=i\delta^a{}_b\int d^3x\,f(\mathbf x)g(\mathbf x),
$$

for real test functions (or with the appropriate complex conjugation according to the smearing convention). This formulation avoids treating $\delta^{(3)}(0)$ or a field at an exact point as an ordinary number or operator. A regulator or finite-volume setup can make intermediate expressions concrete, but the continuum relations are distributional.

# What this calculation does and does not establish

The functional-derivative calculation establishes the classical Poisson-bracket kernel given the canonical field bracket. The passage to commutators is the quantization postulate. The relations are equal-time relations: $t$ is the same on both operators, as appropriate to canonical data on one slice. They do not assert that fields commute at arbitrary spacetime separation. In a relativistic theory, spacelike commutativity is a separate locality property to be checked in the constructed theory.

For a free scalar field, a Fourier-mode expansion with oscillator operators can be checked to reproduce these CCRs; see [[02 Atlas/09 Quantum Field Theory/02 Canonical Quantization/05 Free Scalar Field - example - mode expansion|Free Scalar Field - example - mode expansion]]. That check verifies a realization of the postulated field algebra, rather than deriving quantization from the classical bracket.

# Sources

- Tong, David. *Quantum Field Theory*, §1.4, pp. 19–20 (Hamiltonian field variables) and §2.1, p. 21, Eqs. 2.1–2.3 (canonical quantization, field CCRs, Schrödinger picture). Printed page numbers; local PDF pp. 25–27.
- Local file: [[02 Atlas/09 Quantum Field Theory/99 Sources/01 qft_david_tong.pdf|qft_david_tong.pdf]].
- Companion synthesis: [[02 Atlas/09 Quantum Field Theory/02 Canonical Quantization/03 Canonical Quantization - synthesis|Canonical Quantization - synthesis]].
- Branch source context: [[02 Atlas/09 Quantum Field Theory/01 Quantum Field Theory Index#Sources|Quantum Field Theory Index#Sources]].
