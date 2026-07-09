# Pesquisa: como os concorrentes renderizam (e onde perdem tempo)

**Data:** 2026-07-06  |  **Versões:** arcade 3.3.3, pyglet 2.1.15, moderngl 5.12.0

## 1. arcade: onde está o custo por sprite?

Caminho do dado desde `sprite.position = ...` até a GPU (arcade 3.3.3):

1. `Sprite.position` setter (`arcade/sprite/base.py`, ~linha 100): compara com o valor
   antigo, atualiza `self._position`, atualiza `self._hit_box.position`, chama
   `self.update_spatial_hash()` e então, **para cada SpriteList que contém o sprite**,
   chama `sprite_list._update_position(self)`.
2. `SpriteList._update_position` (`arcade/sprite_list/sprite_list.py:1132`): faz um
   lookup em dict (`self.sprite_slot[sprite]`) e escreve 2 floats em um array Python
   (`self._sprite_pos_angle_data[slot * 4]` e `[slot * 4 + 1]`), marcando
   `self._sprite_pos_angle_changed = True`.
3. `SpriteList.draw()` (`sprite_list.py:956`) chama `_write_sprite_buffers_to_gpu()`
   (`sprite_list.py:916`), que sobe os arrays inteiros que mudaram (pos/angle, size,
   color, texture, index) para os buffers GL e depois faz um draw da lista.

O lado GPU do arcade já é bom (um draw por SpriteList, dados em buffers). O custo está
no **lado Python, por sprite por frame**: uma chamada de property setter, comparação de
tupla, atualização de hit box, spatial hash, loop sobre `sprite_lists`, lookup em dict e
duas escritas indexadas em array — tudo em bytecode Python, multiplicado por N sprites.
Com 10k+ sprites, o frame é dominado por esse trabalho por objeto, não pela renderização.

## 2. pyglet: como as posições chegam à GPU?

`pyglet/sprite.py` (pyglet 2.1.15): cada `Sprite` possui um `_vertex_list` próprio
(4 vértices, indexado, criado em `_create_vertex_list`, linha ~503) dentro do `Batch`.

- `Sprite.position` setter (linha ~549): `self._vertex_list.translate[:] = position * 4`
  — constrói uma tupla de 12 floats em Python e a escreve via slice-assignment no
  atributo `translate` da vertex list (que por baixo escreve na região do sprite dentro
  do buffer compartilhado do batch, marcando-a como suja).
- O mesmo padrão se repete para `x`, `y`, `rotation`, `scale`, `color`: toda mudança de
  atributo replica o valor 4x (um por vértice) e passa pelo protocolo de
  slice-assignment do vertex domain.

O `Batch.draw()` do pyglet consolida os draws, mas o custo por sprite por frame é: uma
property, uma construção de tupla `* 4`, um `__setitem__` de slice no vertex domain —
de novo, bytecode Python por objeto. A replicação por vértice (4x) ainda quadruplica o
volume de dados escrito em Python em relação a um layout por instância.

## 3. moderngl: técnicas de upload disponíveis

moderngl 5.12 (`moderngl/__init__.py`):

- `Buffer.write(data, offset=0)` — sobe bytes (aceita qualquer objeto com buffer
  protocol, incluindo arrays NumPy, sem cópia intermediária em Python).
- `Buffer.orphan(size=-1)` — realoca o armazenamento do buffer (buffer orphaning),
  evitando stall de sincronização quando a GPU ainda está lendo o conteúdo antigo.
- `Buffer.write_chunks(data, start, step, count)` — escrita estriada (útil para
  atualizar um atributo intercalado sem reescrever o resto).
- `Context.vertex_array(program, [(buffer, "2f 2f 1f 4f/i", *attrs)])` — o sufixo
  `/i` marca o buffer como **por instância**: cada instância lê uma fatia do buffer,
  em vez de cada vértice.
- `VertexArray.render(mode, vertices=4, instances=N)` — um único draw call
  instanciado desenha N sprites a partir de um quad de 4 vértices.

## 4. Conclusão: hipóteses da FastObjects

