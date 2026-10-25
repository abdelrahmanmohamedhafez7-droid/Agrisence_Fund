from pathlib import Path
from PIL import Image
import pandas as pd

dataset = Path("data set/tomato-dataset")

extensions = {".jpg", ".jpeg", ".png", ".webp"}
results = []

for split in ["train", "val"]:
    folder = dataset / split

    for disease in sorted(folder.iterdir()):
        if not disease.is_dir():
            continue

        images = [
            file for file in disease.rglob("*")
            if file.suffix.lower() in extensions
        ]

        results.append({
            "Split": split,
            "Disease": disease.name,
            "Images": len(images)
        })

df = pd.DataFrame(results)

print("\nDataset Information:")
print(df.to_string(index=False))

print("\nTotal Images:", df["Images"].sum())
print("Number of Classes:", df["Disease"].nunique())

print("\nChecking Images...")

corrupted = []

for split in ["train", "val"]:
    folder = dataset / split

    for file in folder.rglob("*"):
        if file.suffix.lower() in extensions:
            try:
                with Image.open(file) as img:
                    img.verify()
            except Exception:
                corrupted.append(str(file))

print("Corrupted Images:", len(corrupted))

for file in corrupted[:10]:
    print(file)