# FastObjects Fase 5 — Documentação bilíngue + higiene — Design Spec

**Data:** 2026-07-08
**Status:** Aprovado pelo usuário
**Base:** v0.3.0 no PyPI (SoA + dirty tracking; arena 328.213 sprites@60fps, 86x; 94 testes)
**Ordem acordada das próximas fases:** docs (esta) → hosts extras → texture atlas.

## Objetivo

A biblioteca está pública com números de ponta e API completa, mas sem
documentação navegável — o script de benchmark trazido pelo usuário registrou
literalmente "o README não documenta a API". Esta fase entrega README no padrão
das convenções, site de docs bilíngue no GitHub Pages, exemplos executáveis e a
task de higiene com os itens minor acumulados dos reviews.

**Critérios de aceite:**
- Site publicado em `https://enzo-azevedo.github.io/FastObjects` com seletor
  EN/PT funcionando e todos os exemplos copiáveis-e-executáveis.
- `README.md` (EN) com a tabela da arena no topo; `README.pt-BR.md` espelho;
  links cruzados entre os dois.
- Exemplos novos rodam da raiz do repo sem edição.
- Itens de higiene fechados; suíte inteira verde (94 + novos).
- Release **0.3.1** (leva o README novo ao PyPI; pipeline automático).

## Decisões (com alternativas rejeitadas)

- **Bilíngue via `mkdocs-static-i18n`** (suffix: `page.md` EN + `page.pt.md`
  PT, seletor no header). EN é o idioma principal/fallback. Rejeitado: dois
  sites separados (dobra config e quebra o seletor nativo do material).
- **Referência da API escrita à mão nas duas línguas.** As docstrings do
  código são PT; geração automática (mkdocstrings) misturaria PT no site EN.
  A API pública é pequena (Window, SpriteBatch, ShapeBatch, SpriteGroup,
  SurfaceLayer, attach/ExternalWindow, CapacityError) — mantê-la à mão é
  barato. Tradução dos docstrings do código: fora de escopo.
- **GitHub Pages via workflow** (`mkdocs build` + `actions/deploy-pages` em
  push na main). Habilitação do Pages tentada via REST API com a credencial
  do git (padrão das releases); se a API recusar, instrução manual ao usuário
  (Settings → Pages → Source: GitHub Actions). Rejeitado `mkdocs gh-deploy`
  local: publicação deve ser reprodutível por CI, não da máquina de dev.
- **Deps de docs em extra próprio** `[project.optional-dependencies] docs =
  ["mkdocs-material>=9", "mkdocs-static-i18n>=1"]` — core intocado.

## Componentes

### 1. READMEs

- `README.md` (EN — evolui o atual, preservando o quick start do usuário):
  1. Título + uma linha + **tabela da arena no topo** (328.213 @ 60fps, 86x;
     data + hardware + link para RESULTS.md) — convenção do projeto;
  2. Install + quick start (o atual, com nota `player.png`);
  3. "Why it's fast" CORRIGIDO: dirty tracking por coluna ("you pay for
     change, not existence"), 1 draw call instanciado, SoA — não mais
     "uploads the whole array";
  4. Seção "Use it inside pygame" (attach + despawn + SurfaceLayer, exemplo
     curto + link para examples/pygame_interop.py);
  5. Link para o site de docs + badge; link `Documentação em português →
     README.pt-BR.md` no topo.
- `README.pt-BR.md`: espelho fiel em PT, link `English → README.md` no topo.

### 2. Site mkdocs-material bilíngue

Estrutura (`mkdocs.yml` na raiz; conteúdo em `docs/site/` para não colidir com
`docs/superpowers/` — `docs_dir: docs/site`):

- `index.md` / `index.pt.md` — hero + tabela + mapa das seções.
- `getting-started.md` / `.pt.md` — install, primeiro programa (janela +
  sprites + input), execução.
- `guide/sprites.md` / `.pt.md` — SpriteBatch, spawn/despawn, SpriteGroup
  (views, slicing, invalidação), modelo de custos (pos sempre; frias quando
  tocadas; caveat de não guardar views entre frames).
- `guide/shapes.md` / `.pt.md` — ShapeBatch (rects/circles SDF/lines).
- `guide/window-input.md` / `.pt.md` — Window, frame loop, keys/mouse.
- `guide/interop.md` / `.pt.md` — pygame OPENGL, attach, SurfaceLayer,
  exemplo completo.
- `performance.md` / `.pt.md` — números (arena + benchmark_2d), filosofia
  "decidido por benchmark" (link RESULTS.md), dicas (batch por textura,
  vetorização).
- `api.md` / `.pt.md` — referência à mão: assinaturas, parâmetros, erros.
- Config: theme material (paleta clara/escura), plugin i18n (en default,
  pt), navegação por seções, repo_url.

Todo bloco de código deve rodar copiado-e-colado (convenção) — validado na
execução rodando cada exemplo dos docs.

### 3. Publicação — `.github/workflows/docs.yml`

- Trigger: push em `main` (paths: docs/site, mkdocs.yml, workflow) + manual.
- Jobs: checkout → setup-python → `pip install .[docs]` → `mkdocs build` →
  upload-pages-artifact → deploy-pages (permissions pages/id-token).
- Habilitar Pages: `POST /repos/Enzo-Azevedo/FastObjects/pages` com
  `{"build_type": "workflow"}` via token do credential helper; fallback:
  instrução manual.

### 4. Exemplos novos

- `examples/bunnymark.py` — modo nativo: 100k coelhos, física vetorizada,
  contador de FPS no título da janela, ESC sai; `--n` e `--frames` opcionais.
- `examples/shapes_input.py` — ShapeBatch + input: círculo segue o mouse,
  retângulos com setas, linhas decorativas; ESC sai; `--frames` opcional.
- Ambos referenciados nos docs e verificados com `--frames 120`.

### 5. Higiene (itens do ledger, um commit)

1. Pixel test de rotação de sprite (rot=π/2 em test_renderer — só shapes têm).
2. `run_all.py`: `--label` (anexado ao heading do RESULTS.md) e
   `timeout=600` no subprocess.run (bench travado não trava a arena).
3. Testes: caminho do asset `BUNNY` vira absoluto via `Path(__file__)`
   (suíte roda de qualquer cwd) — test_batch/test_group/test_despawn/test_dirty.
4. Fixture autouse (conftest.py) que salva/restaura a janela atual do
   `_context` — remove a fragilidade de ordenação dos testes.
5. Teste dedicado de `resolve()` com override parcial (ctx sem view_size e
   vice-versa).
6. Type hints: `Window.draw(*batches: Drawable)` (Protocol interno com
   `draw()`), `_context` anotando `Window | ExternalWindow` (TYPE_CHECKING).
7. Docstrings: nota de double-`attach` (chame uma vez por janela) em
   external.py; nota de thread-safety em `_context`; guard `ValueError`
   para surface (0, 0) no SurfaceLayer + teste.

### 6. Release 0.3.1

Bump nos 3 lugares + tag + pre-release GitHub via REST API + verificação
PyPI (workflow automático) — padrão das releases anteriores.

## Testes

- Higiene adiciona ~4 testes (rotação de sprite, resolve parcial, surface
  (0,0), label do run_all via testes puros de formatação se aplicável).
- `mkdocs build --strict` no CI e na execução (links quebrados falham).
- Exemplos rodados com `--frames 120` (janelas reais, foreground).

## Fora de escopo

Hosts pyglet/arcade/raylib e texture atlas (próximas fases, nesta ordem);
tradução de docstrings; mkdocstrings; renderização de texto; versionamento de
docs (mike) — quando houver 1.0.
