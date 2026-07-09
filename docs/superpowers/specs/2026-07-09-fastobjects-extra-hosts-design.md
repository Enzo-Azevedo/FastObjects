# FastObjects — Hosts extras (pyglet / arcade / raylib) — Design Spec

**Data:** 2026-07-09
**Status:** Aprovado pelo usuário
**Base:** v0.3.1 no PyPI (docs bilíngue publicado; 98 testes; `fo.attach` genérico já entregue na fase de interop v0.2.0).
**Ordem das fases:** docs (feita) → **hosts extras (esta)** → texture atlas.

## Objetivo

O `fo.attach()` já conecta o FastObjects ao contexto OpenGL corrente de
qualquer host. Esta fase **valida empiricamente** quais bibliotecas-hospedeiras
além do pygame realmente cooperam — pyglet, arcade, raylib — e entrega, para
cada uma que funciona, um exemplo executável e documentação. Hosts que não
cooperam são documentados honestamente como não suportados, com o motivo
técnico.

**Filosofia:** fase exploratória, no espírito "decidido por evidência" do
projeto. Nenhuma API nova a menos que o spike prove necessário.

**Critérios de aceite:**
- Spike executado e registrado em `benchmarks/RESULTS.md` (status por host:
  verde / amarelo / vermelho + notas técnicas).
- Um `examples/<host>_interop.py` executável (com `--frames N` para auto-teste)
  para cada host verde/amarelo; nenhum para host vermelho.
- Seção "Other hosts" na página de interop das docs (EN/PT) com a tabela de
  status e um snippet por host suportado.
- Suíte inteira verde (sem regressão; testes novos só se um helper de
  isolamento for adicionado).
- Release **0.4.0** (tag + pre-release + PyPI).

## Componentes

### 1. Spike de validação — `benchmarks/lab/spike_hosts.py` (descartável)

Roteiro mínimo por host, um subprocesso cada (isolamento de contexto GL, como
a arena):

1. Criar a janela do host com contexto OpenGL, no idioma do host.
2. `fo.attach(view_size=(W, H))`.
3. `ShapeBatch` desenhando um retângulo de cor conhecida em posição conhecida,
   por ~30 frames, sobre um fundo limpo do host.
4. Ler o pixel do centro do retângulo (via `ctx.screen.read` ou FBO) e comparar
   com a cor esperada; imprimir `HOST verde|amarelo|vermelho: <nota>`.

Três resultados possíveis por host:
- **verde** — attach cru basta (pixel correto sem intervenção) → vira exemplo
  direto.
- **amarelo** — o retângulo só aparece correto se salvar/restaurar o estado GL
  que o FastObjects toca (blend/program/VAO) em volta do `batch.draw()` →
  registrar exatamente o que precisou.
- **vermelho** — o host não expõe um contexto GL que o moderngl consiga adotar,
  ou o estado (ex.: rlgl do raylib) corrompe irremediavelmente o render → não
  suportado.

Hipóteses de entrada (a confirmar pelo spike, não assumir):
- pyglet: nativamente OpenGL → provável **verde**.
- arcade: tem o próprio contexto moderngl → provável **amarelo** (isolamento).
- raylib: rlgl com batching e estado próprios → provável **vermelho**.

O resultado do spike decide os itens 2–4. O script é lab (descartável), não
entra na suíte.

### 2. Isolamento de estado GL — SÓ se o spike pedir

Se algum host **amarelo** exigir, adicionar um helper mínimo em
`fastobjects/external.py`:

```python
class ExternalWindow:
    @contextmanager
    def isolated(self):
        """Salva/restaura o estado GL que o FastObjects toca (blend, program,
        VAO), para conviver com hosts que gerenciam o próprio estado."""
```

- Implementado com `glGetIntegerv`/`glIsEnabled` do estado relevante e
  restauração no `finally` (via `ctx` do moderngl ou `moderngl`/`OpenGL` já
  disponíveis). Escopo exato definido pelo spike (só o que de fato importar).
