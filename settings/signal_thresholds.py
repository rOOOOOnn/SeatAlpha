"""Shared thresholds for seat signals and monitoring rules."""

SIGNAL_THRESHOLDS = {
    "strong_long": 1.0,
    "long": 0.25,
    "short": -0.25,
    "strong_short": -1.0,
    "major_change_z": 1.0,
    "high_divergence": 1.5,
}

