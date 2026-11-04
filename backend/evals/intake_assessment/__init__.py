"""Evals for the intake's own risk assessment: facts, inherent tier and residual tier.

The product's job is to read a description, extract the facts the rules engine needs and
derive the inherent and residual risk. These evals measure that end to end on the configured
model: per-field accuracy, risk false positives (asserting a sensitive practice or a control
that the text does not support), missed risks, tier accuracy and the cost of each extraction.
"""
