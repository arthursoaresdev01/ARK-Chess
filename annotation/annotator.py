from pathlib import Path
import argparse, json, cv2
WINDOW='ARK CoC Annotator'
class Annotator:
    def __init__(self,image_path,classes,out_labels):
        self.image_path=image_path; self.image=cv2.imread(str(image_path))
        if self.image is None: raise SystemExit(f'Não consegui abrir {image_path}')
        self.classes=classes; self.out_labels=out_labels; self.boxes=[]; self.current_class=0
        self.dragging=False; self.start=None; self.preview=None; self.load_existing()
    def load_existing(self):
        if not self.out_labels.exists(): return
        h,w=self.image.shape[:2]
        for line in self.out_labels.read_text(encoding='utf-8').splitlines():
            p=line.split()
            if len(p)!=5: continue
            cls,cx,cy,bw,bh=map(float,p); cls=int(cls)
            x1=int((cx-bw/2)*w); y1=int((cy-bh/2)*h); x2=int((cx+bw/2)*w); y2=int((cy+bh/2)*h)
            self.boxes.append([cls,x1,y1,x2,y2])
    def mouse(self,event,x,y,flags,param):
        if event==cv2.EVENT_LBUTTONDOWN:
            self.dragging=True; self.start=(x,y); self.preview=(x,y,x,y)
        elif event==cv2.EVENT_MOUSEMOVE and self.dragging:
            self.preview=(self.start[0],self.start[1],x,y)
        elif event==cv2.EVENT_LBUTTONUP and self.dragging:
            self.dragging=False; x1,y1=self.start; x2,y2=x,y; xa,xb=sorted([x1,x2]); ya,yb=sorted([y1,y2])
            if xb-xa>4 and yb-ya>4: self.boxes.append([self.current_class,xa,ya,xb,yb])
            self.preview=None
        elif event==cv2.EVENT_RBUTTONDOWN:
            hits=[]
            for i,(cls,x1,y1,x2,y2) in enumerate(self.boxes):
                if x1<=x<=x2 and y1<=y<=y2: hits.append(((x2-x1)*(y2-y1),i))
            if hits: self.boxes.pop(min(hits)[1])
    def draw(self):
        out=self.image.copy()
        for i,(cls,x1,y1,x2,y2) in enumerate(self.boxes):
            cv2.rectangle(out,(x1,y1),(x2,y2),(255,255,255),2)
            cv2.putText(out,f'{i+1}:{self.classes[cls]}',(x1,max(16,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,255,255),1,cv2.LINE_AA)
        if self.preview:
            x1,y1,x2,y2=self.preview; cv2.rectangle(out,(x1,y1),(x2,y2),(200,200,200),1)
        hud=[f'Classe [{self.current_class}]: {self.classes[self.current_class]}','0-9=classes 0-9 | Q,W,E,R,T=10-14','Mouse esq=desenhar | dir=apagar','U=desfazer | S=salvar | ESC=sair']
        y=20
        for line in hud:
            cv2.putText(out,line,(10,y),cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,255,255),1,cv2.LINE_AA); y+=20
        return out
    def save(self):
        h,w=self.image.shape[:2]; lines=[]
        for cls,x1,y1,x2,y2 in self.boxes:
            cx=((x1+x2)/2)/w; cy=((y1+y2)/2)/h; bw=(x2-x1)/w; bh=(y2-y1)/h
            lines.append(f'{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}')
        self.out_labels.parent.mkdir(parents=True,exist_ok=True); self.out_labels.write_text('\n'.join(lines),encoding='utf-8')
        print(f'[SALVO] {self.out_labels} ({len(self.boxes)} caixas)')
    def run(self):
        cv2.namedWindow(WINDOW,cv2.WINDOW_NORMAL); cv2.setMouseCallback(WINDOW,self.mouse)
        keymap={ord(str(i)):i for i in range(10)}; keymap.update({ord('q'):10,ord('w'):11,ord('e'):12,ord('r'):13,ord('t'):14})
        while True:
            cv2.imshow(WINDOW,self.draw()); key=cv2.waitKey(20)&0xFF
            if key==27: break
            elif key in keymap and keymap[key]<len(self.classes): self.current_class=keymap[key]
            elif key in (ord('u'),ord('U')) and self.boxes: self.boxes.pop()
            elif key in (ord('s'),ord('S')): self.save()
        cv2.destroyAllWindows()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--image',required=True); ap.add_argument('--classes',default='annotation/classes.json'); ap.add_argument('--labels-dir',default='datasets/cv18_manual/labels'); args=ap.parse_args()
    image_path=Path(args.image); classes=json.loads(Path(args.classes).read_text(encoding='utf-8')); out=Path(args.labels_dir)/f'{image_path.stem}.txt'; Annotator(image_path,classes,out).run()
if __name__=='__main__': main()
