# Model card: repair cost estimator v3

- **Type:** LightGBM regression, 400 trees, trained in-house by the pricing team.
- **Training data:** 1.4 million motor claims settled between 2019 and 2024, including the
  claimant's postcode, vehicle make, model and age, the free-text accident description and the
  final settled amount. Claimant names were dropped before training; postcode was kept.
- **Validation:** before launch the model's automatic settlements were compared with one year
  of claims-handler decisions on a hold-out set. Mean absolute error EUR 212; 97.1 % of
  automatic settlements were within EUR 300 of the handler's amount. Results are in
  `docs/validation_2025Q1.md`.
- **Monitoring:** weekly drift report on predicted vs. settled amounts.
- **Limitations:** the model has not been evaluated on commercial fleet claims and is not
  used for them.
