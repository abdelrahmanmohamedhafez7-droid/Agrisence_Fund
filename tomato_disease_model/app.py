
import streamlit as st
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import json

st.set_page_config(
    page_title="Tomato Disease Detection",
    page_icon="🍅",
    layout="centered"
)

@st.cache_resource
def load_model():
    with open("models/class_names.json", "r") as f:
        class_names = json.load(f)

    model = models.efficientnet_b0(weights=None)

    model.classifier[1] = nn.Linear(
        model.classifier[1].in_features,
        len(class_names)
    )

    model.load_state_dict(
        torch.load(
            "models/best_finetuned_model.pth",
            map_location="cpu",
            weights_only=True
        )
    )

    model.eval()
    return model, class_names


model, class_names = load_model()

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        [0.485, 0.456, 0.406],
        [0.229, 0.224, 0.225]
    )
])

st.title("🍅 Tomato Disease Detection")
st.write("AI-Based Tomato Leaf Disease Classification")

st.info("Upload a tomato leaf image to predict its disease.")

uploaded_file = st.file_uploader(
    "Choose an image",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")

    st.image(image, caption="Uploaded Image", use_container_width=True)

    if st.button("Predict Disease", type="primary"):
        image_tensor = transform(image).unsqueeze(0)

        with torch.inference_mode():
            outputs = model(image_tensor)
            probabilities = torch.softmax(outputs, dim=1)[0]

        confidence, predicted_index = torch.max(
            probabilities, dim=0
        )

        disease = class_names[predicted_index.item()]
        disease = disease.replace("Tomato___", "").replace("_", " ")

        st.success(f"Predicted Disease: {disease}")
        st.metric("Model Confidence", f"{confidence.item() * 100:.2f}%")

        st.subheader("Top 3 Predictions")

        top_probs, top_indices = torch.topk(probabilities, 3)

        for prob, index in zip(top_probs, top_indices):
            name = class_names[index.item()]
            name = name.replace("Tomato___", "").replace("_", " ")

            st.write(f"{name}: {prob.item() * 100:.2f}%")
            st.progress(float(prob.item()))

        st.caption(
            "Predictions are experimental. Confidence is not a "
            "guarantee of correctness. This model was trained "
            "for tomato leaf classification only."
        )
