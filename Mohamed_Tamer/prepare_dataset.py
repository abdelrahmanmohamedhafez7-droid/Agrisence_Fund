from pathlib import Path
import random
import shutil

random.seed(42)

source = Path("data set/tomato-dataset")
destination = Path("prepared_dataset")

extensions = {".jpg", ".jpeg", ".png", ".webp"}

if destination.exists():
    raise SystemExit("prepared_dataset already exists. No files changed.")

for class_folder in sorted((source / "train").iterdir()):
    if not class_folder.is_dir():
        continue

    images = [
        f for f in class_folder.iterdir()
        if f.suffix.lower() in extensions
    ]

    random.shuffle(images)

    split_index = int(len(images) * 0.9)

    train_images = images[:split_index]
    val_images = images[split_index:]

    for split, files in [
        ("train", train_images),
        ("val", val_images)
    ]:
        target = destination / split / class_folder.name
        target.mkdir(parents=True, exist_ok=True)

        for image in files:
            shutil.copy2(image, target / image.name)

    print(class_folder.name, len(train_images), len(val_images))

# Original validation becomes the final test set
shutil.copytree(source / "val", destination / "test")

print("\nDataset preparation completed!")