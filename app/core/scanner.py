import os
import time
from pathlib import Path
from typing import List, Set, Dict, Any, Optional, Tuple
from PySide6.QtCore import QThread, Signal

from app.core.database import MediaDatabase
from app.utils.media_helpers import get_category_for_extension, get_drive_letter
from app.utils.duration_extractor import extract_media_duration

IGNORED_DIRS = {
    "$recycle.bin", "system volume information", ".git", ".svn",
    "node_modules", "__pycache__", "$windows.~bt", "$windows.~ws",
    "recovery", "msocache", "config.msi"
}

class IndexWorker(QThread):
    """Thread em segundo plano para varredura e indexação ultra rápida de arquivos."""

    # Sinais para UI
    progress_changed = Signal(str, int)                # (pasta_atual, arquivos_encontrados)
    detailed_progress = Signal(str, int, int, str)     # (stage: "scan"|"duration", current, total, name)
    finished = Signal(int, float, dict)                 # (total_indexado, tempo_segundos, stats)
    error_occurred = Signal(str, str)                   # (pasta, mensagem_erro)

    # Aliases de compatibilidade para sinais
    progress = progress_changed
    finished_scan = finished

    def __init__(self, folders: Any = None, db: Any = None, parent=None):
        super().__init__(parent)
        if isinstance(folders, MediaDatabase):
            self.db = folders
            raw_folders = db or []
        elif isinstance(db, MediaDatabase):
            self.db = db
            raw_folders = folders or []
        else:
            self.db = db or folders
            raw_folders = folders if isinstance(folders, list) else (db or [])

        self.folders = [os.path.normpath(f) for f in raw_folders if f and isinstance(f, str)]
        self._is_running = True
        self.batch_size = 2000

    def stop(self) -> None:
        """Sinaliza parada imediata do scan."""
        self._is_running = False

    def run(self) -> None:
        start_time = time.time()
        total_indexed = 0

        for folder in self.folders:
            if not self._is_running:
                break

            if not os.path.exists(folder):
                self.error_occurred.emit(folder, "Diretório ou unidade não está acessível no momento.")
                continue

            try:
                folder_count = self._scan_directory(folder)
                total_indexed += folder_count
            except Exception as e:
                self.error_occurred.emit(folder, str(e))

        # Enriquecimento de metadados: Extração de duração real para vídeos e áudios
        if self._is_running:
            try:
                self._enrich_media_durations(total_indexed)
            except Exception:
                pass

        elapsed = time.time() - start_time
        stats = self.db.get_stats()
        self.finished.emit(total_indexed, elapsed, stats)

    def _enrich_media_durations(self, total_indexed: int) -> None:
        """Extrai a duração exata de vídeos e áudios que ainda não possuem duração no banco."""
        batch_updates: List[Tuple[int, str]] = []
        total_to_process = self.db.get_count_media_files_missing_duration()
        if total_to_process <= 0:
            return

        processed_count = 0
        
        while self._is_running:
            missing_items = self.db.get_media_files_missing_duration(limit=300)
            if not missing_items:
                break

            for item in missing_items:
                if not self._is_running:
                    break

                processed_count += 1
                file_path = item.get("path", "")
                file_name = item.get("name", "")
                
                self.detailed_progress.emit("duration", processed_count, total_to_process, file_name)
                self.progress_changed.emit(f"Duração: {processed_count}/{total_to_process} ({file_name})", total_indexed)

                dur = extract_media_duration(file_path)
                if dur and dur > 0:
                    batch_updates.append((dur, file_path))
                else:
                    # Marca como 1s para não reprocessar indefinidamente arquivos ilegíveis
                    batch_updates.append((1, file_path))

                if len(batch_updates) >= 50:
                    self.db.update_durations_batch(batch_updates)
                    batch_updates.clear()

            if batch_updates:
                self.db.update_durations_batch(batch_updates)
                batch_updates.clear()

    def _scan_directory(self, root_folder: str) -> int:
        """Varre recursivamente o diretório usando os.scandir."""
        batch_records: List[Dict[str, Any]] = []
        existing_paths: Set[str] = set()
        count = 0
        
        # Pilha de diretórios para varredura iterativa (evita estouro de recursão)
        stack = [root_folder]

        while stack and self._is_running:
            current_dir = stack.pop()
            self.detailed_progress.emit("scan", count, 0, current_dir)
            self.progress_changed.emit(current_dir, count)

            try:
                with os.scandir(current_dir) as it:
                    for entry in it:
                        if not self._is_running:
                            break

                        try:
                            # Ignora pastas de sistema/lixeira
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name.lower() not in IGNORED_DIRS and not entry.name.startswith("."):
                                    stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                path_str = entry.path
                                existing_paths.add(path_str)
                                
                                stat = entry.stat(follow_symlinks=False)
                                ext = os.path.splitext(entry.name)[1].lower()
                                cat = get_category_for_extension(ext)
                                drive = get_drive_letter(path_str)

                                batch_records.append({
                                    "name": entry.name,
                                    "path": path_str,
                                    "parent_dir": current_dir,
                                    "extension": ext,
                                    "category": cat,
                                    "size": stat.st_size,
                                    "mtime": stat.st_mtime,
                                    "drive": drive
                                })

                                count += 1

                                # Persiste em lote para performance
                                if len(batch_records) >= self.batch_size:
                                    self.db.upsert_files_batch(batch_records)
                                    batch_records.clear()
                                    self.progress_changed.emit(current_dir, count)

                        except (PermissionError, FileNotFoundError, OSError):
                            continue

            except (PermissionError, FileNotFoundError, OSError):
                continue

        # Inserir o restante
        if batch_records and self._is_running:
            self.db.upsert_files_batch(batch_records)
            batch_records.clear()

        # Limpar registros do banco que foram excluídos do disco
        if self._is_running and existing_paths:
            self.db.remove_missing_files(existing_paths, root_folder)

        return count
