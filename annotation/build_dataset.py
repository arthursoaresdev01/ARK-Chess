from pathlib import Path
import json,yaml,shutil,random
def main():
    base=Path('datasets/cv18_manual'); images=base/'images'; labels=base/'labels'; classes=json.loads(Path('annotation/classes.json').read_text(encoding='utf-8'))
    imgs=[p for p in images.iterdir() if p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}]
    if len(imgs)<2: raise SystemExit('Adicione pelo menos 2 imagens anotadas.')
    random.seed(42); random.shuffle(imgs); n=len(imgs); cut=max(1,int(n*.8)); train=imgs[:cut]; val=imgs[cut:] or imgs[-1:]
    out=Path('datasets/cv18_yolo');
    if out.exists(): shutil.rmtree(out)
    for split,items in [('train',train),('val',val)]:
        (out/split/'images').mkdir(parents=True,exist_ok=True); (out/split/'labels').mkdir(parents=True,exist_ok=True)
        for img in items:
            shutil.copy2(img,out/split/'images'/img.name); lbl=labels/f'{img.stem}.txt'
            shutil.copy2(lbl,out/split/'labels'/lbl.name) if lbl.exists() else (out/split/'labels'/f'{img.stem}.txt').write_text('',encoding='utf-8')
    data={'path':str(out.resolve()).replace('\\','/'),'train':'train/images','val':'val/images','names':{i:n for i,n in enumerate(classes)}}
    (out/'dataset.yaml').write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True),encoding='utf-8'); print(f'[OK] {out/"dataset.yaml"} | train={len(train)} val={len(val)}')
if __name__=='__main__': main()
