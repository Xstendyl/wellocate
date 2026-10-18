"""Small statistics helpers used by the analysis scripts, using only the standard library."""
import math


def holm(pvals, alpha=0.05):
    """Holm-Bonferroni correction. Returns (index, p, adjusted_p, reject) tuples in the input order.

    Adjusted p values are made monotone with a running maximum.
    """
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        a = min(1.0, (m - rank) * pvals[i])
        running = max(running, a)
        adj[i] = running
    return [(i, pvals[i], adj[i], adj[i] <= alpha) for i in range(m)]


def welch_p(a, b):
    """Two-sided Welch t-test for unpaired samples. Returns (mean difference, se, p)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan"), float("nan"), float("nan")
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    se = math.sqrt(va / na + vb / nb)
    if se == 0:
        return mb - ma, 0.0, float("nan")
    t = (mb - ma) / se
    df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    return mb - ma, se, 2.0 * _t_sf(abs(t), df)


def _t_sf(t, df):
    """Upper tail of Student's t, computed via the incomplete beta function."""
    x = df / (df + t * t)
    return 0.5 * _betainc(df / 2.0, 0.5, x)


def _betainc(a, b, x):
    """Regularised incomplete beta I_x(a,b) by Lentz's continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    r = front * (f - 1.0)
    return r if x < (a + 1) / (a + b + 2) else 1.0 - _betainc(b, a, 1 - x)


def ols(xs, ys):
    """Slope and its standard error. Returns (slope, se, n)."""
    n = len(xs)
    if n < 3:
        return float("nan"), float("nan"), n
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return float("nan"), float("nan"), n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    s2 = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / (n - 2)
    return b, math.sqrt(s2 / sxx), n
