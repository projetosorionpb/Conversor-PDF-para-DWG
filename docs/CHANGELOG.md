# Changelog

## [2.0.0] - Profissionalização da Estrutura

### Mudanças e Reestruturações (Refatoração)
- O monolito central `pdf_para_dxf.py` que comportava 1000+ linhas foi desmembrado no pacote profissional `src/` em 7 submódulos especialistas.
- Remoção da pasta `web_version` com código desatualizado, em favor de um único source of truth em `web/app.py` que agora importa direto de `src/`.
- Limpeza sistemática de 46MB de dejetos locais temporários e artefatos de builds velhas.
- Arquivos de LISP avulsos migrados para diretórios secundários ou descontinuados, trazendo toda a lógica para o backend em Python.
- Nova documentação arquitetural.

### Adicionado
- `src/blocks.py`: Substituição das antigas chamadas e arquivos confusos para um processamento limpo e acoplável de símbolos para AutoCAD.
- Adição de `requirements-dev.txt` focado apenas no empacotamento com PyInstaller, separando a aplicação em ambiente isolado do processo de build do cliente local.
- Separação clara de Entrypoints: O binário Windows usará agora o `main.py` focado apenas no launcher do Flask + Browser.
