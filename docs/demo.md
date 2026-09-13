# Demo Guide

## Demo narrative

The judge should understand this as a simulated near-real-time impersonation defense prototype. The system demonstrates the decision flow and explains the risk logic, while clearly separating prototype logic from production-grade AI claims.

## Scenario 1: Genuine call

- low AI probability
- high speaker match
- low context risk
- recommended action: continue

## Scenario 2: AI-cloned call

- high AI probability
- low speaker match
- suspicious credential or payment request
- recommended action: additional verification

## Scenario 3: Executive impersonation attack

- urgent financial request
- secrecy instruction
- potential credential theft request
- high risk
- recommended action: do not authorize

## Scenario 4: Medium-risk call

- mostly genuine voice
- suspicious context but not high enough for immediate block
- additional verification required

## Speaker notes

- emphasize the system is simulating streaming analysis
- explain that the detector is demo-only and modular
- highlight the modular architecture for future real models
- clarify that the platform recommends, but does not execute, security actions
