---
type: synthesis
tags:
  - synthesis
  - area/physics
  - status/seed
parent_index: "[[02 Atlas/09 Quantum Field Theory/02 Canonical Quantization/01 Canonical Quantization Index]]"
status: seed
---

# Summary

Canonical quantization applies the Hamiltonian framework of quantum mechanics to a field theory by treating the field and its conjugate momentum on a spatial slice as the canonical variables. Their equal-time commutators are postulated to have the same canonical form as the classical Poisson brackets, with the correspondence factor of $i$ in units $hbar=1$. The Hamiltonian then generates time evolution.

# The field as a system of canonical variables

For fields $\phi^a(\mathbf{x},t)$ with Lagrangian density $\mathcal L$, define the momentum conjugate to each field component by

$$
\pi_a(\mathbf{x},t)=\frac{\partial\mathcal L}{\partial\dot\phi^a(\mathbf{x},t)}.
$$

At a fixed time, the classical canonical data are the functions $\phi^a(\mathbf{x})$ and $\pi_a(\mathbf{x})$ over space. The Hamiltonian is the spatial integral of the Hamiltonian density, with velocities eliminated in favour of momenta. For example, for a real scalar field with $\mathcal L=\tfrac12\dot\phi^2-\tfrac12(\nabla\phi)^2-V(\phi)$, $\pi=\dot\phi$ and

$$
H=\int d^3x\left[\frac12\pi^2+\frac12(\nabla\phi)^2+V(\phi)\right].
$$

The field and its conjugate momentum are local canonical variables; the total momentum of the field configuration is a different quantity. This Hamiltonian description selects a time slice, so Lorentz invariance is not manifest at each step.

# Quantization rule

Promote $\phi^a(\mathbf{x})$ and $\pi_a(\mathbf{x})$ to operators and impose, at a common time,

$$
[\hat\phi^a(\mathbf{x}),\hat\phi^b(\mathbf{y})]=0,\qquad
[\hat\pi_a(\mathbf{x}),\hat\pi_b(\mathbf{y})]=0,\qquad
[\hat\phi^a(\mathbf{x}),\hat\pi_b(\mathbf{y})]
=i\,\delta^a{}_b\,\delta^{(3)}(\mathbf{x}-\mathbf{y}).
$$

These are equal-time canonical commutation relations (CCRs). The spatial delta function expresses locality of the canonical pairing: the field at $\mathbf{x}$ is canonically paired with momentum at the same point. For a single real scalar field the species labels drop out. The displayed normalization assumes $\hbar=1$ and the usual continuum normalization of the spatial delta function.

The correspondence with classical mechanics is a quantization prescription: schematically, a classical Poisson bracket is represented by $1/i$ times the operator commutator. It motivates the CCRs, but the CCRs are not a theorem that follows from the classical Poisson bracket alone. A quantization also requires choices about the operator algebra, representation, constraints, ordering, and (in a continuum theory) regularization. This note describes the canonical starting point, not a complete construction of every quantum field theory.

# Why modes help

For a free scalar field, Fourier modes decouple in the classical equations and each momentum mode behaves as a harmonic oscillator with frequency $\omega_{\mathbf p}=\sqrt{\mathbf p^2+m^2}$. Quantizing those oscillators gives creation and annihilation operators. Their algebra can be chosen so that the mode expansion reproduces the field CCRs. This makes the infinite collection of field degrees of freedom tractable and identifies particle excitations in the free theory.

The mode expansion is a consequence and useful realization of the canonical algebra for the free theory; it is not the definition of canonical quantization in general. Interactions retain the canonical starting point but generally spoil the independent-oscillator solution.

# Scope and assumptions

The fields in these formulas are formal operator-valued distributions, rather than ordinary operators defined pointwise. The delta function in the CCR is likewise a distribution. A precise formulation smears the fields against suitable test functions (or first imposes a regulator, such as a finite spatial lattice or box) and specifies a representation of the resulting algebra. Equal time matters: these are canonical relations on one chosen spatial slice, not commutators between arbitrary spacetime points. In the Schrödinger picture the canonical operators are time independent and states evolve with $H$; in other pictures the operators carry time dependence while the equal-time algebra is preserved.

# Connection to the companion notes

- [[02 Atlas/09 Quantum Field Theory/02 Canonical Quantization/02 Canonical Quantization|Canonical Quantization]] states the basic rule.
- [[02 Atlas/09 Quantum Field Theory/02 Canonical Quantization/04 Canonical Commutation Relations - derivation|Canonical Commutation Relations - derivation]] explains the classical bracket kernel and the quantization step.
- [[02 Atlas/09 Quantum Field Theory/02 Canonical Quantization/05 Free Scalar Field - example - mode expansion|Free Scalar Field - example - mode expansion]] works through the free-field realization.

# Sources

- Tong, David. *Quantum Field Theory*, §1.4, pp. 19–20 (Hamiltonian field variables) and §2.1, p. 21 (canonical quantization and equal-time algebra); §2.2, pp. 23–24 (free scalar modes). Printed page numbers; local PDF pages 25–30.
- Local file: [[02 Atlas/09 Quantum Field Theory/99 Sources/01 qft_david_tong.pdf|qft_david_tong.pdf]].
- Branch source context: [[02 Atlas/09 Quantum Field Theory/01 Quantum Field Theory Index#Sources|Quantum Field Theory Index#Sources]].
