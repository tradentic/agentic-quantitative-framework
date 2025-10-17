# Feature Inventory

## Matrix Profile (`features.matrix_profile`)
- **Docstring:** Matrix-profile utilities with `MATRIX_PROFILE_ENGINE` override support.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L2-L21】
- **Naive engine:** Discord distance 1.33, primary motif 0.03, motif counts `[2, 2, 2]` on a 60-point toy sine wave (≈139 ms).【F:reports/audit/20251017_2201_postfix/feature_checks.json†L4-L13】
- **Numba request:** For a 20-point slice with subseq_length=2 the runtime forced the pure-Python fallback, completing in ≈13.7 ms (no JIT dependency required).【F:reports/audit/20251017_2201_postfix/feature_checks.json†L14-L20】

## Change Points (`features.change_points`)
- **Docstring:** Offline PELT + optional BOCPD detector wrapper.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L22-L45】
- **Synthetic run:** Breakpoints recovered at indices 40 & 80 with deltas `[1.5, -2.0]`; execution ≈8.3 ms.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L24-L45】

## Hawkes Features (`features.hawkes_features`)
- **Docstring:** Hawkes self-excitation metrics with exponential kernel fitter.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L46-L56】
- **Synthetic run:** Fit converged to baseline 1.89, branching ratio 0.037 on 50 exponential timestamps (≈23.6 ms).【F:reports/audit/20251017_2201_postfix/feature_checks.json†L48-L56】

## Microstructure (`features.microstructure`)
- **Docstring:** Order flow imbalance, book imbalance, Kyle's λ, Amihud illiquidity, and spread metrics.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L58-L112】
- **Synthetic run:** Produced finite OFI (1130), book imbalance (~0.18), Kyle's λ (~4.7e-4), Amihud (~5.2e-8), and average spreads on grouped NBBO/trade frames (≈23.3 ms).【F:reports/audit/20251017_2201_postfix/feature_checks.json†L60-L112】

## VPIN (`features.vpin`)
- **Docstring:** Volume-synchronised probability of informed trading metrics.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L113-L127】
- **Synthetic run:** VPIN=1.0 with Δ=0.25 over 5 synthetic prints (≈6.5 ms).【F:reports/audit/20251017_2201_postfix/feature_checks.json†L115-L126】

## TS2Vec (`features.generate_ts2vec_embeddings`)
- **Docstring:** Supabase-friendly embedding generator with TS2Vec fallback identity path.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L128-L275】
- **Synthetic run:** Returned three 128-d identity embeddings (fallback path engaged) with canonical metadata; runtime ≈0.44 ms.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L129-L275】

## MiniRocket (`features.minirocket_embeddings`)
- **Docstring:** MiniRocket-based embeddings for multivariate panels; optional `sktime` dependency.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L277-L282】
- **Runtime status:** Import succeeds under NumPy≥2.0, but execution raises a controlled `DependencyUnavailable` because `sktime` is not installed in this environment.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L277-L282】【f8fd4b†L1-L1】
- **PCA pipeline:** Downstream PCA reducer projects to 128 dimensions via the refreshed artifact.【c3f0fc†L1-L2】

## DeepLOB (`features.deeplob_embeddings`)
- **Docstring:** Lightweight DeepLOB encoder with device and weights hints.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L283-L286】
- **Runtime status:** Import succeeds; requesting embeddings raises a `DependencyUnavailable` warning because `torch` is absent, matching optional dependency expectations.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L283-L286】【f8fd4b†L1-L2】
