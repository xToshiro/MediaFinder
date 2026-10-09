import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

class AppConfig:
    """Gerencia o salvamento e carregamento de configurações e histórico do usuário."""

    def __init__(self):
        # Diretório de configuração: XDG em Linux (~/.config/MediaFinder) e AppData em Windows
        if sys.platform == "win32":
            base_dir = os.getenv("APPDATA") or str(Path.home())
        else:
            base_dir = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        self.config_dir = Path(base_dir) / "MediaFinder"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"

        self.default_config: Dict[str, Any] = {
            "watched_folders": [],  # Somente diretórios explicitamente indicados pelo usuário
            "media_folder_groups": {
                "Filmes": [],
                "Séries": [],
                "Desenhos": [],
                "Animes": [],
                "Documentários": [],
                "Músicas": []
            },


            "last_search_query": "",
            "last_category_filter": "all",
            "last_drive_filter": "all",
            "search_history": [],
            "max_history_items": 30,
            "window_width": 1150,
            "window_height": 720,
            "window_maximized": False,
            "last_indexed_at": None,
            "auto_scan_on_startup": True,
            "random_mode_folders": [],
            "random_mode_category": "video",
            "random_mode_source": "custom", # "custom" (pastas marcadas) ou "current_results" (busca atual)
            "tv_channels": [
                {
                    "id": "ch_1",
                    "number": 1,
                    "name": "Panorama",
                    "icon": "⚡",
                    "category": "video",
                    "mode": "random",
                    "folders": [],
                    "folder_groups": [],
                    "auto_filter_tag": "mixed"
                },
                {
                    "id": "ch_2",
                    "number": 2,
                    "name": "TeleCine",
                    "icon": "🎬",
                    "category": "video",
                    "mode": "random",
                    "folders": [],
                    "folder_groups": ["Filmes"],
                    "auto_filter_tag": "movies"
                },
                {
                    "id": "ch_3",
                    "number": 3,
                    "name": "Maratonando",
                    "icon": "🍿",
                    "category": "video",
                    "mode": "sequential",
                    "folders": [],
                    "folder_groups": ["Séries"],
                    "auto_filter_tag": "series"
                },
                {
                    "id": "ch_4",
                    "number": 4,
                    "name": "Cartoonopolis",
                    "icon": "🌀",
                    "category": "video",
                    "mode": "sequential",
                    "folders": [],
                    "folder_groups": ["Desenhos"],
                    "auto_filter_tag": "cartoons"
                },
                {
                    "id": "ch_5",
                    "number": 5,
                    "name": "Anime Station",
                    "icon": "🌸",
                    "category": "video",
                    "mode": "sequential",
                    "folders": [],
                    "folder_groups": ["Animes"],
                    "auto_filter_tag": "animes"
                },
                {
                    "id": "ch_6",
                    "number": 6,
                    "name": "Olhar Curioso",
                    "icon": "🔭",
                    "category": "video",
                    "mode": "random",
                    "folders": [],
                    "folder_groups": ["Documentários"],
                    "auto_filter_tag": "documentaries"
                },
                {
                    "id": "ch_7",
                    "number": 7,
                    "name": "Na Onda FM",
                    "icon": "🎙️",
                    "category": "audio",
                    "mode": "random",
                    "folders": [],
                    "folder_groups": ["Músicas"],
                    "auto_filter_tag": "music"
                }
            ]
        }
        
        self.data = self.load()

    def load(self) -> Dict[str, Any]:
        """Carrega configurações do arquivo JSON ou retorna padrão."""
        if not self.config_file.exists():
            self.save(self.default_config)
            return self.default_config.copy()
        
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Mescla chaves ausentes caso nova versão adicione campos
                for k, v in self.default_config.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            print(f"Aviso: Erro ao carregar config.json ({e}), usando padrão.")
            return self.default_config.copy()

    def save(self, data: Dict[str, Any] = None) -> None:
        """Salva as configurações atuais no arquivo JSON."""
        if data is not None:
            self.data = data
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            if sys.platform != "win32":
                try:
                    os.chmod(self.config_file, 0o600)
                except OSError:
                    pass
        except Exception as e:
            print(f"Erro ao salvar config: {e}")

    def get_watched_folders(self) -> List[str]:
        return self.data.get("watched_folders", self.default_config["watched_folders"])

    def set_watched_folders(self, folders: List[str]) -> None:
        self.data["watched_folders"] = folders
        self.save()

    def get_folder_groups(self) -> Dict[str, List[str]]:
        """Retorna os grupos de equivalência de pastas (ex: 'Filmes' -> ['E:\\Midias\\Filmes', 'F:\\Midias\\Filmes'])."""
        groups = self.data.get("media_folder_groups")
        if groups is None:
            groups = dict(self.default_config["media_folder_groups"])
            self.data["media_folder_groups"] = groups
            self.save()
        return groups

    def set_folder_groups(self, groups: Dict[str, List[str]]) -> None:
        self.data["media_folder_groups"] = groups
        self.save()

    def resolve_channel_folders(self, folders: List[str], folder_groups: Optional[List[str]] = None) -> List[str]:
        """Combina pastas diretas e pastas pertencentes aos grupos de mídia sem duplicatas."""
        resolved = []
        # 1. Pastas diretas
        for f in folders or []:
            f_clean = str(f).strip()
            if f_clean and f_clean not in resolved:
                resolved.append(f_clean)

        # 2. Pastas dos grupos selecionados
        groups = self.get_folder_groups()
        for grp_name in folder_groups or []:
            grp_folders = groups.get(grp_name, [])
            for f in grp_folders:
                f_clean = str(f).strip()
                if f_clean and f_clean not in resolved:
                    resolved.append(f_clean)

        return resolved

    def add_search_history(self, query: str) -> None:
        """Adiciona termo ao histórico evitando duplicatas sucessivas."""
        query = query.strip()
        if not query:
            return
        history = self.data.get("search_history", [])
        if query in history:
            history.remove(query)
        history.insert(0, query)
        max_items = self.data.get("max_history_items", 30)
        self.data["search_history"] = history[:max_items]
        self.save()

    def get_search_history(self) -> List[str]:
        return self.data.get("search_history", [])

    def clear_search_history(self) -> None:
        self.data["search_history"] = []
        self.save()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def get_tv_channels(self) -> List[Dict[str, Any]]:
        channels = self.data.get("tv_channels")
        if not channels:
            channels = list(self.default_config["tv_channels"])
            self.data["tv_channels"] = channels
            self.save()
        return channels

    def set_tv_channels(self, channels: List[Dict[str, Any]]) -> None:
        self.data["tv_channels"] = channels
        self.save()

    def reset_tv_channels_to_default(self) -> List[Dict[str, Any]]:
        default_chans = [dict(c) for c in self.default_config["tv_channels"]]
        self.data["tv_channels"] = default_chans
        self.save()
        return default_chans
