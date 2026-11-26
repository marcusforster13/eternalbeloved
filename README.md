# Eternal Beloved

Chaveiro de coração atravessado por flecha, em 3D, publicado em **mofl.com.br/eternalbeloved**.

- `eternalbeloved/index.html`: a página (Three.js via CDN, sem build). Gira, aproxima e troca acabamento (rosa, PLA branco, cromo).
- `eternalbeloved/eternal-beloved-stl.zip`: o relicário em duas metades (abre ao meio, bolso de foto de 21 mm), o molde da foto em tamanho real, o chaveiro inteiro e as instruções de impressão.
- `ferramentas/relicario_blender.py`: no Blender, corta o chaveiro ao meio, abre o bolso da foto e os furos dos pinos.
- `ferramentas/relicario_imas.py`: versão atual (Blender headless): corta o chaveiro, abre o bolso da foto e os furos de 5,24 x 2,1 mm para ímãs 5 x 2 mm, e testa encaixe, fechar e abrir.
- `ferramentas/fatiar_p1s.py`: fatia as peças para a Bambu Lab P1S com o Bambu Studio instalado (um `.gcode.3mf` por cor).
- `ferramentas/gerar_stl.py`: gera o STL a partir da mesma equação do coração usada na página (`python ferramentas/gerar_stl.py`, só biblioteca padrão).

O site principal (projeto `mofl-site` na Vercel) serve esta página em `/eternalbeloved` por uma regra de rewrite para o deploy deste repositório.

No ar: https://mofl.com.br/eternalbeloved/
