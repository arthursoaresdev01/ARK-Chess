# pyrefly: ignore [missing-import]
from ultralytics import YOLO

model = YOLO("yolo11n-cls.pt")

model.train(
    data="dataset_final",
    epochs=20,
    imgsz=96
)