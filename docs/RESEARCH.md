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
