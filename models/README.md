# Bundled prediction models

## Portable nutrition-quality classifier

`nutrition_quality_portable.json` is NutriPulse's pure-Python tabular prediction bundle. It was
trained from the normalized records described in `data/dataset_manifest.json` and runs without
SciPy, scikit-learn, or native model-loading DLLs. See `nutrition_quality_model_card.json` for its
validation results, intended use, and limitations.

## Food-image classifier

NutriPulse includes a MobileNetV2 model fine-tuned on Food-101:

- food_classifier.onnx
- food_labels.json
- food_classifier_model_card.json
- food101_LICENSE.txt

The model must accept a float32 RGB tensor shaped `[1, 3, 224, 224]`, normalized with ImageNet
mean and standard deviation, and return one class-score vector shaped `[1, classes]`.
`food_labels.json` must be a JSON list in model-output order, for example:

```json
["apple", "biryani", "daal", "grilled chicken", "salad"]
```

The app runs this model with ONNX Runtime on the CPU. Uploading an image automatically produces
top-five predictions. The user must still confirm a nutrition record before adding it to the diary.

The source model reports 76.3% top-1 accuracy on Food-101. It is an image-classification aid,
not a portion estimator or medical model. It cannot determine hidden ingredients, allergens,
cooking oil, recipe quantities or exact nutrients. See `food_classifier_model_card.json` and
`THIRD_PARTY_NOTICES.md` for provenance and limitations.

The bundled graph was re-exported from the published epoch-27 checkpoint with the network in
evaluation mode and ONNX opset 17. The application verifies its SHA-256 digest before loading it.
