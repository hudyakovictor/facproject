# ПОЛНЫЙ РЕЕСТР 10 СТАТЕЙ И КАТАЛОГ 100% ФУНКЦИЙ БЭКЕНДА (DEEPUTIN MONOGRAPH SERIES)

**Назначение:** Канонический указатель научно-журналистской серии из 10 статей, подробно описывающих реализацию антропологического и судебно-медицинского анализа архива из 1,900 фотографий Владимира Путина (1999–2026).  
**Охват данных:** 100% извлекаемых признаков (`3DDFA_v3`, `info.json`, `texture.json`, `provenance_sidecar_v1.json`, `09_RESULTS_REGISTER.md`).

---

## 1. ОГЛАВЛЕНИЕ 10 СТАТЕЙ В РЕПОЗИТОРИИ

| # | Название статьи | Файл в репозитории | Ключевой метод / Алгоритм | Наглядный рендер |
|---|---|---|---|---|
| **01** | **«Археология цифрового портрета»** | [`01_ARTICLE_DIGITAL_ARCHAEOLOGY_AND_PROVENANCE.md`](01_ARTICLE_DIGITAL_ARCHAEOLOGY_AND_PROVENANCE.md) | SHA-256 провенанс, EXIF-аудит, 9 ракурсных корзин (Pose Gate ≤ 6°) | `01_archaeology_provenance_render.jpg` |
| **02** | **«Сквозь пиксели к костям»** | [`02_ARTICLE_3DDFA_BFM_RAW_COORDINATES.md`](02_ARTICLE_3DDFA_BFM_RAW_COORDINATES.md) | Нейросеть 3DDFA_v3, Basel Face Model, Raw Object-Normalized Coordinates | `02_3ddfa_bfm_geometry_render.jpg` |
| **03** | **«Анатомия стабильности»** | [`03_ARTICLE_21_ZONES_AND_SUBSET_91.md`](03_ARTICLE_21_ZONES_AND_SUBSET_91.md) | 21 костная зона лица, веса ($w=1.0$), детерминированный Subset-91 | `02_3ddfa_bfm_geometry_render.jpg` |
| **04** | **«Свет, тень и силикон»** | [`04_ARTICLE_UV_ALBEDO_AND_DEEPFAKE_DETECTION.md`](04_ARTICLE_UV_ALBEDO_AND_DEEPFAKE_DETECTION.md) | Нормализация альбедо (De-lighting), спектр Лапласа, детекция швов и дипфейков | `04_uv_albedo_deepfake_render.jpg` |
| **05** | **«Суд вероятностей»** | [`05_ARTICLE_BAYESIAN_COURTROOM_AND_SNR.md`](05_ARTICLE_BAYESIAN_COURTROOM_AND_SNR.md) | Байесовский вывод ($H_0, H_1, H_2$), нормализованный SNR, анизотропный шум X/Y/Z | `07_chronology_aba_return_render.jpg` |
| **06** | **«Защита от самообмана»** | [`06_ARTICLE_LOPO_FDR_AND_NEGATIVE_CONTROL.md`](06_ARTICLE_LOPO_FDR_AND_NEGATIVE_CONTROL.md) | Протокол LOPO 7/7 HIGH, контроль FDR 0.05 Бенджамини-Хохберга, негативный контроль | `01_archaeology_provenance_render.jpg` |
| **07** | **«Закон необратимости времени»** | [`07_ARTICLE_AGEING_CURVE_AND_ABA_RETURN.md`](07_ARTICLE_AGEING_CURVE_AND_ABA_RETURN.md) | Монотонная кривая старения, необратимость костей A->B->A, правило одного дня | `07_chronology_aba_return_render.jpg` |
| **08** | **«Хронологическая кластеризация»** | [`08_ARTICLE_CHRONOLOGICAL_CLUSTERING_AND_BOUNDARIES.md`](08_ARTICLE_CHRONOLOGICAL_CLUSTERING_AND_BOUNDARIES.md) | Дорожки кластеров #1, #2, #3 на шкале 1999–2026, Boundary Detector ($p < 0.001$) | `07_chronology_aba_return_render.jpg` |
| **09** | **«Анатомия гипотез»** | [`09_ARTICLE_HYPOTHESIS_VALIDATION_SHIFT_BIAS.md`](09_ARTICLE_HYPOTHESIS_VALIDATION_SHIFT_BIAS.md) | Изолированная проверка 90+ гипотез (`putin`, `udmurt`, `vasilich`), сдвиг Shift Bias | `02_3ddfa_bfm_geometry_render.jpg` |
| **10** | **«Вечность в блокчейне»** | [`10_ARTICLE_BLOCKCHAIN_NFT_AND_ARWEAVE.md`](10_ARTICLE_BLOCKCHAIN_NFT_AND_ARWEAVE.md) | Гибридный хостинг 15–25 ГБ (IPFS/Arweave + CDN), 1,900 NFT и воронка монетизации | `01_archaeology_provenance_render.jpg` |

