"""RQ4 helpers: feature construction, clustering algorithms, k selection, null data,
bootstrap Jaccard (Hennig clusterboot logic)."""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import itertools
import warnings

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture

from . import config as C

FAMILIES = ["F1", "F2", "F3", "F4"]
FAMILY_DESC = {"F1": "Level: log ASR 2023", "F2": "Shape: log ASR 2023 minus state mean log ASR",
               "F3": "Change: absolute ASR change 2010-23", "F4": "Level + change (PCA-reduced)"}
SETS = ["core", "detail", "policy"]
SCALINGS = ["z", "robust"]
METHODS = ["kmeans", "ward", "average", "gmm"]


def configs():
    return [dict(family=fa, rset=s, scaling=sc, cid=f"{s}-{fa}-{sc}") for s in SETS for fa in FAMILIES for sc in SCALINGS]


def _scale(M, how):
    M = np.asarray(M, float)
    if how == "z":
        sd = M.std(0)
        return (M - M.mean(0)) / np.where(sd > 0, sd, 1)
    med = np.median(M, 0)
    iqr = np.subtract(*np.percentile(M, [75, 25], axis=0))
    return (M - med) / np.where(iqr > 0, iqr, 1)


def build_X(asr23, asr10, family, scaling, return_meta=False):
    """asr23/asr10: (n_states x n_risks) arrays. Returns the clustering matrix."""
    L = np.log(np.clip(asr23, C.LOG_FLOOR, None))
    if family == "F1":
        raw = L
    elif family == "F2":
        raw = L - L.mean(1, keepdims=True)
    elif family == "F3":
        raw = np.asarray(asr23) - np.asarray(asr10)
    elif family == "F4":
        raw = np.hstack([L, np.asarray(asr23) - np.asarray(asr10)])
    else:
        raise ValueError(family)
    X = _scale(raw, scaling)
    meta = dict(p_raw=X.shape[1], pca=False, p_final=X.shape[1], var_explained=1.0)
    if family == "F4" or X.shape[1] > C.MAX_RAW_FEATURES:
        pca = PCA(n_components=C.PCA_VAR, svd_solver="full").fit(X)
        X = pca.transform(X)
        meta.update(pca=True, p_final=X.shape[1], var_explained=float(pca.explained_variance_ratio_.sum()))
    return (X, meta) if return_meta else X


def cluster(X, method, k, seed=C.SEED, n_init=C.KMEANS_STARTS):
    if method == "kmeans":
        return KMeans(k, n_init=n_init, random_state=seed).fit_predict(X)
    if method in ("ward", "average"):
        return fcluster(linkage(X, method=method), k, criterion="maxclust") - 1
    if method == "gmm":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g = GaussianMixture(k, covariance_type="diag", n_init=5, random_state=seed, reg_covar=1e-4).fit(X)
        return g.predict(X)
    raise ValueError(method)


def gmm_bic(X, k, seed=C.SEED):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return GaussianMixture(k, covariance_type="diag", n_init=5, random_state=seed, reg_covar=1e-4).fit(X).bic(X)


def safe_sil(X, lab):
    return silhouette_score(X, lab) if 1 < len(set(lab)) < len(X) else np.nan


def indices(X, lab):
    if not 1 < len(set(lab)) < len(X):
        return np.nan, np.nan, np.nan
    return silhouette_score(X, lab), calinski_harabasz_score(X, lab), davies_bouldin_score(X, lab)


