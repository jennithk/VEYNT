# Architecture

## Overview

The voice clone defense prototype follows a modular, simulated audio-processing pipeline with a clear risk engine and explainability layer.

## Pipeline

1. Recorded or simulated call audio enters the system.
2. Audio is segmented into short chunks for near-real-time streaming simulation.
3. Features are extracted from each chunk for AI voice detection and speech analysis.
4. Speaker verification compares embeddings to an enrolled trusted profile.
5. ASR and context analysis detect suspicious requests and urgency.
6. The risk engine combines multiple signals into a score.
7. Alerts and recommendations are rendered in the dashboard.
8. Event metadata is saved to history without retaining raw audio when unnecessary.

## Scope boundaries

This prototype is intentionally limited to simulated processing. It does not intercept live VoIP or cellular traffic.
