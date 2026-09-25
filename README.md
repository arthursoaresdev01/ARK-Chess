# ARK Chess ♟️

ARK Chess é um projeto em Python que criei para reconhecer um tabuleiro de xadrez pela tela e sugerir a melhor jogada usando o Stockfish.

## O que ele faz

- Captura o tabuleiro automaticamente
- Reconhece as peças usando YOLO
- Monta a posição do jogo
- Detecta as jogadas feitas
- Valida as jogadas com python-chess
- Usa Stockfish para encontrar a melhor jogada
- Mostra a jogada na tela através de um overlay
- Possui sistema de recuperação caso perca a sincronização
- Possui Auto Play experimental para testes contra bots

## Tecnologias

- Python
- OpenCV
- YOLO
- python-chess
- Stockfish
- PySide6
- PyInstaller

## Como executar

Instale as dependências:

```bash
pip install opencv-python mss numpy python-chess ultralytics PySide6
```

Depois execute:

```bash
python ark_front_v7_guard.py
```

Também é necessário ter o Stockfish e o modelo YOLO configurados no projeto.

## Status

O projeto ainda está em desenvolvimento. Algumas situações de reconhecimento e sincronização ainda podem apresentar erros.

## Autor

Arthur Soares  
GitHub: `arthursoaresdev01`