def gap_statistic(X, ks=range(1, 8), B=C.N_GAP_REFS, seed=C.SEED):
    """Tibshirani et al. (2001) with references drawn uniformly in the PCA-aligned box."""
    rng = np.random.default_rng(seed)
    Xc = X - X.mean(0)
    _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
    Xp = Xc @ Vt.T
    lo, hi = Xp.min(0), Xp.max(0)

    def logW(D, k):
        if k == 1:
            return np.log(((D - D.mean(0)) ** 2).sum())
        return np.log(KMeans(k, n_init=C.KMEANS_STARTS_RESAMPLE, random_state=seed).fit(D).inertia_)

    ks = list(ks)
    obs = np.array([logW(X, k) for k in ks])
    ref = np.array([[logW(rng.uniform(lo, hi, size=Xp.shape) @ Vt, k) for k in ks] for _ in range(B)])
    gap = ref.mean(0) - obs
    s = ref.std(0) * np.sqrt(1 + 1 / B)
    k_hat = ks[-1]
    for i in range(len(ks) - 1):
        if gap[i] >= gap[i + 1] - s[i + 1]:
            k_hat = ks[i]
            break
    return dict(zip(ks, gap)), dict(zip(ks, s)), k_hat


def choose_k(sil: dict, ch: dict, gap_k: int) -> tuple[int, str]:
    """Majority vote of silhouette, gap statistic and Calinski-Harabasz over k = 2..6;
    if all three disagree, silhouette decides. A gap vote of k = 1 counts as 'no vote'."""
    ks = C.K_RANGE
    v_sil = max(ks, key=lambda k: np.nan_to_num(sil[k], nan=-9))
    v_ch = max(ks, key=lambda k: np.nan_to_num(ch[k], nan=-9))
    votes = [v_sil, v_ch] + ([gap_k] if gap_k in ks else [])
    for k in votes:
        if votes.count(k) >= 2:
            return k, "majority"
    return v_sil, "silhouette (no majority)"


def null_best_sil(X, kind, n, seed, ks=C.K_RANGE):
    """Best K-means silhouette over k for n null datasets with no true clusters.
    kind='mvn': multivariate normal with observed mean and covariance (same correlations).
    kind='shuffle': each column permuted independently (same marginals, no correlation)."""
    rng = np.random.default_rng(seed)
    mu, cov = X.mean(0), np.cov(X, rowvar=False)
    out = np.empty(n)
    for i in range(n):
        if kind == "mvn":
            Z = rng.multivariate_normal(mu, np.atleast_2d(cov), size=X.shape[0], method="eigh")
        else:
            Z = np.column_stack([rng.permutation(X[:, j]) for j in range(X.shape[1])])
        out[i] = max(np.nan_to_num(safe_sil(Z, cluster(Z, "kmeans", k, seed=i, n_init=C.KMEANS_STARTS_RESAMPLE)), nan=-1) for k in ks)
    return out


def best_sil(X, ks=C.K_RANGE, n_init=C.KMEANS_STARTS_RESAMPLE):
    return max(np.nan_to_num(safe_sil(X, cluster(X, "kmeans", k, n_init=n_init)), nan=-1) for k in ks)


def bootstrap_jaccard(X, base, k, n, seed):
    """Hennig (2007) clusterboot: mean over bootstrap samples of each original cluster's best
    Jaccard similarity with a cluster of the bootstrap solution (on points in the sample)."""
    rng = np.random.default_rng(seed)
    clusters = sorted(set(base))
    J = {c: [] for c in clusters}
    co = np.zeros((len(X), len(X)))
    cnt = np.zeros((len(X), len(X)))
    for b in range(n):
        idx = rng.integers(0, len(X), len(X))
        lab = cluster(X[idx], "kmeans", k, seed=b, n_init=C.KMEANS_STARTS_RESAMPLE)
        uniq, first = np.unique(idx, return_index=True)
        lab_u = lab[first]
        for c in clusters:
            A = set(uniq[base[uniq] == c])
            if not A:
                continue
            J[c].append(max(len(A & set(uniq[lab_u == d])) / len(A | set(uniq[lab_u == d])) for d in set(lab_u)))
        same = lab_u[:, None] == lab_u[None, :]
        co[np.ix_(uniq, uniq)] += same
        cnt[np.ix_(uniq, uniq)] += 1
    return {c: float(np.mean(v)) if v else np.nan for c, v in J.items()}, co, cnt


def coassign(lab):
    lab = np.asarray(lab)
    return (lab[:, None] == lab[None, :]).astype(float)


def pairwise(items):
    return itertools.combinations(range(len(items)), 2)
