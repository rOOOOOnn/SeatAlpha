"""Shared thresholds for seat signals and monitoring rules."""

SIGNAL_THRESHOLDS = {
    "strong_long": 1.0,
    "long": 0.25,
    "short": -0.25,
    "strong_short": -1.0,
    "major_change_z": 1.0,
    "high_divergence": 1.5,
}

# Absolute, bounded direction scores are used for the human-readable labels.
# Keep these separate from cross-sectional Z thresholds, which remain useful
# for relative ranking and divergence detection.
DIRECTION_THRESHOLDS = {
    "strong_long": 0.20,
    "long": 0.02,
    "short": -0.02,
    "strong_short": -0.20,
}
