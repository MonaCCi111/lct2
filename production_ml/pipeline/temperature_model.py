"""Единая схема входа температурной модели."""

from .temperature_features import FEATURES

MODEL_FEATURES = FEATURES


def model_frame(rows):
    return rows.loc[:, list(MODEL_FEATURES)].copy()
