# ARK CoC — Prototype v0.1

Protótipo de **copiloto tático para Clash of Clans**, feito em Python.

Ele NÃO clica no jogo e NÃO executa ataques automaticamente. O objetivo é:
1. ler uma screenshot;
2. delimitar a área jogável;
3. detectar construções quando houver um YOLO CoC treinado;
4. enquanto o modelo ainda não existe, usar candidatos geométricos;
5. avaliar 16 ângulos de entrada;
6. estimar layout, core, funil e rota;
7. salvar uma imagem anotada e um JSON com o plano.

## Estrutura

```text
ARK_CoC_Prototype/
├─ main.py
├─ requirements.txt
├─ base_exemplo.png
├─ arkcoc/
│  ├─ geometry.py
│  ├─ vision.py
│  ├─ tactics.py
│  ├─ overlay.py
│  ├─ models.py
│  └─ io_utils.py
├─ data/
│  └─ knowledge_2026_09.json
├─ models/
│  └─ ark_coc.pt   <- entra aqui no futuro
└─ saida/
```

## Instalação

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Rodar com sua base

Coloque a screenshot como `base.png` e rode:

```powershell
python main.py --image base.png --army ranked_adaptive --show
```

Ou use a imagem de exemplo:

```powershell
python main.py --image base_exemplo.png --army ranked_adaptive --show
```

Outros perfis:

```powershell
python main.py --image base.png --army dragons --show
python main.py --image base.png --army cyclopes_healers --show
python main.py --image base.png --army ground_smash --show
```

## O que já funciona

- máscara geométrica da área jogável;
- detector fallback por OpenCV;
- suporte pronto para `models/ark_coc.pt`;
- mapa de objetos;
- core ponderado;
- classificação básica do layout;
- 16 candidatos de entrada;
- pontuação de densidade, acesso ao core, risco e funil;
- recomendação de entrada;
- pontos de funil A/B;
- rota até o core;
- overlay visual;
- `saida/analise.png`;
- `saida/plano.json`.

## Limitação principal atual

Sem um **YOLO treinado especificamente em construções do CoC**, o programa não sabe se um objeto é CV, Inferno, Monólito etc.

O fallback atual encontra apenas regiões visualmente densas. Por isso a arquitetura está pronta, mas a inteligência estratégica ainda trabalha com informação incompleta.

A melhoria que mais aumenta a qualidade agora é o dataset/modelo `ark_coc.pt`.

## Próxima evolução planejada

### V0.2 — detector real
Treinar YOLO com classes prioritárias de defesas e CV.

### V0.3 — threat map
Usar classe, alcance, prioridade e sinergias das defesas para criar um mapa de risco.

### V0.4 — pathing
Criar grafo de construções/compartimentos e simular caminhos prováveis do exército.

### V0.5 — ranked
Ler a base quando ela aparece e, dado um exército já escolhido, recomendar entrada e execução.

### V0.6 — aprendizado pós-ataque
Registrar previsão vs. resultado para calibrar pesos do sistema.
