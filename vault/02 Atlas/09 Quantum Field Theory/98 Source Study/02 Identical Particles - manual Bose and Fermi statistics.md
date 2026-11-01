---
type: example
tags:
  - example
  - source-study
  - area/physics
  - status/seed
parent_index: "[[02 Atlas/09 Quantum Field Theory/98 Source Study/01 Source Study]]"
status: seed
---

# Summary

This example shows exactly what Tong means when he says that in ordinary quantum mechanics we put Bose or Fermi statistics in by hand.

# Problem

Consider two identical, non-interacting, spinless particles in a one-dimensional infinite square well of length $L$.

The one-particle eigenfunctions are

$$
u_n(x)=\sqrt{\frac{2}{L}}\sin\!\left(\frac{n\pi x}{L}\right),
\qquad n=1,2,3,\dots
$$

with energies

$$
E_n=\frac{n^2\pi^2\hbar^2}{2mL^2}\equiv n^2 E_0.
$$

Find the ground state and first excited state if the particles are:

1. bosons
2. fermions

# Solution

If the particles were distinguishable, we would begin with product states

$$
u_n(x_1)u_m(x_2)
$$

with total energy

$$
E=E_n+E_m=(n^2+m^2)E_0.
$$

For identical particles, ordinary non-relativistic quantum mechanics does not choose the correct statistics for us. We must impose the symmetry rule separately:

$$
\Psi(x_1,x_2)=+\Psi(x_2,x_1) \quad \text{for bosons},
$$

$$
\Psi(x_1,x_2)=-\Psi(x_2,x_1) \quad \text{for fermions}.
$$

So for $n\neq m$ we manually build the allowed states:

$$
\Psi_B(x_1,x_2)
=
\frac{1}{\sqrt{2}}
\Bigl(
u_n(x_1)u_m(x_2)+u_m(x_1)u_n(x_2)
\Bigr),
$$

$$
\Psi_F(x_1,x_2)
=
\frac{1}{\sqrt{2}}
\Bigl(
u_n(x_1)u_m(x_2)-u_m(x_1)u_n(x_2)
\Bigr).
$$

If $n=m$, then the bosonic state

$$
\Psi_B(x_1,x_2)=u_n(x_1)u_n(x_2)
$$

is allowed, but the fermionic state vanishes because the antisymmetrized combination is zero.

For bosons, both particles may occupy the lowest level $n=1$, so the ground state is

$$
\Psi_{\mathrm{ground}}^{(B)}(x_1,x_2)=u_1(x_1)u_1(x_2),
$$

with energy

$$
E_{\mathrm{ground}}^{(B)}=2E_1=2E_0.
$$

The first excited bosonic state has one particle in $n=1$ and one in $n=2$:

$$
\Psi_{1}^{(B)}(x_1,x_2)
=
\frac{1}{\sqrt{2}}
\Bigl(
u_1(x_1)u_2(x_2)+u_2(x_1)u_1(x_2)
\Bigr),
$$

with energy

$$
E_{1}^{(B)}=E_1+E_2=(1+4)E_0=5E_0.
$$

For fermions, both particles cannot occupy $n=1$, because the antisymmetric state would be zero. The lowest allowed state is therefore

$$
\Psi_{\mathrm{ground}}^{(F)}(x_1,x_2)
=
\frac{1}{\sqrt{2}}
\Bigl(
u_1(x_1)u_2(x_2)-u_2(x_1)u_1(x_2)
\Bigr),
$$

with energy

$$
E_{\mathrm{ground}}^{(F)}=E_1+E_2=5E_0.
$$

The first excited fermionic state is

$$
\Psi_{1}^{(F)}(x_1,x_2)
=
\frac{1}{\sqrt{2}}
\Bigl(
u_1(x_1)u_3(x_2)-u_3(x_1)u_1(x_2)
\Bigr),
$$

with energy

$$
E_{1}^{(F)}=E_1+E_3=(1+9)E_0=10E_0.
$$

# Takeaway

The Hamiltonian gives us product states such as $u_1(x_1)u_2(x_2)$ and $u_2(x_1)u_1(x_2)$, but it does not tell us whether the physical state should be their symmetric or antisymmetric combination. In ordinary quantum mechanics we add that rule by hand:

$$
\text{bosons} \Rightarrow \text{symmetric states only},
\qquad
\text{fermions} \Rightarrow \text{antisymmetric states only}.
$$

This is the point Tong is making in his discussion of identical particles.

# Sources

- Tong, David. *Quantum Field Theory*, printed p. 3, PDF p. 9.
- Local file: [[02 Atlas/09 Quantum Field Theory/99 Sources/01 qft_david_tong.pdf|qft_david_tong.pdf]]
