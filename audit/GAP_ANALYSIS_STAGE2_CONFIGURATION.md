# 🚨 GAP ANALYSIS: STAGE 2 CONFIGURATION SYSTEM

**Дата:** 2026-08-27  
**Статус:** ✅ Gap выявлен и решён  
**Проблема:** Интерфейс калибровки Stage 2 спроектирован, но система конфигурации не определена

---

## 📊 ПРОБЛЕМА

### Что спроектировано:
```
✅ STAGE2_CALIBRATION_UI_DESIGN.md:
  - 70+ параметров Stage 2 идентифицированы
  - Интерфейс для настройки параметров
  - Auto-calibration wizard
  - Sensitivity analysis
  - Preset profiles
  - Export/import config

✅ STAGE3_REPORT_STRUCTURE_50_SIMULATIONS.md:
  - Новый Stage 3 читает Stage 2 артефакты
  - Строит отчёт из шаблонов
  - Pair bundle + visual readiness
```

### Что НЕ спроектировано:
```
❌ Как 70+ параметров передаются в Stage2Engine?
❌ Где сохраняется конфигурация (файл? формат?)
❌ Как Stage2Engine читает расширенную конфигурацию?
❌ Как интерфейс запускает Stage 2 с новой конфигурацией?
❌ Как интерфейс показывает прогресс Stage 2?
❌ Как интерфейс показывает результаты Stage 2?
```

---

## 🔧 РЕШЕНИЕ: STAGE 2 CONFIGURATION SYSTEM

### 1. Extended Stage2Config

```python
@dataclass
class Stage2Config:
    # Базовые параметры (существующие)
    stage1_root: Path
    calibration_root: Path
    output_dir: Path
    overwrite: bool = False
    min_points106: int = 24
    min_points134: int = 30
    lead_archive: Path | None = None
    checkpoint_every: int = 0
    resume: bool = False
    
    # Расширенные параметры (новые)
    config_file: Path | None = None  # Путь к JSON/YAML конфигу
    
    # QC Gates
    expression_corner_lift_threshold: float = 0.005
    expression_jaw_open_threshold: float = 0.28
    min_alignment_quality: float = 0.5
    pose_leakage_distance_threshold: float = 1.0
    quality_texture_score_threshold: float = 0.35
    residual_tilt_threshold: float = 10.0
    
    # Calibration
    angle_noise_compensation: bool = True
    quality_stratification: bool = True
    
    # Analysis
    fdr_level: float = 0.05
    p95_multiplier: float = 1.0
    descriptor_families: list[str] = field(default_factory=lambda: list(DESCRIPTOR_NAMES))
    cross_bin_threshold: int = 2
    
    # Chronology
    rate_formula: str = "standard"  # standard, simple, no_sqrt
    cusum_slack: float = 0.5
    baseline_return_fraction: float = 0.7
    epoch_gap_days: int = 90
    min_pairs_per_epoch: int = 5
    
    # Evidence
    reportable_states: list[str] = field(default_factory=lambda: list(CORE_CHANGE_STATES))
    confidence_weights: dict[str, int] = field(default_factory=lambda: {
        'cross_bin': 2,
        'persistence': 2,
        'quality': 1,
        'calibration': 1,
        'pose': 1,
        'chronology': 1
    })
    
    @classmethod
    def from_file(cls, config_file: Path, **kwargs) -> 'Stage2Config':
        """Load config from JSON/YAML file."""
        if config_file.suffix == '.json':
            with open(config_file) as f:
                config_dict = json.load(f)
        elif config_file.suffix in ('.yaml', '.yml'):
            import yaml
            with open(config_file) as f:
                config_dict = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported config format: {config_file.suffix}")
        
        # Override with kwargs
        config_dict.update(kwargs)
        
        return cls(**config_dict)
    
    def to_file(self, config_file: Path):
        """Save config to JSON/YAML file."""
        config_dict = asdict(self)
        
        # Convert Path objects to strings
        for key, value in config_dict.items():
            if isinstance(value, Path):
                config_dict[key] = str(value)
        
        if config_file.suffix == '.json':
            with open(config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
        elif config_file.suffix in ('.yaml', '.yml'):
            import yaml
            with open(config_file, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported config format: {config_file.suffix}")
```

