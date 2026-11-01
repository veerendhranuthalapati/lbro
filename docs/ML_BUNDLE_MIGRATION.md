# ML bundle migration (v3)

Legacy artifacts **`cicids2017_classifier.pkl`**, **`scaler.pkl`**, **`label_encoder.pkl`**, and hand-edited **`registry.json`** are superseded by the signed bundle directory:

`backend/app/ml/models/bundle/`

- Loader: `app/ml/classifier.py` → `app/ml/bundle_io.py`
- Config: `ML_MODEL_BUNDLE_DIR`, `ML_MODEL_SIGNING_KEY`
- Train: `python scripts/train_models_cli.py --sign`
- Verify: `python scripts/verify_model.py --load-model`

Remove legacy pickle files from deployments after verifying the bundle loads in staging.
