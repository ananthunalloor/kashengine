---
title: Markets and predictions
---

# Markets and predictions

The markets domain stores instrument definitions, market quotes, global cues, prediction outputs, and prediction evaluation. The primary target is configured as an instrument of kind `target`; other instruments can be indexes or cues.

## Instrument configuration

The Phase 13 implementation described by the project session summary defines these invariants:

- Instrument kind is one of the registered kinds (`target`, `index`, or `cue`).
- Weight is bounded from -1 to 1.
- Scale must be greater than zero.
- Only one target instrument may exist.
- The target cannot be duplicated, have its kind changed, be disabled, or be deleted through the supported operations.
- Cue weight aggregation and target lookup use the market service helpers.

The Ops > Instruments page stores the live set. Do not introduce a second Python constant list that can drift from the database records.

## Prediction inputs and result

The prediction combines stored news/sentiment data with configured market cues and instrument weights. A valid result must make its target and evaluation date clear. It must also distinguish missing or stale input from a real neutral signal. Market timing follows the configured local market close and final-data buffer.

Do not interpret a prediction as a guaranteed return or financial advice. Document scoring scales, sign conventions, normalization, missing-input behavior, and all thresholds. If any scoring weights change, add regression tests with fixed input/output cases and update this page.

## Evaluation

Evaluation compares persisted predictions with subsequently observed market direction. Keep the outcome definition explicit. Test correct, incorrect, unchanged, missing-quote, and not-yet-evaluable cases. Avoid data leakage: a feature for a prediction date must not incorporate information that was unavailable at prediction time.

Use the generated [Python API reference](../reference/generated/index.md) to find the current module and function signatures for market helpers.
