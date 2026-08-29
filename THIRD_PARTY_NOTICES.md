# Third-party notices

## MobileNetV2 Food-101 model

- Model: `models/food_classifier.onnx`
- Author/repository: AlexKoff88, `mobilenetv2_food101`
- Source: https://huggingface.co/AlexKoff88/mobilenet_v2_food101
- Training code: https://github.com/AlexKoff88/mobilenetv2_food101
- License: Apache License 2.0
- Reported top-1 Food-101 accuracy: 76.3%
- Published checkpoint SHA-256: `42cd5d9988f0830588b3be5107197c9b622c9b73426377975c07e8b24e346680`
- Bundled ONNX SHA-256: `87b73d4d635e9f5cf611021cbf6db1b1d7d4b1965b19fe383abaf0aee3617f09`

The bundled ONNX graph was re-exported from the published epoch-27 checkpoint in evaluation mode
with ONNX opset 17. This prevents training-mode batch-normalization behavior during inference.

The complete license text is included at `models/food101_LICENSE.txt`. The model is used only
for food-image suggestions. It does not estimate portions, diagnose disease, or replace manual
confirmation of the food and nutrient record.

## RapidOCR and OpenCV

- RapidOCR project: https://github.com/RapidAI/RapidOCR
- OpenCV project: https://opencv.org/
- Licenses: Apache License 2.0

These packages provide local text detection and recognition for laboratory-report images and scanned PDFs. OCR output is always unverified until a user compares it with the original report.
