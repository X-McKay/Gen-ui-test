# Claims Fast-Track

Motor insurance claims service for the mobile app. Customers photograph the damage, fill in
the claim form and submit. A gradient-boosted regression model trained on five years of
settled claims estimates the repair cost. Claims estimated under EUR 2,000 are **settled
automatically** and paid to the customer's account; everything else is queued for a claims
handler.

## What it does

1. The mobile app calls `POST /claims` with the form, the photos and the policy number.
2. `src/model/estimator.py` scores the claim with the LightGBM model in `models/estimator.txt`.
3. `src/settlement/decide.py` applies the threshold and either pays out through the payments
   service or opens a handler task.
4. Handlers can reopen any automatic settlement from the back office (`POST /claims/{id}/reopen`).

There is no language model in this service; the estimator is a tree ensemble trained by the
pricing team (see `docs/model_card.md`).

## Status

In production since March for customers in Germany and Austria. Hosted on Azure (West Europe).

## Access

The mobile app authenticates customers with OAuth2 through the group identity provider; the
back-office endpoints require the `claims-handler` role (see `src/api/auth.py`).
