\# Tomato Disease Detection — Model Documentation



\## Project Overview

This module is part of the AgriSense graduation project. It uses deep learning to classify tomato leaf images and identify possible diseases.



\## Workflow

1\. Collect the original tomato leaf images.

2\. Inspect and prepare the dataset.

3\. Split the processed dataset for model development.

4\. Train the initial classification model.

5\. Fine-tune the model.

6\. Evaluate the trained models.

7\. Use the Streamlit application to make predictions.



\## Model Files

\- `Models/best\_model.pth` — Initial trained model.

\- `Models/best\_finetuned\_model.pth` — Fine-tuned model.

\- `Models/class\_names.json` — Class names used for classification.



\## Dataset

\- `Original\_Dataset/` — Documentation and download link for the original dataset.

\- `Processed\_Dataset/` — Prepared data used during model development.



\## Source Code

The `Scripts/` folder contains Python files for dataset inspection, preparation, training, evaluation, and prediction.



\## Important Notes

\- The original dataset is stored separately because of its large size.

\- Model accuracy and evaluation metrics should be reported using the actual saved results.

\- Model predictions are experimental and are not a guaranteed plant disease diagnosis.



\## Developer

Mohamed Tamer



AgriSense Graduation Project



