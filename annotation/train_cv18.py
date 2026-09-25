from pathlib import Path
import argparse,shutil
from ultralytics import YOLO
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base-model',default='models/ark_coc.pt'); ap.add_argument('--epochs',type=int,default=60); ap.add_argument('--batch',type=int,default=4); ap.add_argument('--imgsz',type=int,default=768); ap.add_argument('--device',default=None); args=ap.parse_args()
    data=Path('datasets/cv18_yolo/dataset.yaml')
    if not data.exists(): raise SystemExit('Rode: python annotation\\build_dataset.py')
    model=YOLO(args.base_model if Path(args.base_model).exists() else 'yolo11n.pt'); kwargs=dict(data=str(data),epochs=args.epochs,batch=args.batch,imgsz=args.imgsz,project='runs_arkcoc',name='cv18_v1',patience=15,workers=2,pretrained=True)
    if args.device: kwargs['device']=args.device
    results=model.train(**kwargs); best=Path(results.save_dir)/'weights'/'best.pt'; dst=Path('models')/'ark_coc_cv18.pt'; shutil.copy2(best,dst); print(f'[OK] Modelo CV18: {dst}')
if __name__=='__main__': main()
