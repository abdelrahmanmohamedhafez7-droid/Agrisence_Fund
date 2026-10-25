
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from pathlib import Path
import json

# Settings
DATA_PATH = Path("prepared_dataset")
BATCH_SIZE = 16
EPOCHS = 10
LEARNING_RATE = 0.001

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Training on:", device)

if device.type != "cuda":
    raise RuntimeError("CUDA is not available. Check PyTorch GPU installation.")

# Image preprocessing
train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ToTensor(),
    transforms.Normalize(
        [0.485, 0.456, 0.406],
        [0.229, 0.224, 0.225]
    )
])

val_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        [0.485, 0.456, 0.406],
        [0.229, 0.224, 0.225]
    )
])

# Load dataset
train_data = datasets.ImageFolder(
    DATA_PATH / "train", transform=train_transform
)

val_data = datasets.ImageFolder(
    DATA_PATH / "val", transform=val_transform
)

assert train_data.classes == val_data.classes

train_loader = DataLoader(
    train_data, batch_size=BATCH_SIZE, shuffle=True, num_workers=0
)

val_loader = DataLoader(
    val_data, batch_size=BATCH_SIZE, shuffle=False, num_workers=0
)

print("Classes:", len(train_data.classes))
print("Training images:", len(train_data))
print("Validation images:", len(val_data))

# Load pretrained EfficientNetB0
weights = models.EfficientNet_B0_Weights.DEFAULT
model = models.efficientnet_b0(weights=weights)

# Freeze pretrained layers
for param in model.features.parameters():
    param.requires_grad = False

# Replace classification layer
model.classifier[1] = nn.Linear(
    model.classifier[1].in_features,
    len(train_data.classes)
)

model = model.to(device)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(
    model.classifier.parameters(),
    lr=LEARNING_RATE
)

Path("models").mkdir(exist_ok=True)
Path("results").mkdir(exist_ok=True)

with open("models/class_names.json", "w") as f:
    json.dump(train_data.classes, f, indent=4)

best_accuracy = 0.0
history = []

# Training loop
for epoch in range(EPOCHS):
    model.train()
    train_correct = 0
    train_loss = 0.0

    for images, labels in train_loader:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)

        loss.backward()
        optimizer.step()

        train_loss += loss.item() * images.size(0)
        train_correct += (outputs.argmax(1) == labels).sum().item()

    train_acc = 100 * train_correct / len(train_data)
    train_loss /= len(train_data)

    # Validation
    model.eval()
    val_correct = 0
    val_loss = 0.0

    with torch.no_grad():
        for images, labels in val_loader:
            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels)

            val_loss += loss.item() * images.size(0)
            val_correct += (outputs.argmax(1) == labels).sum().item()

    val_acc = 100 * val_correct / len(val_data)
    val_loss /= len(val_data)

    history.append({
        "epoch": epoch + 1,
        "train_accuracy": train_acc,
        "validation_accuracy": val_acc,
        "train_loss": train_loss,
        "validation_loss": val_loss
    })

    print(
        f"Epoch {epoch+1}/{EPOCHS} | "
        f"Train Acc: {train_acc:.2f}% | "
        f"Val Acc: {val_acc:.2f}% | "
        f"Train Loss: {train_loss:.4f} | "
        f"Val Loss: {val_loss:.4f}",
        flush=True
    )

    if val_acc > best_accuracy:
        best_accuracy = val_acc
        torch.save(model.state_dict(), "models/best_model.pth")
        print("Best model saved!", flush=True)

with open("results/training_history.json", "w") as f:
    json.dump(history, f, indent=4)

print("\nTraining completed!")
print(f"Best Validation Accuracy: {best_accuracy:.2f}%")