---

## 2. ПОЛНЫЙ СВОДНЫЙ КАТАЛОГ РЕАЛИЗОВАННЫХ ФУНКЦИЙ БЭКЕНДА (100% ОХВАТ КОДА)

Для удобства аудита ниже сгруппированы все ключевые функции и классы модулей `app6/`, описанные в 10 статьях:

### А. Слой цифровой археологии и провенанса (Статья #01)
- `app6/stage1/input_provenance.py`:
  - `sha256_hash_file(path: Path) -> str` — расчет 64-символьного хеша изображения.
  - `extract_exif_metadata(image_path: Path) -> dict` — извлечение дат, модели камеры и фокусного расстояния.
  - `build_date_provenance(filename: str, exif: dict) -> ProvenanceRecord` — сверка даты EXIF с именем файла.
- `app6/run_preflight.py`:
  - `verify_four_provenance_hashes(run_dir: Path) -> dict` — фиксация 4 хешей прогона (`dataset_hash`, `code_hash`, `model_hash`, `config_hash`).
- `app6/archive_adapter.py`:
  - `deduplicate_near_duplicates(photo_pool: list) -> list` — очистка секундных серийных кадров по качеству $Q$.
  - `classify_pose_bin(yaw, pitch, roll) -> str` — распределение фото по 9 ракурсным корзинам (допуск $\le 6^\circ$).

### Б. Слой 3D-реконструкции и костной геометрии (Статьи #02, #03)
- `app6/api/bfm_topology.py`:
  - `class BFMModel` — хранение базовой топологии лица `mean_shape`, костей `id_base` и мимики `exp_base`.
  - `compute_shape(alpha_id, alpha_exp) -> np.ndarray` — уравнение реконструкции 3D-сетки $S_{bone} = \bar{S} + \mathbf{P}_{id} \cdot \alpha_{id}$.
  - `_convert_npy_to_safe_npz(npy_path) -> Path` — безопасная загрузка весов `.npz` с проверкой SHA-256.
  - `is_bfm_available() -> bool` — проверка локальных весов `3ddfa_v3/assets/`.
- `app6/stage2/loaders.py`:
  - `load_raw_mesh_coordinates(photo_id: str) -> np.ndarray` — экспорт `Raw Object-Normalized Coordinates`.
  - `normalize_zero_mean(coords: np.ndarray) -> np.ndarray` — центрирование по центру масс костей.
- `app6/api/skin_zones.py`:
  - `zone_catalog() -> list` — атлас 21 зоны лица с весами ($w=1.0$ для глазниц и скул).
  - `load_skin_zone_report(photo_dir) -> dict` — исключение губ и щек при улыбке/открытом рте (`mouth_open > 0.35`).
- `app6/stage2/landmark_policy.py`:
  - `filter_subset_91(vertices_3d) -> np.ndarray` — отбор ровно 91 стабильной костной вершины (Subset-91).
  - `nan_safe_landmark_intersection(a, b) -> tuple` — NaN-безопасное пересечение видимых точек профиля.

### В. Слой анализа UV-текстур и детекции дипфейков (Статья #04)
- `uv_module/delight.py`:
  - `remove_specular_highlights(uv_map) -> np.ndarray` — удаление бликов (de-lighting) и выравнивание светимости.
  - `normalize_albedo_contrast(uv_map, mask) -> np.ndarray` — контрастная нормализация альбедо кожи.
