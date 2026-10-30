import numpy as np
import pandas as pd

from app9.validation import anchor_geometry_probe as probe


def test_family_consensus_uses_training_only_selection_scale_and_polarity():
    train = pd.DataFrame({"reference": np.arange(12, dtype=float)})
    definitions, scores = {}, {}
    for index, family in enumerate(probe.geometry.FAMILIES):
        name = f"feature{index}"
        train[name] = (-1 if index % 2 else 1) * np.arange(12, dtype=float) + index
        definitions[name] = {"family": family}
        scores[name] = 0.8
    full = train.copy()
    baseline, params = probe.consensus_parameters(train, full, definitions, scores, "reference")
    assert params["available"]
    full.loc[6:, "feature0"] += 1000
    changed, new_params = probe.consensus_parameters(train, full, definitions, scores, "reference")
    assert new_params == params
    assert np.allclose(changed.iloc[:6], baseline.iloc[:6])


def test_constant_family_reports_unavailable_instead_of_fabricated_scale():
    train = pd.DataFrame({"reference": np.arange(12, dtype=float)})
    definitions, scores = {}, {}
    for index, family in enumerate(probe.geometry.FAMILIES):
        name = f"feature{index}"
        train[name] = 1.0 if index == 0 else np.arange(12, dtype=float)
        definitions[name] = {"family": family}
        scores[name] = 0.8
    values, metadata = probe.consensus_parameters(train, train, definitions, scores, "reference")
    assert not metadata["available"]
    assert values.isna().all()
