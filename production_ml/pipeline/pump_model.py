"""Единая схема входа модели состояния насоса."""

import pandas as pd

from .pump_features import FEATURES, PUMP_STATUSES

MODEL_FEATURES = ("current_status",) + FEATURES


def model_frame(rows):
    frame = rows.loc[:, list(MODEL_FEATURES)].copy()
    frame["current_status"] = pd.Categorical(
        frame["current_status"],
        categories=PUMP_STATUSES,
    )
    return frame
