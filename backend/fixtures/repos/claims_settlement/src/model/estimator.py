"""Repair cost estimate from the LightGBM model trained by the pricing team.

See docs/model_card.md. The model never sees the claimant's name; postcode, vehicle and the
accident description are features.
"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "estimator.txt"
_booster = lgb.Booster(model_file=str(MODEL_PATH)) if MODEL_PATH.exists() else None


def features(form: dict[str, object], photos: list[bytes]) -> pd.DataFrame:
    address = str(form["claimant_address"])
    return pd.DataFrame(
        [
            {
                "postcode": address.split()[-2] if len(address.split()) > 1 else "",
                "registration_prefix": str(form["vehicle_registration"])[:2],
                "description_length": len(str(form["accident_description"])),
                "photo_count": len(photos),
            }
        ]
    )


def estimate_repair_cost(form: dict[str, object], photos: list[bytes]) -> float:
    if _booster is None:
        raise RuntimeError("estimator model file missing")
    return float(_booster.predict(features(form, photos))[0])