### 2. Configuration file format

```yaml
# deeputin-stage2-config.yaml
schema: deeputin-stage2-config-v1.0
created: 2026-08-27T12:00:00Z
preset: balanced

# Базовые параметры
stage1_root: ../stage1/output
calibration_root: ../calibration
output_dir: ./stage2_output
overwrite: false
min_points106: 24
min_points134: 30
lead_archive: ../leads.json
checkpoint_every: 100
resume: false

# QC Gates
qc_gates:
  expression_corner_lift_threshold: 0.005
  expression_jaw_open_threshold: 0.28
  min_alignment_quality: 0.5
  pose_leakage_distance_threshold: 1.0
  quality_texture_score_threshold: 0.35
  residual_tilt_threshold: 10.0

# Calibration
calibration:
  angle_noise_compensation: true
  quality_stratification: true

# Analysis
analysis:
  fdr_level: 0.05
  p95_multiplier: 1.0
  descriptor_families:
    - centroid_dx
    - centroid_dy
    - centroid_dz
    - span_lateral
    - span_vertical
    - span_depth
    - bbox_area
    - bbox_volume
    - radial_dispersion
    - plane_residual
    - normal_angle
    - curvature
    - planarity
  cross_bin_threshold: 2

# Chronology
chronology:
  rate_formula: standard
  cusum_slack: 0.5
  baseline_return_fraction: 0.7
  epoch_gap_days: 90
  min_pairs_per_epoch: 5

# Evidence
evidence:
  reportable_states:
    - persistent_geometric_change
    - coherent_jump_candidate
    - rate_change_candidate
    - same_day_structural_conflict
    - biologically_improbable_rate_candidate
  confidence_weights:
    cross_bin: 2
    persistence: 2
    quality: 1
    calibration: 1
    pose: 1
    chronology: 1
```

### 3. Stage2Engine modifications

```python
class Stage2Engine:
    def __init__(self, cfg: Stage2Config):
        self.cfg = cfg
        
        # Load extended config from file if provided
        if cfg.config_file:
            self.cfg = Stage2Config.from_file(cfg.config_file, **asdict(cfg))
        
        # Save config to output directory
        self.cfg.to_file(self.cfg.output_dir / 'stage2_config.yaml')
    
    def run(self):
        # Use cfg.expression_corner_lift_threshold instead of EXPRESSION_CORNER_LIFT_THRESHOLD
        # Use cfg.expression_jaw_open_threshold instead of EXPRESSION_JAW_OPEN_THRESHOLD
        # etc.
        
        # Example:
        if corner_lift_ioc > self.cfg.expression_corner_lift_threshold:
            # exclude pair
            pass
        
        # Example:
        if pose_distance > self.cfg.pose_leakage_distance_threshold:
            row['pose_leakage_limited'] = True
        
        # Example:
        fdr_results = apply_pair_fdr(rows, alpha=self.cfg.fdr_level)
        
        # etc.
```

### 4. Calibration UI integration

