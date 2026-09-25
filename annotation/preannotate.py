from pathlib import Path
import argparse, shutil, json, cv2
from ultralytics import YOLO
ALIASES={'townhall':'town_hall','th':'town_hall','inferno':'inferno_tower','xbow':'x_bow','x_bow':'x_bow','ad':'air_defense','clancastle':'clan_castle'}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--image',required=True); ap.add_argument('--model',default='models/ark_coc.pt'); ap.add_argument('--conf',type=float,default=0.45); ap.add_argument('--classes',default='annotation/classes.json'); ap.add_argument('--images-dir',default='datasets/cv18_manual/images'); ap.add_argument('--labels-dir',default='datasets/cv18_manual/labels'); args=ap.parse_args()
    image_path=Path(args.image); classes=json.loads(Path(args.classes).read_text(encoding='utf-8')); class_to_id={n:i for i,n in enumerate(classes)}
    out_img_dir=Path(args.images_dir); out_lbl_dir=Path(args.labels_dir); out_img_dir.mkdir(parents=True,exist_ok=True); out_lbl_dir.mkdir(parents=True,exist_ok=True)
    dst=out_img_dir/image_path.name; shutil.copy2(image_path,dst)
    model=YOLO(args.model); result=model(str(image_path),conf=args.conf,verbose=False)[0]; img=cv2.imread(str(image_path)); h,w=img.shape[:2]
    lines=[]; kept=0
    if result.boxes is not None:
        for b in result.boxes:
            raw=str(result.names[int(b.cls[0])]).lower().strip().replace(' ','').replace('-',''); mapped=ALIASES.get(raw)
            if not mapped or mapped not in class_to_id: continue
            x1,y1,x2,y2=map(float,b.xyxy[0].tolist()); cx=((x1+x2)/2)/w; cy=((y1+y2)/2)/h; bw=(x2-x1)/w; bh=(y2-y1)/h
            lines.append(f'{class_to_id[mapped]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}'); kept+=1
    lp=out_lbl_dir/f'{image_path.stem}.txt'; lp.write_text('\n'.join(lines),encoding='utf-8')
    print(f'[OK] Imagem: {dst}'); print(f'[OK] Pré-anotações úteis: {kept}'); print(f'[OK] Label: {lp}'); print(f'Agora: python annotation\\annotator.py --image "{dst}"')
if __name__=='__main__': main()