- `uv_module/uv_semantic.py` & `uv_module/analysis.py`:
  - `build_analytic_uv_mask(confidence_map, threshold=0.60) -> np.ndarray` — маскировка волос, фона и одежды.
  - `class UVMaskedTextureMetrics` — структура текстурного индекса, контраста и дисперсии.
- `uv_module/detail.py`:
  - `compute_laplacian_variance(uv_roi) -> float` — расчет высокочастотного спектра Лапласа для выявления сглаживания кожи.
  - `filter_jpeg_grid_harmonics(spectrum) -> np.ndarray` — удаление артефактов сетки 8×8 сжатия JPEG 1999 г.
- `uv_module/inpaint_blend.py`:
  - `detect_border_gradient_anomalies(uv_map) -> list` — детекция сшивки синтетических швов по периметру шеи и ушей.

### Г. Слой статистики, LOPO-калибровки и байесовского вывода (Статьи #05, #06)
- `app6/api/compare.py`:
  - `compare_records(a, b) -> dict` — парное сравнение снимков (костный SNR, альбедо, 21 зона).
  - `compute_bayesian_posteriors(snr, texture, gap) -> tuple` — расчет вероятностей $(P(H_0), P(H_1), P(H_2))$.
- `app6/api/noise_calibration.py`:
  - `load_anisotropic_covariance() -> np.ndarray` — анизотропная матрица ковариации шума 3DDFA_v3 X/Y/Z.
  - `compute_mahalanobis_snr(delta_vec, cov_matrix) -> float` — расчет нормализованного SNR Махаланобиса.
- `app6/run_calibration.py` & `app6/api/calibration.py`:
  - `load_calibration_health(root) -> dict` — аудит 7 независимых эталонных персон (`LOPO 7/7 HIGH`).
  - `_bucket_confidence(person_count, frame_count) -> str` — классификация доверия ракурсной выборки.
- `app6/multiple_testing.py`:
  - `apply_benjamini_hochberg_fdr(p_values, fdr=0.05) -> list[bool]` — контроль ложных тревог ($\text{FDR} \le 0.05$).
  - `compute_effective_sample_size(timestamps) -> int` — расчет эффективного размера выборки (ESS).
- `app6/stage2/same_day_gate.py`:
  - `run_negative_control_matrix(control_pool) -> float` — тест негативного контроля на 5 сторонних лицах (`0.000%` false alarms).

### Д. Слой хронологии, кластеризации и гипотез (Статьи #07, #08, #09, #10)
- `app6/irreversible_return.py`:
  - `detect_a_b_a_returns(chronology) -> list` — детекция парадоксального возврата `A -> B -> A`.
  - `guard_against_null_return(event) -> bool` — предохранитель от ложного срабатывания на NULL/пропусках.
- `app6/same_day_gate.py`:
  - `check_same_day_contradictions(pool) -> list` — правило одного дня (Same-Day Gate).
- `app6/api/research_timeline.py` & `app6/stage1_timeline.py`:
  - `fit_physiological_ageing_curve(coords, years) -> np.ndarray` — монотонный сплайн старения.
  - `build_chronological_tracks(pool) -> dict` — построение дорожек кластеров #1, #2, #3 на шкале 1999–2026.
  - `detect_cluster_transition_boundaries(series, min_days=90) -> list` — алгоритм Boundary Detector ($p < 0.001$).
- `app6/private_hypothesis_seed/`:
  - `load_legacy_hypothesis_ledger() -> list` — чтение 90+ журналистских гипотез для `putin`, `udmurt`, `vasilich`.
  - `apply_shift_bias_calibration(record, shift_x, shift_y, shift_z, tolerance) -> Record` — калибровка смещения старой разметки.
- `app6/api/report.py`:
  - `export_signed_release_bundle(run_id) -> Path` — формирование зашифрованного архива **Immutable Release Bundle** с SHA-256 подписями для блокчейна и СМИ.
