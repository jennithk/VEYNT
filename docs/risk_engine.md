# Risk Engine

## Overview

The risk engine combines signal contributors such as:

- AI voice probability
- speaker mismatch
- transcript-based risk
- urgency and secrecy indicators
- verification status

## Prototype rule set

The scoring thresholds are deliberately configurable and labeled as prototype-only thresholds.

## Risk categories

- LOW: continue or allow
- MEDIUM: request verification
- HIGH: block sensitive action and recommend independent verification

## Important note

The prototype does not execute transactions or block live financial actions.
