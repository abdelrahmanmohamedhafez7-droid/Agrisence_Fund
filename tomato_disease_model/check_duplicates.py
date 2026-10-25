from pathlib import Path
import hashlib

dataset = Path("data set/tomato-dataset")

def get_hashes(split):
    hashes = set()

    for file in (dataset / split).rglob("*"):
        if file.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            with open(file, "rb") as f:
                image_hash = hashlib.md5(f.read()).hexdigest()
                hashes.add(image_hash)

    return hashes

train_hashes = get_hashes("train")
val_hashes = get_hashes("val")

duplicates = train_hashes.intersection(val_hashes)

print("Train Unique Images:", len(train_hashes))
print("Validation Unique Images:", len(val_hashes))
print("Duplicate Images:", len(duplicates))