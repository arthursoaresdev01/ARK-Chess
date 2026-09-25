# ARK CoC v0.2 — visão real com dataset público

Agora o projeto já tem o pipeline para baixar automaticamente um dataset público de Clash of Clans, converter as anotações COCO para YOLO, treinar um modelo e instalar o `best.pt` como `models/ark_coc.pt`.

O dataset público citado no projeto vem de `keremberke/clash-of-clans-object-detection` no Hugging Face. Ele é pequeno (~125 imagens), então serve como **baseline**, não como detector final de CV18.

## 1) instalar dependências

No PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 2) baixar e preparar o dataset

```powershell
python training\download_public_dataset.py
```

O script:
- baixa train/valid/test;
- acha automaticamente o JSON COCO;
- copia as imagens;
- converte os bounding boxes para YOLO;
- cria `datasets/coc_public/dataset.yaml`;
- imprime todas as classes reais que encontrou.

## 3) treinar

Primeiro tente:

```powershell
python training\train_public_model.py --epochs 80 --batch 8
```

Se faltar memória:

```powershell
python training\train_public_model.py --epochs 60 --batch 4
```

Se estiver usando somente CPU, o treino pode demorar bastante. Para um teste rápido:

```powershell
python training\train_public_model.py --epochs 15 --batch 4 --device cpu
```

Ao terminar, o script copia automaticamente:

```text
runs_arkcoc/.../weights/best.pt
```

para:

```text
models/ark_coc.pt
```

## 4) testar o detector puro

```powershell
python training\test_detector.py --image base.png
```

## 5) testar o cérebro completo

```powershell
python main.py --image base.png --army ranked_adaptive --show
```

Se `models/ark_coc.pt` existir, o `VisionEngine` muda automaticamente de:

```text
generic_cv
```

para:

```text
custom_yolo
```

## O que muda na prática

Antes:
```text
imagem -> regiões genéricas -> geometria -> entrada
```

Agora:
```text
imagem -> YOLO de CoC -> construções reais -> pesos de ameaça -> entrada/funil/core
```

## Limitação importante

O dataset público é antigo/pequeno e não terá necessariamente todas as construções modernas do CV18. O objetivo dele é nos dar **um modelo inicial funcional sem você precisar anotar tudo do zero**.

Depois usamos esse modelo para pré-anotar screenshots modernas e você só corrige as caixas. Isso é muito mais rápido do que começar manualmente.

## Roadmap imediato

1. treinar o baseline público;
2. testar na sua `base.png`;
3. ver quais classes ele reconhece e quais erra;
4. montar dataset CV18 incremental;
5. adicionar Monólito, Dispersores, Torres de Feitiço e defesas modernas;
6. gerar threat map real;
7. melhorar pathing e escolha de entrada para ranked.