- Testável offscreen: dentro do context manager mudar blend/program, sair, e
  verificar que voltou ao valor anterior (novo teste em `tests/test_external.py`).
- **Se nenhum host amarelo precisar, este componente não é criado** (YAGNI).
  A decisão fica registrada no spec de execução / RESULTS.md.

### 3. Exemplos por host — um por host verde/amarelo

- `examples/pyglet_interop.py` — `pyglet.window.Window` (OpenGL nativo),
  `pyglet.app.run`/`on_draw` OU loop manual; `fo.attach`; sprites+shapes do
  FastObjects sobre um `pyglet.text.Label` ou shape nativo; input do pyglet.
- `examples/arcade_interop.py` — `arcade.Window` + `on_draw`; FastObjects
  desenhando dentro do `on_draw` (com `ext.isolated()` se o spike exigir);
  algo nativo do arcade coexistindo.
- `examples/raylib_interop.py` — **só se o raylib não for vermelho**:
  `while not rl.window_should_close()`, `rl.begin_drawing()`/`end_drawing()`,
  FastObjects entre eles.
- Padrão dos exemplos atuais: docstring com instruções, `--frames N` para
  rodada não-interativa imprimindo `<host> ok: <frames> frames`, ESC/fechar
  sai, asset via `Path(__file__)`.

### 4. Documentação — página de interop (EN/PT)

Nova seção **"Other hosts"** em `docs/site/guide/interop.md` e `.pt.md`:
- Tabela host × status: pygame (documentado), pyglet, arcade, raylib —
  "supported" / "supported with `ext.isolated()`" / "not supported (reason)".
- Um snippet mínimo por host suportado (criar janela do host → `attach` →
  draw).
- Nota geral: `attach` funciona com qualquer contexto GL corrente; para hosts
  que gerenciam estado próprio, envolver os draws do FastObjects em
  `ext.isolated()`.
- Se `ext.isolated()` for criado, documentá-lo também na página de API.

### 5. Dependências

pyglet, arcade e raylib já estão no extra `[bench]` do `pyproject.toml`
(pyglet vem via arcade). Nada muda no core; os exemplos assumem
`pip install fastobjects[bench]` ou a lib do host instalada — documentado no
topo de cada exemplo.

### 6. Release 0.4.0

Bump nos 3 lugares + tag `v0.4.0` + pre-release GitHub via REST API (sem gh
CLI — token do git credential, padrão registrado na memória do projeto) +
verificação do publish.yml e do PyPI. Docs republicam pelo workflow.

## Tratamento de erros

Sem novas classes de erro. Se `ext.isolated()` for adicionado, ele não levanta
nada próprio — apenas restaura estado. O erro de attach sem contexto GL já é
acionável.

## Testes

- Spike: script lab, verificação por execução (não entra na suíte).
- Se `ext.isolated()` existir: teste offscreen de save/restore de estado.
- Exemplos: rodados com `--frames 120` em foreground (janelas reais).
- Suíte completa + ruff verdes antes de cada commit.

## Fora de escopo

- Texture atlas (próxima fase).
- Hosts além dos três nomeados.
- Qualquer solução que exija fork/patch de uma biblioteca-hospedeira.
- Backend não-OpenGL.

## Decisões (com alternativas rejeitadas)

- **Spike-first, enviar o que funcionar.** Rejeitado comprometer com os 3 a
  qualquer custo (engenharia frágil dependente de internals) e rejeitado só
  pyglet (entrega menos que o pedido). Evidência decide.
- **Isolamento decidido após o spike.** Rejeitado projetar o context manager
  antecipadamente (YAGNI: pyglet provavelmente não precisa).
- **raylib provavelmente não suportado.** Se vermelho, documentado como tal
  com o motivo (rlgl), em vez de forçar — decisão já validada com o usuário.
- **Exemplos, não módulos de código por host.** Mantém `attach` genérico; cada
  host é exemplo + doc, não caso especial no pacote (mesma decisão da fase de
  interop).