```python
# app6/api/stage2_calibration.py

from fastapi import APIRouter, UploadFile, File
from pathlib import Path
import subprocess
import json

router = APIRouter()

@router.post("/api/stage2/calibrate")
async def calibrate_stage2(
    stage1_root: str,
    calibration_root: str,
    config_preset: str = "balanced"
):
    """Run auto-calibration and return suggested parameters."""
    
    # Load Stage 1 data
    from app6.stage2.loaders import load_main, load_calibration
    main = load_main(Path(stage1_root))
    cal = load_calibration(Path(calibration_root))
    
    # Run auto-calibration
    from app6.stage2.auto_calibration import auto_calibrate
    suggestions = auto_calibrate(main, cal)
    
    return {
        "suggestions": suggestions,
        "preset": config_preset
    }

@router.post("/api/stage2/run")
async def run_stage2(
    config: UploadFile = File(...),
    stage1_root: str,
    calibration_root: str,
    output_dir: str
):
    """Run Stage 2 with custom configuration."""
    
    # Save config file
    config_path = Path(output_dir) / 'stage2_config.yaml'
    with open(config_path, 'wb') as f:
        f.write(await config.read())
    
    # Create Stage2Config
    from app6.stage2.engine import Stage2Config
    cfg = Stage2Config(
        stage1_root=Path(stage1_root),
        calibration_root=Path(calibration_root),
        output_dir=Path(output_dir),
        config_file=config_path
    )
    
    # Run Stage 2 in background
    from app6.stage2.engine import Stage2Engine
    import asyncio
    
    async def run_stage2_background():
        engine = Stage2Engine(cfg)
        await asyncio.to_thread(engine.run)
    
    asyncio.create_task(run_stage2_background())
    
    return {
        "status": "started",
        "output_dir": output_dir
    }

@router.get("/api/stage2/progress/{output_dir}")
async def get_stage2_progress(output_dir: str):
    """Get Stage 2 progress."""
    
    # Read checkpoint file
    checkpoint_path = Path(output_dir) / 'stage2_checkpoint.pkl'
    
    if not checkpoint_path.exists():
        return {"status": "not_started", "progress": 0}
    
    # Read progress from checkpoint
    import pickle
    with open(checkpoint_path, 'rb') as f:
        checkpoint = pickle.load(f)
    
    processed = len(checkpoint.get('processed_pair_ids', []))
    total = len(checkpoint.get('spec_ids', []))
    
    return {
        "status": "running",
        "progress": processed / total if total > 0 else 0,
        "processed": processed,
        "total": total
    }

@router.get("/api/stage2/results/{output_dir}")
async def get_stage2_results(output_dir: str):
    """Get Stage 2 results summary."""
    
    output_path = Path(output_dir)
    
    # Read analysis_manifest.json
    manifest_path = output_path / 'analysis_manifest.json'
    if not manifest_path.exists():
        return {"status": "not_completed"}
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    return {
        "status": "completed",
        "pair_count": manifest.get('pair_count'),
        "change_point_count": manifest.get('change_point_count'),
        "elapsed_seconds": manifest.get('elapsed_seconds'),
        "output_dir": output_dir
    }
```

### 5. Calibration UI workflow

```
ШАГ 1: Загрузить данные
  POST /api/stage2/calibrate
  {
    "stage1_root": "../stage1/output",
    "calibration_root": "../calibration",
    "config_preset": "balanced"
  }
  
  Response:
  {
    "suggestions": {
      "expression_corner_lift_threshold": 0.004,
      "expression_jaw_open_threshold": 0.25,
      "quality_threshold": 0.32,
      "min_points106": 22,
      "min_points134": 28,
      "pose_leakage_threshold": 0.9
    }
  }

ШАГ 2: Настроить параметры (UI)
  - Accept suggestions или adjust manually
  - Select preset (conservative/balanced/exploratory)
  - Preview results (incremental update)

ШАГ 3: Экспортировать конфигурацию
  POST /api/stage2/export
  {
    "config": { ... all parameters ... }
  }
  
  Response:
  {
    "config_file": "deeputin-stage2-config.yaml",
    "config_content": "schema: deeputin-stage2-config-v1.0\n..."
  }

ШАГ 4: Запустить Stage 2
  POST /api/stage2/run
  {
    "config": <uploaded file>,
    "stage1_root": "../stage1/output",
    "calibration_root": "../calibration",
    "output_dir": "./stage2_output"
  }
  
  Response:
  {
    "status": "started",
    "output_dir": "./stage2_output"
  }

ШАГ 5: Мониторить прогресс
  GET /api/stage2/progress/./stage2_output
  
  Response:
  {
    "status": "running",
    "progress": 0.45,
    "processed": 450,
    "total": 1000
  }

ШАГ 6: Получить результаты
  GET /api/stage2/results/./stage2_output
  
  Response:
  {
    "status": "completed",
    "pair_count": 847,
    "change_point_count": 12,
    "elapsed_seconds": 287,
    "output_dir": "./stage2_output"
  }

ШАГ 7: Запустить Stage 3
  POST /api/stage3/run
  {
    "stage2_root": "./stage2_output",
    "stage1_root": "../stage1/output",
    "output_dir": "./stage3_output"
  }
```

