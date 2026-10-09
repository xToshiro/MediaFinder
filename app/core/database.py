import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

class MediaDatabase:
    """Gerencia a base de dados SQLite e índices FTS para busca instantânea de arquivos."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            appdata = os.getenv("APPDATA") or str(Path.home())
            db_dir = Path(appdata) / "MediaFinder"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(db_dir / "media_index.db")
        else:
            self.db_path = db_path

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Otimizações de performance SQLite
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;") # 64MB de cache
        conn.execute("PRAGMA temp_store = MEMORY;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabela principal de arquivos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    parent_dir TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    category TEXT NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    mtime REAL NOT NULL DEFAULT 0,
                    drive TEXT NOT NULL,
                    duration INTEGER NOT NULL DEFAULT 0
                );
            """)

            # Migração automática: Adicionar coluna duration se a tabela já existia sem ela
            cursor.execute("PRAGMA table_info(files);")
            columns = [row["name"] for row in cursor.fetchall()]
            if "duration" not in columns:
                try:
                    cursor.execute("ALTER TABLE files ADD COLUMN duration INTEGER NOT NULL DEFAULT 0;")
                except Exception:
                    pass

            # Índices para filtros rápidos
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(name COLLATE NOCASE);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_category ON files(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_drive ON files(drive);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files(size DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_ext ON files(extension);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_duration ON files(duration);")

            # Tabela FTS5 para busca textual com suporte a prefixo
            try:
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                        name,
                        path,
                        content='files',
                        content_rowid='id',
                        tokenize = 'unicode61'
                    );
                """)

                # Triggers para manter o FTS5 sincronizado automaticamente
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                        INSERT INTO files_fts(rowid, name, path) VALUES (new.id, new.name, new.path);
                    END;
                """)
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                        INSERT INTO files_fts(files_fts, rowid, name, path) VALUES('delete', old.id, old.name, old.path);
                    END;
                """)
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
                        INSERT INTO files_fts(files_fts, rowid, name, path) VALUES('delete', old.id, old.name, old.path);
                        INSERT INTO files_fts(rowid, name, path) VALUES (new.id, new.name, new.path);
                    END;
                """)
            except Exception as e:
                print(f"Nota: FTS5 não pôde ser inicializado ({e}), fallback para LIKE.")

            conn.commit()

    def upsert_files_batch(self, files_data: List[Dict[str, Any]]) -> int:
        """Insere ou atualiza registros de arquivos em lote para máxima velocidade."""
        if not files_data:
            return 0

        # Garante campo duration padrão se omitido
        for item in files_data:
            if "duration" not in item:
                item["duration"] = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO files (name, path, parent_dir, extension, category, size, mtime, drive, duration)
                VALUES (:name, :path, :parent_dir, :extension, :category, :size, :mtime, :drive, :duration)
                ON CONFLICT(path) DO UPDATE SET
                    name = excluded.name,
                    parent_dir = excluded.parent_dir,
                    extension = excluded.extension,
                    category = excluded.category,
                    size = excluded.size,
                    mtime = excluded.mtime,
                    drive = excluded.drive,
                    duration = CASE WHEN excluded.duration > 0 THEN excluded.duration ELSE files.duration END
            """
            cursor.executemany(query, files_data)
            conn.commit()
            return cursor.rowcount

    def remove_missing_files(self, existing_paths_set: set, folder_root: str) -> int:
        """Remove do banco arquivos da pasta que não existem mais no disco."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            norm_root = os.path.normpath(folder_root)
            # Seleciona todos os caminhos do banco que começam com a pasta
            cursor.execute("SELECT id, path FROM files WHERE path LIKE ?", (f"{norm_root}%",))
            rows = cursor.fetchall()
            ids_to_delete = [r["id"] for r in rows if r["path"] not in existing_paths_set]

            if ids_to_delete:
                # Divide em lotes de 900 para não estourar o limite de parâmetros do sqlite
                for i in range(0, len(ids_to_delete), 900):
                    batch = ids_to_delete[i:i+900]
                    placeholders = ",".join("?" for _ in batch)
                    cursor.execute(f"DELETE FROM files WHERE id IN ({placeholders})", batch)
                conn.commit()
                return len(ids_to_delete)
            return 0

    def delete_files_by_paths(self, paths: List[str]) -> int:
        """Remove do banco múltiplos arquivos especificados por seus caminhos."""
        if not paths:
            return 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            deleted_count = 0
            for i in range(0, len(paths), 900):
                batch = paths[i:i+900]
                placeholders = ",".join("?" for _ in batch)
                cursor.execute(f"DELETE FROM files WHERE path IN ({placeholders})", batch)
                deleted_count += cursor.rowcount
            conn.commit()
            return deleted_count

    def update_file_duration(self, path: str, duration_sec: int) -> bool:
        """Atualiza a duração em segundos de um arquivo individual."""
        if not path or duration_sec <= 0:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE files SET duration = ? WHERE path = ?", (int(duration_sec), path))
            conn.commit()
            return cursor.rowcount > 0

    def update_durations_batch(self, items: List[Tuple[int, str]]) -> int:
        """Atualiza a duração em lote: lista de (duration_sec, path)."""
        if not items:
            return 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("UPDATE files SET duration = ? WHERE path = ?", items)
            conn.commit()
            return cursor.rowcount

    def get_count_media_files_missing_duration(self) -> int:
        """Retorna o total de arquivos de mídia pendentes de cálculo de duração."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM files WHERE category IN ('video', 'audio') AND (duration IS NULL OR duration <= 0)")
            row = cursor.fetchone()
            return row["count"] if row else 0

    def get_media_files_missing_duration(self, limit: int = 2000) -> List[Dict[str, Any]]:
        """Retorna arquivos de mídia (vídeo/áudio) que ainda não possuem duração extraída."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, path, parent_dir, extension, category, size, mtime, drive
                FROM files
                WHERE category IN ('video', 'audio') AND (duration IS NULL OR duration <= 0)
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def search_files(
        self,
        query: str = "",
        category: str = "all",
        drive: str = "all",
        sort_by: str = "name_asc",
        limit: int = 500,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """Realiza busca ultra rápida com múltiplos filtros e paginação."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = query.strip()
            where_clauses = []
            params = []

            # 1. Filtro por Categoria
            if category and category.lower() != "all":
                where_clauses.append("f.category = ?")
                params.append(category.lower())

            # 2. Filtro por Drive
            if drive and drive.lower() != "all":
                drive_clean = drive.upper()
                if not drive_clean.endswith(":"):
                    drive_clean += ":"
                where_clauses.append("f.drive = ?")
                params.append(drive_clean)

            # 3. Filtro por Query (FTS5 ou LIKE para correspondência parcial flexível)
            use_fts = False
            if query:
                # Termos separados para permitir busca tipo 'curso aula 01'
                terms = query.split()
                fts_terms = []
                like_clauses = []
                for term in terms:
                    clean_term = "".join(c for c in term if c.isalnum() or c in ("-", "_", "."))
                    if clean_term:
                        fts_terms.append(f'"{clean_term}"*')
                    like_clauses.append("(f.name LIKE ? OR f.path LIKE ?)")
                    params.extend([f"%{term}%", f"%{term}%"])
                
                # Se houver múltiplos termos, usamos LIKE com índices para máxima precisão de substring
                where_clauses.append(" AND ".join(like_clauses))

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # Ordenação
            sort_map = {
                "name_asc": "f.name COLLATE NOCASE ASC",
                "name_desc": "f.name COLLATE NOCASE DESC",
                "size_desc": "f.size DESC",
                "size_asc": "f.size ASC",
                "mtime_desc": "f.mtime DESC",
                "mtime_asc": "f.mtime ASC",
                "ext_asc": "f.extension ASC",
            }
            order_sql = sort_map.get(sort_by, "f.name COLLATE NOCASE ASC")

            count_query = f"SELECT COUNT(*) as total, COALESCE(SUM(f.size), 0) as total_size FROM files f {where_sql}"
            cursor.execute(count_query, params)
            count_row = cursor.fetchone()
            total_count = count_row["total"]
            total_size = count_row["total_size"]

            data_query = f"""
                SELECT f.id, f.name, f.path, f.parent_dir, f.extension, f.category, f.size, f.mtime, f.drive, COALESCE(f.duration, 0) as duration
                FROM files f
                {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_query, params + [limit, offset])
            rows = [dict(r) for r in cursor.fetchall()]

            return rows, total_count, total_size

    def get_random_file(
        self,
        categories: Optional[List[str]] = None,
        folders: Optional[List[str]] = None,
        drive: Optional[str] = "all",
        query: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retorna um arquivo aleatório do banco respeitando os filtros especificados."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            where_clauses = []
            params = []

            # Filtro por categorias (ex: ['video', 'audio'])
            if categories:
                cat_clean = [c.lower() for c in categories if c.lower() != "all"]
                if cat_clean:
                    placeholders = ",".join("?" for _ in cat_clean)
                    where_clauses.append(f"f.category IN ({placeholders})")
                    params.extend(cat_clean)

            # Filtro por pastas específicas (ex: ['E:\\Midias\\Filmes', 'F:\\Desenhos'])
            if folders:
                folder_clauses = []
                for folder in folders:
                    norm_folder = os.path.normpath(folder)
                    folder_clauses.append("f.path LIKE ?")
                    params.append(f"{norm_folder}%")
                if folder_clauses:
                    where_clauses.append(f"({' OR '.join(folder_clauses)})")

            # Filtro por Drive
            if drive and drive.lower() != "all":
                drive_clean = drive.upper()
                if not drive_clean.endswith(":"):
                    drive_clean += ":"
                where_clauses.append("f.drive = ?")
                params.append(drive_clean)

            # Filtro por query se houver
            if query and query.strip():
                terms = query.strip().split()
                for term in terms:
                    where_clauses.append("(f.name LIKE ? OR f.path LIKE ?)")
                    params.extend([f"%{term}%", f"%{term}%"])

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            data_query = f"""
                SELECT f.id, f.name, f.path, f.parent_dir, f.extension, f.category, f.size, f.mtime, f.drive, COALESCE(f.duration, 0) as duration
                FROM files f
                {where_sql}
                ORDER BY RANDOM()
                LIMIT 1
            """
            cursor.execute(data_query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_files_for_channel(
        self,
        categories: Optional[List[str]] = None,
        folders: Optional[List[str]] = None,
        drive: Optional[str] = "all",
        limit: int = 50000
    ) -> List[Dict[str, Any]]:
        """Busca arquivos indexados para preenchimento de canal de TV respeitando filtros de pastas e categorias."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            where_clauses = []
            params = []

            # Filtro por categorias (ex: ['video'], ['audio'])
            if categories:
                cat_clean = [c.lower() for c in categories if c.lower() != "all"]
                if cat_clean:
                    placeholders = ",".join("?" for _ in cat_clean)
                    where_clauses.append(f"f.category IN ({placeholders})")
                    params.extend(cat_clean)

            # Filtro por pastas específicas (ex: ['E:\\Midias\\Series', 'F:\\Midias\\Animes'])
            if folders:
                folder_clauses = []
                for folder in folders:
                    folder_str = str(folder).strip()
                    if folder_str:
                        norm_folder = os.path.normpath(folder_str)
                        folder_clauses.append("f.path LIKE ?")
                        params.append(f"{norm_folder}%")
                if folder_clauses:
                    where_clauses.append(f"({' OR '.join(folder_clauses)})")

            # Filtro por Drive
            if drive and drive.lower() != "all":
                drive_clean = drive.upper()
                if not drive_clean.endswith(":"):
                    drive_clean += ":"
                where_clauses.append("f.drive = ?")
                params.append(drive_clean)

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            data_query = f"""
                SELECT f.id, f.name, f.path, f.parent_dir, f.extension, f.category, f.size, f.mtime, f.drive, COALESCE(f.duration, 0) as duration
                FROM files f
                {where_sql}
                ORDER BY f.parent_dir ASC, f.name ASC
                LIMIT ?
            """
            cursor.execute(data_query, params + [limit])
            return [dict(r) for r in cursor.fetchall()]


    def get_indexed_subfolders(self, limit: int = 100) -> List[str]:
        """Retorna uma lista de diretórios pai/pastas conhecidas indexadas no banco."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT parent_dir
                FROM files
                ORDER BY parent_dir ASC
                LIMIT ?
            """, (limit,))
            return [r["parent_dir"] for r in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas gerais da base indexada."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as total_files, COALESCE(SUM(size), 0) as total_size, COALESCE(SUM(duration), 0) as total_duration FROM files")
            row = cursor.fetchone()
            total_files = row["total_files"]
            total_size = row["total_size"]
            total_duration = row["total_duration"]

            cursor.execute("SELECT category, COUNT(*) as count FROM files GROUP BY category")
            cat_counts = {r["category"]: r["count"] for r in cursor.fetchall()}

            cursor.execute("SELECT drive, COUNT(*) as count FROM files GROUP BY drive")
            drive_counts = {r["drive"]: r["count"] for r in cursor.fetchall()}

            return {
                "total_files": total_files,
                "total_size": total_size,
                "total_duration": total_duration,
                "categories": cat_counts,
                "drives": drive_counts
            }

    def get_detailed_stats(self) -> Dict[str, Any]:
        """Retorna dados agregados detalhados para o painel de estatísticas e gráficos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Totais Gerais
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_files, 
                    COALESCE(SUM(size), 0) as total_size,
                    COALESCE(SUM(duration), 0) as total_duration,
                    COUNT(DISTINCT drive) as total_drives
                FROM files
            """)
            summary_row = cursor.fetchone()

            # 2. Estatísticas por Categoria (contagem, tamanho e duração)
            cursor.execute("""
                SELECT 
                    category, 
                    COUNT(*) as count, 
                    COALESCE(SUM(size), 0) as total_size,
                    COALESCE(SUM(duration), 0) as total_duration
                FROM files 
                GROUP BY category 
                ORDER BY total_size DESC
            """)
            categories_stats = [dict(r) for r in cursor.fetchall()]

            # 3. Estatísticas por Disco/Drive
            cursor.execute("""
                SELECT 
                    drive, 
                    COUNT(*) as count, 
                    COALESCE(SUM(size), 0) as total_size
                FROM files 
                GROUP BY drive 
                ORDER BY total_size DESC
            """)
            drives_stats = [dict(r) for r in cursor.fetchall()]

            # 4. Top 8 Extensões / Formatos
            cursor.execute("""
                SELECT 
                    extension, 
                    category,
                    COUNT(*) as count, 
                    COALESCE(SUM(size), 0) as total_size
                FROM files 
                WHERE extension != ''
                GROUP BY extension 
                ORDER BY count DESC 
                LIMIT 8
            """)
            top_extensions = [dict(r) for r in cursor.fetchall()]

            # 5. Top 5 Maiores Arquivos da Biblioteca
            cursor.execute("""
                SELECT id, name, path, parent_dir, extension, category, size, duration, drive
                FROM files 
                ORDER BY size DESC 
                LIMIT 5
            """)
            largest_files = [dict(r) for r in cursor.fetchall()]

            return {
                "total_files": summary_row["total_files"],
                "total_size": summary_row["total_size"],
                "total_duration": summary_row["total_duration"],
                "total_drives": summary_row["total_drives"],
                "categories": categories_stats,
                "drives": drives_stats,
                "top_extensions": top_extensions,
                "largest_files": largest_files
            }

    def clear_database(self) -> None:
        """Limpa todos os registros do banco de dados."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM files;")
            try:
                cursor.execute("DELETE FROM files_fts;")
            except Exception:
                pass
            conn.commit()
