# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [1.2.0] - 2026-10-09

### Adicionado
- **Painel de Estatísticas da Biblioteca (`StatsDialog`)**:
  - Cards de métricas principais (KPIs): Total de Mídias, Espaço Ocupado (GB/TB), Tempo Total de Reprodução Acumulado e Volumes Monitorados.
  - Distribuição visual por categoria com barras proporcionais coloridas.
  - Armazenamento comparativo por disco/unidade (`E:`, `F:`, `H:`).
  - Principais formatos e extensões mais frequentes (`.mkv`, `.mp4`, `.flac`, etc.).
  - Top 5 maiores arquivos da biblioteca com botões de reprodução instantânea e localização no Explorer.
- **Acesso Rápido**:
  - Novo botão **📊 Estatísticas** no cabeçalho superior.
  - Novos atalhos de teclado: `F9` e `Ctrl+I`.
  - Opção no menu de contexto da bandeja do Windows (System Tray).
- **Progresso Determinístico e Percentual**:
  - Extração de durações no `IndexWorker` agora exibe porcentagem e contagem real (`⏱️ Duração: 340/1,250 mídias (27%)`).
- **Método `get_detailed_stats()`**: Agregação de dados otimizada em SQLite no `MediaDatabase`.

---

## [1.1.0] - 2026-10-09

### Adicionado
- **Duração Exata de Mídias**: Extrator ultrarrápido em Python puro (`app/utils/duration_extractor.py`) para leitura de cabeçalhos de contêineres MP4, MOV, MKV, WebM, AVI, WAV e MP3.
- **Adaptação Real da Grade de TV**: Grade do Modo TV agora gera blocos de horários precisos baseados na duração real dos arquivos indexados.
- **Persistência de Duração no SQLite**: Nova coluna `duration` na tabela `files` com migração automática e preservação de metadados em reindexações.
- **Enriquecimento em Segundo Plano**: `IndexWorker` extrai durações de vídeos/áudios novos sem bloquear a busca de arquivos.
- **Padronização de Versionamento**: Inclusão de `app/__version__.py` e skill `mediafinder-release` para automação de publicações no GitHub.

### Modificado
- `TVModeWindow`: Salva no SQLite a duração detectada dinamicamente pelo player durante a reprodução.
- `main.py`: Supressão de logs espúrios do backend multimídia FFmpeg (`QFFmpeg::Demuxer`).

---

## [1.0.0] - 2026-10-08

### Adicionado
- Versão inicial estável do **MediaFinder**.
- Busca instantânea de arquivos distribuídos em múltiplos volumes (`E:`, `F:`, `H:`).
- SQLite WAL com FTS5 (Full-Text Search) de alta performance.
- Filtros por categoria (Vídeos, Imagens, Áudios, Documentos) e por unidades de disco.
- Grupos de mídia multi-pastas e multi-HD.
- Painel lateral de prévia retrátil (`Ctrl+P`) com miniaturas e leitura de texto.
- Modo TV com canais temáticos (Filmes, Séries, Desenhos, Animes, Documentários, Músicas).
- Modos de reprodução Aleatório (Shuffle) e Sequencial cronológico estrito (S01E01 -> S01E02).
- Sorteio rápido de mídia aleatória (`F4`).
- Integração com Windows Explorer (`explorer.exe /select`).
