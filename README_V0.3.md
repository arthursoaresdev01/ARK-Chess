# ARK CoC v0.3

Ferramenta de anotação rápida para criar um dataset moderno de CV18.

## Fluxo

```powershell
python annotation\preannotate.py --image base.png
python annotation\annotator.py --image datasets\cv18_manual\images\base.png
python annotation\build_dataset.py
python annotation\train_cv18.py --epochs 60 --batch 4
python main.py --image base.png --model models\ark_coc_cv18.pt --army ranked_adaptive --show
```

Controles do anotador: mouse esquerdo desenha; direito apaga; U desfaz; S salva; ESC sai; 0-9 selecionam classes 0-9; Q/W/E/R/T selecionam classes 10-14.
