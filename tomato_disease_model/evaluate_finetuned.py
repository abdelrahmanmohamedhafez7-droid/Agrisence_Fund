
import torch
import torch.nn as nn
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import matplotlib.pyplot as plt
import numpy as np
import json
from pathlib import Path

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

test_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        [0.485, 0.456, 0.406],
        [0.229, 0.224, 0.225]
    )
])

test_data = datasets.ImageFolder(
    "prepared_dataset/test",
    transform=test_transform
)

test_loader = DataLoader(
    test_data,
    batch_size=16,
    shuffle=False,
    num_workers=0
)

with open("models/class_names.json", "r") as f:
    class_names = json.load(f)

assert test_data.classes == class_names, "Class names do not match!"

model = models.efficientnet_b0(weights=None)

model.classifier[1] = nn.Linear(
    model.classifier[1].in_features,
    len(class_names)
)

model.load_state_dict(
    torch.load("models/best_finetuned_model.pth", map_location=device, weights_only=True)
)

model = model.to(device)
model.eval()

true_labels = []
predicted_labels = []

with torch.no_grad():
    for images, labels in test_loader:
        images = images.to(device)

        outputs = model(images)
        predictions = outputs.argmax(dim=1)

        true_labels.extend(labels.numpy())
        predicted_labels.extend(predictions.cpu().numpy())

accuracy = accuracy_score(true_labels, predicted_labels)

print(f"\nTest Accuracy: {accuracy * 100:.2f}%")

report = classification_report(
    true_labels,
    predicted_labels,
    labels=list(range(len(class_names))),
    target_names=class_names,
    zero_division=0
)

print("\nClassification Report:\n")
print(report)

Path("results").mkdir(exist_ok=True)

with open("results/finetuned_classification_report.txt", "w") as f:
    f.write(f"Test Accuracy: {accuracy * 100:.2f}%\n\n")
    f.write(report)

cm = confusion_matrix(
    true_labels,
    predicted_labels,
    labels=list(range(len(class_names)))
)

fig, ax = plt.subplots(figsize=(12, 10))
im = ax.imshow(cm, cmap="Blues")
fig.colorbar(im, ax=ax)

ax.set_xticks(np.arange(len(class_names)))
ax.set_yticks(np.arange(len(class_names)))

ax.set_xticklabels(class_names, rotation=90)
ax.set_yticklabels(class_names)

ax.set_xlabel("Predicted Label")
ax.set_ylabel("True Label")
ax.set_title("Tomato Disease Confusion Matrix")

for i in range(len(class_names)):
    for j in range(len(class_names)):
        ax.text(j, i, str(cm[i, j]),
                ha="center", va="center", fontsize=8)

plt.tight_layout()
plt.savefig("results/finetuned_confusion_matrix.png", dpi=200)
plt.show()

print("\nEvaluation completed!")