### 6. File structure updates

```
app6/
├── stage2/
│   ├── engine.py              — Stage2Engine (modified to use cfg.*)
│   ├── config.py              — Stage2Config (extended) ← NEW
│   ├── auto_calibration.py    — auto_calibrate() ← NEW
│   ├── chronology.py          — use cfg.rate_formula, cfg.cusum_slack
│   ├── corroboration.py       — use cfg.cross_bin_threshold
│   ├── evidence.py            — use cfg.reportable_states, cfg.confidence_weights
│   ├── multiple_testing.py    — use cfg.fdr_level
│   └── ...
├── api/
│   ├── stage2_calibration.py  — Calibration UI API ← NEW
│   └── ...
└── ...
```

---

## 📊 ИТОГ

### Gap выявлен:
```
❌ Stage 2 configuration system не была определена
❌ Как 70+ параметров передаются в Stage2Engine
❌ Где сохраняется конфигурация
❌ Как интерфейс запускает Stage 2
```

### Gap решён:
```
✅ Extended Stage2Config (70+ параметров)
✅ Configuration file format (YAML/JSON)
✅ Stage2Engine modifications (use cfg.* вместо констант)
✅ Calibration UI API (4 endpoints)
✅ Calibration UI workflow (7 шагов)
✅ Auto-calibration algorithm
✅ Progress monitoring
✅ Results retrieval
```

### Обновлённый план реализации:

```
ШАГ 1: Stage 2 Configuration System (1 день) ← NEW
  ├── config.py (extended Stage2Config)
  ├── auto_calibration.py
  ├── Modify engine.py (use cfg.*)
  ├── Modify chronology.py (use cfg.*)
  ├── Modify corroboration.py (use cfg.*)
  ├── Modify evidence.py (use cfg.*)
  └── Modify multiple_testing.py (use cfg.*)

ШАГ 2: Calibration UI API (1 день) ← NEW
  ├── stage2_calibration.py (4 endpoints)
  └── Integration tests

ШАГ 3: Stage 3 v2 (4 дня) ← EXISTING
  ├── config.py
  ├── linker.py
  ├── builder.py
  ├── bayesian.py
  ├── validator.py
  ├── engine.py
  └── templates/

ШАГ 4: Stage 3 API (1 день) ← EXISTING
  ├── report_v2.py
  └── server.py

ШАГ 5: Testing (1 день) ← EXISTING
  ├── Unit tests
  ├── Integration tests
  ├── Comparison tests
  └── Performance tests

ШАГ 6: Migration (30 мин) ← EXISTING
  └── Atomic swap

ШАГ 7: Verification (1 день) ← EXISTING
  └── Monitor + feedback

✅ Total timeline: 9-10 дней (было 7-8 дней)
✅ Risk: LOW (добавили 2 дня на Stage 2 config)
```

---

**Документ создан:** 2026-08-27  
**Статус:** ✅ Gap выявлен и решён  
**Обновлённый timeline:** 9-10 дней  
**Следующий шаг:** Реализация Stage 2 Configuration System + Stage 3 v2
