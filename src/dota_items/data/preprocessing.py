"""Train-only sklearn transforms with a portable JSON state, never executable pickle."""

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .contracts import FEATURE_SCHEMA, NUMERIC

COLUMNS = [*NUMERIC, *(f"{k}_missing" for k in NUMERIC)]


def numeric_matrix(rows, columns):
    # Constant fill is a fixed policy, not a statistic fitted to validation/test data.
    frame = pd.DataFrame(rows)[columns].astype(float)
    return SimpleImputer(strategy="constant", fill_value=0, keep_empty_features=True).fit_transform(
        frame
    )


def fit_preprocessor(train_rows):
    if not train_rows:
        raise ValueError("Cannot fit preprocessing without training samples")
    columns = [*COLUMNS, *sorted(set(train_rows[0]) - {*COLUMNS, "sample_id", "hero_id"})]
    scaler = StandardScaler().fit(numeric_matrix(train_rows, columns))
    heroes = sorted({int(r["hero_id"]) for r in train_rows})
    return {
        "schema_version": "coach-preprocessor/1", "feature_schema": FEATURE_SCHEMA,
        "columns": columns, "imputation": "constant_zero_with_explicit_missing_indicators",
        "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
        "variance": scaler.var_.tolist(), "train_samples": int(scaler.n_samples_seen_),
        "hero_categories": heroes,
        "output_columns": [*columns, *(f"hero_id_{hero}" for hero in heroes)],
    }


def transform_features(rows, state):
    if state["schema_version"] != "coach-preprocessor/1" or not set(COLUMNS) <= set(state["columns"]):
        raise ValueError("Unsupported preprocessing state")
    if not rows:
        return np.empty((0, len(state["output_columns"])), dtype=np.float32)
    scaler = StandardScaler()
    scaler.mean_ = np.asarray(state["mean"])
    scaler.scale_ = np.asarray(state["scale"])
    scaler.var_ = np.asarray(state["variance"])
    scaler.n_features_in_ = len(state["columns"])
    scaler.n_samples_seen_ = state["train_samples"]
    categories = state["hero_categories"]
    encoder = OneHotEncoder(categories=[categories], handle_unknown="ignore", sparse_output=False)
    encoder.fit(np.asarray(categories).reshape(-1, 1))
    heroes = encoder.transform(np.asarray([r["hero_id"] for r in rows]).reshape(-1, 1))
    result = np.concatenate([scaler.transform(numeric_matrix(rows, state["columns"])), heroes], axis=1)
    with np.errstate(over="ignore", invalid="ignore"):
        result = result.astype(np.float32)
    if not np.isfinite(result).all():
        raise ValueError("Features overflow float32; inspect source units/ranges")
    return result


def save_arrays(path, features, labels, state, config):
    classes = ["no_purchase", "other", *config.candidate_items]
    item = [classes.index(r["item_action"]) if r["item_mask"] else -1 for r in labels]
    route = [[r["route_dx"], r["route_dy"]] if r["route_mask"] else [0, 0] for r in labels]
    with np.errstate(over="ignore", invalid="ignore"):
        route = np.asarray(route, dtype=np.float32).reshape(-1, 2)
    if not np.isfinite(route).all():
        raise ValueError("Route targets overflow float32")
    np.savez_compressed(
        path, X=transform_features(features, state),
        sample_id=np.asarray([r["sample_id"] for r in features], dtype=str),
        item_target=np.asarray(item, dtype=np.int64),
        item_mask=np.asarray([r["item_mask"] for r in labels], dtype=bool),
        route_target=route, route_mask=np.asarray([r["route_mask"] for r in labels], dtype=bool),
    )
