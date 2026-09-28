"""Фиксированная схема входа модели состояния вентилятора."""

from .fan_features import FEATURES

MODEL_FEATURES = FEATURES


def model_frame(rows):
    return rows.loc[:, list(MODEL_FEATURES)].copy()
