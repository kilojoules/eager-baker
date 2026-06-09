"""
power.py — Gate B power calculation for Step 3.

Primary test: between-model difference in OVER-EAGER RATE = fraction of tasks with
>=1 over-eager menu selection. This is a rare-event two-proportion comparison.

We use the normal-approximation two-proportion power formula and report:
  (a) n/model required for plausible effect sizes at 80% power, alpha=0.05 (two-sided)
  (b) the minimum detectable difference (MDE) at candidate feasible n values.
Fisher's exact (used for the actual analysis at small n) needs similar-or-larger
n than the normal approx, so these are optimistic lower bounds — stated as such.
"""
import math

Z_A = 1.959963985   # alpha=0.05 two-sided
Z_B = 0.8416212336  # power=0.80


def n_per_group(p1, p2, za=Z_A, zb=Z_B):
    pbar = (p1 + p2) / 2
    a = za * math.sqrt(2 * pbar * (1 - pbar))
    b = zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return (a + b) ** 2 / (p1 - p2) ** 2


def power_for_n(p1, p2, n, za=Z_A):
    """Achieved power for given n/group (normal approx)."""
    pbar = (p1 + p2) / 2
    se0 = math.sqrt(2 * pbar * (1 - pbar) / n)
    se1 = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n)
    z = (abs(p1 - p2) - za * se0) / se1
    # Phi(z)
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def mde(p1, n, za=Z_A, zb=Z_B):
    """Minimum detectable p2 (>p1) at 80% power for given baseline p1 and n/group."""
    p2 = p1
    while p2 < 1.0:
        p2 += 0.005
        if n_per_group(p1, p2) <= n:
            return p2
    return None


print("PILOT over-eager rates (menu): cautious 0/8=0%, eager 1/8=12.5%; combined ~6%.")
print("Plausible base rates 5-25%.\n")

print("(a) n PER MODEL needed @ 80% power, alpha=0.05 (two-sided):")
print(f"    {'p1 vs p2':18s} {'n/model':>8} {'total(3 models)':>16}")
for p1, p2 in [(0.10, 0.25), (0.10, 0.30), (0.05, 0.25), (0.05, 0.30),
               (0.10, 0.40), (0.15, 0.40), (0.20, 0.50), (0.10, 0.50)]:
    n = n_per_group(p1, p2)
    print(f"    {f'{p1:.0%} vs {p2:.0%}':18s} {math.ceil(n):8d} {3*math.ceil(n):16d}")

print("\n(b) MINIMUM DETECTABLE p2 at 80% power for feasible n (baseline p1=15%):")
print(f"    {'n/model':>8} {'total(3)':>9} {'detectable p2 (from 15%)':>26}")
for n in [15, 20, 30, 50, 80, 100]:
    m = mde(0.15, n)
    print(f"    {n:8d} {3*n:9d}   {('>= %.0f%% (diff %.0f pp)' % (m*100,(m-0.15)*100)) if m else 'no detectable diff <100%':>26}")

print("\n(c) Achieved power if we run n=30/model, for a few true effects:")
for p1, p2 in [(0.10, 0.25), (0.10, 0.40), (0.05, 0.30), (0.20, 0.50)]:
    print(f"    {p1:.0%} vs {p2:.0%}:  power = {power_for_n(p1,p2,30):.0%}")
