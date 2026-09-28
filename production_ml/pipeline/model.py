"""Одинаковый вход модели при обучении и расчёте балла."""

import pandas as pd

from .features import FEATURES, SENSORS

MODEL_FEATURES = ("sensor_type",) + FEATURES


def model_frame(rows):
    frame = rows.loc[:, list(MODEL_FEATURES)].copy()
    frame["sensor_type"] = pd.Categorical(frame["sensor_type"], categories=SENSORS)
    return frame
