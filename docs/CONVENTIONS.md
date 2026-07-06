# Convenções da FastObjects

## Código
- Type hints completos em toda a API pública; `from __future__ import annotations`.
- Docstrings estilo Google (Args/Returns/Raises) — legíveis no código e no mkdocs.
- ruff como linter/formatter único (config no pyproject).
- Arquivos focados: um módulo = uma responsabilidade (window, batch, core).

## Documentação (padrão FastAPI/rich)
- README começa com a tabela de benchmarks, depois um exemplo mínimo executável.
- Todo exemplo em docs/ deve rodar copiado-e-colado, sem edição.
- docs/ futura em mkdocs-material (Fase 5).

## Performance
- Nenhum loop Python por sprite em caminho quente — sempre NumPy vetorizado.
- Toda decisão de performance referencia um experimento em benchmarks/RESULTS.md.

## Erros
- Mensagens dizem o que fazer: valores esperados, valor necessário, causa provável.
