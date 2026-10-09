# MediaFinder

[![Versão](https://img.shields.io/badge/vers%C3%A3o-1.2.0-blue.svg)](CHANGELOG.md)
[![Licença: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)

Aplicativo desktop para Windows desenvolvido em Python e Qt (PySide6) que ajuda a localizar, organizar e reproduzir arquivos de mídia (vídeos, fotos, músicas e documentos) distribuídos em diferentes pastas, discos rígidos, SSDs ou unidades montadas.

---

## Recursos

### Busca e Indexação
- **Busca por texto**: Consulta arquivos pelo nome utilizando banco de dados SQLite com suporte a busca textual (FTS5).
- **Varredura em segundo plano**: A indexação das pastas ocorre sem travar a interface do programa com cálculo determinístico de duração.
- **Histórico e preferências**: Salva as últimas pastas utilizadas, termos de pesquisa e filtros selecionados.

### Dashboard & Estatísticas
- **Panorama Geral da Biblioteca**: Painel visual com cards de métricas (total de arquivos, GB/TB ocupados, tempo total contínuo de filmes/músicas e discos ativos).
- **Gráficos Proporcionais**: Visualização de distribuição por categorias e armazenamento por volume de disco.
- **Top Formatos e Maiores Arquivos**: Identificação dos formatos mais comuns e acesso aos arquivos mais pesados com reprodução e abertura no Explorer.

### Filtros e Agrupamentos
- **Categorias**: Filtros rápidos para Vídeos, Imagens, Áudios e Documentos.
- **Filtro por unidade**: Opção para pesquisar em uma unidade específica ou em todas ao mesmo tempo.
- **Grupos de mídia**: Permite agrupar pastas de locais diferentes sob uma mesma categoria (por exemplo, reunir pastas de filmes que estejam em discos separados).
- **Ordenação**: Ordenação por nome, tamanho de arquivo e data de modificação.

### Modo TV
- **Reprodução contínua**: Janela de reprodução de vídeo contínua com suporte a canais.
- **Ordem de reprodução**:
  - *Sequencial*: Reproduz episódios em ordem cronológica (ex.: `S01E01`, `S01E02`).
  - *Aleatório*: Sorteia itens sem repetir o mesmo arquivo em sequência.
- **Grade de programação**: Lista os próximos itens previstos com base na duração dos vídeos.
- **Controles**: Troca de canais, ajuste de volume e alternância de faixas de áudio e legendas.

### Pré-Visualização e Utilitários
- **Painel lateral de prévia**: Exibe detalhes do arquivo, dimensões de imagens e trecho de arquivos de texto (`.txt`, `.nfo`, `.srt`).
- **Ações no sistema**: Atalho para abrir o arquivo no reprodutor padrão ou localizá-lo no Windows Explorer.
- **Sorteio rápido**: Abre uma mídia aleatória a partir de um atalho (`F4`).
- **Exclusão de arquivos**: Permite remover arquivos do disco com janela de confirmação.

---

## Guia de Uso

### 1. Adicionar pastas para monitoramento
1. Clique no botão **Pastas** no canto superior direito.
2. Na aba **Pastas & Unidades Monitoradas**, clique em **Adicionar Pasta / Unidade...** e escolha os diretórios que contêm seus arquivos.
3. Para atualizar a lista de arquivos a qualquer momento, clique em **Reindexar Tudo Agora** (ou pressione `F5`).

### 2. Pesquisar e filtrar
- Digite o nome do arquivo no campo de busca.
- Use os botões de categoria (*Vídeos*, *Imagens*, etc.) ou o seletor de unidade para refinar o resultado.
- Pressione `Ctrl + P` para abrir ou fechar o painel de detalhes e prévia lateral.

### 3. Agrupar pastas de locais diferentes
Se você possui arquivos do mesmo tipo espalhados por vários discos:
1. Abra o menu **Pastas** e vá para a aba **Grupos de Mídia & Categorias**.
2. Selecione ou crie um grupo (ex.: `Filmes`).
3. Adicione os caminhos das pastas de cada disco (ex.: `D:\Filmes`, `E:\Cinema`, `F:\Downloads\Filmes`).
4. Essas pastas serão tratadas de forma unificada nas buscas e nos canais de TV.

### 4. Usar o Modo TV
1. Pressione `F8` (ou `Ctrl + T`) para abrir a janela da TV.
2. Troque de canal pelas setas `←` / `→` ou digitando o número do canal (`1` a `9`).
3. Pressione a tecla `C` para abrir o gerenciador de canais, onde você pode:
   - Adicionar canais e associá-los a pastas ou grupos de mídia.
   - Definir se a reprodução deve ser sequencial (para séries) ou aleatória (para filmes e clipes).
4. Use as setas `↑` / `↓` para volume, `A` para faixas de áudio e `S` ou `L` para legendas.

---

## Sugestões de Organização de Arquivos

O aplicativo varre subpastas em qualquer nível de profundidade. Para facilitar a identificação de séries e episódios no Modo TV, recomenda-se uma organização simples:

### Séries e Conteúdo Episódico

```
Séries/
└── Breaking Bad/
    ├── Temporada 01/
    │   ├── Breaking Bad S01E01.mkv
    │   ├── Breaking Bad S01E02.mkv
    │   └── ...
    └── Temporada 02/
        ├── Breaking Bad S02E01.mkv
        └── ...
```

Padrões de nomes identificados automaticamente:
- `S01E02`, `s1e2`, `1x05`, `01x05`
- `Episódio 03`, `Ep 03`, `Capitulo 12`, `Parte 2`
- Numeração simples ao final do arquivo (`Nome 01.mp4`, `Nome 02.mp4`)

### Filmes

Filmes podem ficar soltos na pasta principal, divididos por categorias/gêneros ou em subpastas individuais com arquivos de legenda:

```
Filmes/
├── Interestelar (2014)/
│   ├── Interestelar (2014).mkv
│   └── Interestelar (2014).srt
├── Matrix (1999)/
│   └── Matrix (1999).mp4
├── Ficção/
│   └── Blade Runner 2049 (2017).mkv
└── O Poderoso Chefao.avi
```

---

## Atalhos de Teclado

### Janela Principal
| Atalho | Ação |
|---|---|
| `Ctrl + F` / `F3` | Focar no campo de busca |
| `F4` / `Ctrl + R` | Sorteio aleatório de mídia |
| `F8` / `Ctrl + T` | Abrir o Modo TV |
| `F9` / `Ctrl + I` | Abrir o painel de Estatísticas da Biblioteca |
| `Ctrl + P` | Mostrar / ocultar painel de prévia |
| `Ctrl + A` | Selecionar todos os arquivos da lista |
| `Enter` | Abrir arquivo no reprodutor padrão |
| `Delete` | Excluir arquivos selecionados |
| `F5` | Reindexar diretórios |

### Janela do Modo TV
| Atalho | Ação |
|---|---|
| `←` / `→` ou `Page Up/Down` | Trocar de canal |
| `↑` / `↓` ou `+` / `-` | Ajustar volume |
| `1` a `9` | Ir direto para o canal |
| `Espaço` | Pausar / Continuar |
| `C` | Gerenciar canais |
| `A` | Alternar faixa de áudio |
| `S` / `L` | Alternar legendas |
| `G` / `Tab` | Mostrar / ocultar grade de programação |
| `F` / `F11` | Tela cheia |
| `Esc` | Sair de tela cheia ou fechar a janela |

---

## Instalação e Execução

### Executável (Windows)
Baixe o arquivo `MediaFinder.exe` na aba de [Releases](https://github.com/xToshiro/MediaFinder/releases). Não é necessário instalar Python nem configurar dependências.

### A partir do Código-Fonte

1. Clone o repositório:
```bash
git clone https://github.com/xToshiro/MediaFinder.git
cd MediaFinder
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute:
```bash
python main.py
```

### Gerar o Executável

Para compilar o `.exe` localmente:
```bash
python build_exe.py
```
O arquivo será criado na pasta `dist/MediaFinder.exe`.

---

## Tecnologias Utilizadas

- **Linguagem**: Python 3.10+
- **Interface**: PySide6 (Qt 6)
- **Banco de Dados**: SQLite (FTS5)
- **Imagens**: Pillow (PIL)
- **Empacotamento**: PyInstaller

---

## Licença

Distribuído sob a licença GNU General Public License v3.0 (GPLv3). Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.