- H1: estado em array NumPy único (AoS interleaved) + 1 `buffer.write` + 1 draw
  instanciado elimina o custo por objeto que domina arcade/pyglet. O trabalho por
  sprite por frame vira aritmética vetorizada em C (NumPy) e um memcpy para o driver —
  zero bytecode Python por sprite.
- H2: a estratégia de upload (write total vs. orphan vs. parcial) importa em
  N alto — decidir no lab (Task 13).

## Texture atlas: como arcade e pyglet fazem (e por que o nosso é estático)

**Data:** 2026-07-09 | **Versões:** arcade 3.3.3, pyglet 2.1.15

Todos os três resolvem o mesmo problema — muitas imagens, um `bind` de textura,
um draw call — empacotando sub-imagens numa textura grande com UVs por imagem.
As diferenças estão no ciclo de vida.

### pyglet (`pyglet/image/atlas.py`)

- `Allocator` de **prateleiras** (`_Strip`): coloca retângulos em faixas
  horizontais; melhor quando as imagens têm alturas parecidas ou entram em
  ordem decrescente de altura (`Allocator.alloc`, linha ~90). É o mesmo
  algoritmo do nosso `Atlas` (shelf packing).
- `TextureAtlas.add(img, border=0)`: aloca, faz `blit_into` e retorna uma
  `TextureRegion` (as UVs). O `border` é blank (deixa pixels em branco em volta),
  não extrusão — a docstring assume que o chamador cuida do bleeding.
- `TextureBin`: quando um atlas enche (`AllocatorException`), **cria um novo
  atlas** em vez de crescer o existente. Ou seja: **dinâmico por multiplicação
  de atlas** — pode passar a ter vários binds se as imagens não couberem num só.
- Imagens **não podem ser removidas** de um atlas depois de adicionadas (a
  própria docstring diz isso).

### arcade (`arcade/texture_atlas/atlas_default.py`)

- Também usa um `Allocator` de prateleiras, mas o atlas é **dinâmico e cresce**:
  `add()` (linha 268) tenta alocar; em `AllocatorException` chama `resize()`
  (linha 652) — **dobra o tamanho da textura e recopia tudo** — ou `rebuild()`
  (linha 744) quando há buracos de texturas coletadas. Mantém ref-counting das
  regiões (`ref_counters.py`) para reaproveitar espaço.
- `border` (default **2px**) com **extrusão de verdade**: copia as tiras de 1px
  de cada borda da imagem para o padding (linha ~499-520), exatamente a técnica
  que adotamos (via `np.pad(mode="edge")`) para evitar bleeding sob filtragem
  linear.
- UVs guardadas por região (`region.py`/`uv_data.py`) e enviadas à GPU num
  buffer de textura, para o shader olhar por `texture_id`.

### FastObjects: atlas estático

Nosso `fastobjects/atlas.py` usa o **mesmo shelf packing** do pyglet/arcade e a
**mesma extrusão de borda** do arcade, mas é **estático**: montado uma vez, a
partir da lista fixa de imagens passada ao `SpriteBatch`, sem alocador dinâmico,
sem `resize`/`rebuild` e sem ref-counting.

- **Por que basta:** o caso de uso do FastObjects é arte conhecida na criação do
  batch (um spritesheet, o conjunto de sprites de um jogo). Nesse cenário, todo
  o custo de um alocador dinâmico — recopiar a textura em cada `resize`,
  fragmentação, contagem de referências — é overhead sem retorno.
- **Trade-off aceito:** não dá para adicionar imagens em runtime (fase futura, se
  houver demanda medida). Em troca: código muito menor, determinístico e
  testável **sem contexto GL** (a lógica de packing/UV é NumPy puro — ver
  `tests/test_atlas.py`), e zero custo de realocação.
- **UVs por instância, não por texture_id:** em vez de um buffer de texture-id
  consultado no shader (arcade), guardamos o retângulo `(u0,v0,u1,v1)` como uma
  coluna fria do SoA e o vertex shader faz `mix(uv0, uv1, corner)`. Assim a
  seleção de imagem entra de graça no dirty tracking existente (sobe só quando
  muda) e a animação de spritesheet é só `group.image = frame`.
