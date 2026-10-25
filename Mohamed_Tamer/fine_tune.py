
import torch
import torch.nn as nn
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader
from pathlib import Path
import json
import copy

DATA_PATH = Path("prepared_dataset")
BATCH_SIZE = 16
EPOCHS = 10

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Training on:", device)

if device.type != "cuda":
    raise RuntimeError("CUDA is not available")

train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
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

train_data = datasets.ImageFolder(
    DATA_PATH / "train", transform=train_transform
)

val_data = datasets.ImageFolder(
    DATA_PATH / "val", transform=val_transform
)

with open("models/class_names.json", "r") as f:
    class_names = json.load(f)

assert train_data.classes == val_data.classes == class_names

train_loader = DataLoader(
    train_data, batch_size=BATCH_SIZE, shuffle=True, num_workers=0
)

val_loader = DataLoader(
    val_data, batch_size=BATCH_SIZE, shuffle=False, num_workers=0
)

model = models.efficientnet_b0(weights=None)

model.classifier[1] = nn.Linear(
    model.classifier[1].in_features,
    len(class_names)
)

model.load_state_dict(
    torch.load(
        "models/best_model.pth",
        map_location="cpu",
        weights_only=True
    )
)

# Freeze all feature layers
for param in model.features.parameters():
    param.requires_grad = False

# Unfreeze last two feature blocks
for param in model.features[-2:].parameters():
    param.requires_grad = True

# Keep classifier trainable
for param in model.classifier.parameters():
    param.requires_grad = True

model = model.to(device)

criterion = nn.CrossEntropyLoss()

optimizer = torch.optim.Adam([
    {"params": model.features[-2:].parameters(), "lr": 0.00001},
    {"params": model.classifier.parameters(), "lr": 0.0001}
])

best_accuracy = -1
history = []

Path("models").mkdir(exist_ok=True)
Path("results").mkdir(exist_ok=True)

for epoch in range(EPOCHS):
    model.train()

    # Keep BatchNorm statistics frozen in feature blocks
    for module in model.features.modules():
        if isinstance(module, nn.BatchNorm2d):
            module.eval()

    train_correct = 0
    train_loss = 0

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

    model.eval()
    val_correct = 0
    val_loss = 0

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
        torch.save(
            model.state_dict(),
            "models/best_finetuned_model.pth"
        )
        print("Best fine-tuned model saved!", flush=True)

with open("results/finetuning_history.json", "w") as f:
    json.dump(history, f, indent=4)

print("\nFine-Tuning Completed!")
print(f"Best Validation Accuracy: {best_accuracy:.2f}%")
