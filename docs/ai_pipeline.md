# AI Pipeline

## Overview

The current pipeline is intentionally modular so a placeholder detector can be replaced by a real model later.

## Current implementation

- The backend exposes a FastAPI service.
- The AI detector interface is represented as a pluggable component.
- The prototype currently exposes a demo-only adapter with explicit labeling to avoid implying a trained model. 

## Future real model integration

A production-grade system would integrate a trained deepfake detector using audio features such as spectral artifacts, prosody deviations, and vocoder signatures.

## Limitation

This prototype does not claim measured accuracy or benchmark success without validated evaluation data.
