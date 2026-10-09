import os
import re
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from app.core.database import MediaDatabase
from app.core.config import AppConfig


class ScheduleItem:
    """Representa um item na grade de programação da TV."""

    def __init__(
        self,
        file_data: Dict[str, Any],
        start_dt: datetime,
        duration_seconds: int = 1800,
        channel_name: str = ""
    ):
        self.file_data = file_data
        self.file_path = file_data.get("path", "")
        self.raw_name = file_data.get("name", "")
        self.start_dt = start_dt
        self.duration_seconds = max(60, duration_seconds)
        self.end_dt = start_dt + timedelta(seconds=self.duration_seconds)
        self.channel_name = channel_name

        self.clean_title, self.episode_tag, self.season_number, self.episode_number = self._parse_title_and_ep(
            self.raw_name, self.file_path
        )

    def _parse_title_and_ep(self, filename: str, filepath: str = "") -> Tuple[str, str, int, int]:
        """Extrai um título legível, etiqueta de temporada/episódio e valores numéricos para ordenação."""
        base, _ = os.path.splitext(filename)
        clean_base = base.replace(".", " ").replace("_", " ").strip()

        # Procura padrões como S01E02, s1e2, S1.E02
        match_s_e = re.search(r'\b[sS](\d+)[eE](\d+)\b', clean_base)
        if match_s_e:
            s_num = int(match_s_e.group(1))
            e_num = int(match_s_e.group(2))
            ep_tag = f"T{s_num:02d}:E{e_num:02d}"
            title_part = clean_base[:match_s_e.start()].strip()
            if not title_part and filepath:
                # Tenta pegar da pasta pai
                parent = os.path.basename(os.path.dirname(filepath))
                title_part = re.sub(r'\b(?:temporada|season|s\d+)\b.*', '', parent, flags=re.IGNORECASE).strip()
            return (title_part or clean_base).title(), ep_tag, s_num, e_num

        # Procura padrão 1x05, 01x02
        match_x = re.search(r'\b(\d+)x(\d+)\b', clean_base)
        if match_x:
            s_num = int(match_x.group(1))
            e_num = int(match_x.group(2))
            ep_tag = f"T{s_num:02d}:E{e_num:02d}"
            title_part = clean_base[:match_x.start()].strip()
            return (title_part or clean_base).title(), ep_tag, s_num, e_num

        # Procura padrão Episódio / Capitulo / EP 03
        match_ep = re.search(r'\b(?:ep|episodio|episódio|capitulo|capítulo|parte)\s*(\d+)\b', clean_base, re.IGNORECASE)
        s_num = 1
        # Tenta detectar temporada no caminho da pasta pai
        if filepath:
            parent_path = os.path.dirname(filepath)
            match_parent_s = re.search(r'\b(?:temporada|season|s)\s*(\d+)\b', parent_path, re.IGNORECASE)
            if match_parent_s:
                s_num = int(match_parent_s.group(1))

        if match_ep:
            e_num = int(match_ep.group(1))
            ep_tag = f"T{s_num:02d}:E{e_num:02d}" if s_num > 1 else f"Episódio {e_num:02d}"
            title_part = clean_base[:match_ep.start()].strip()
            return (title_part or clean_base).title(), ep_tag, s_num, e_num

        # Procura número solto de episódio no final do nome (ex: "Naruto 025", "One Piece 1080")
        match_end_num = re.search(r'(\D+)\s+(\d{1,4})$', clean_base)
        if match_end_num:
            t_part = match_end_num.group(1).strip()
            e_num = int(match_end_num.group(2))
            # Se o número não for ano (ex: 1999, 2024)
            if not (1900 <= e_num <= 2030):
                ep_tag = f"Episódio {e_num:02d}"
                return t_part.title(), ep_tag, s_num, e_num

        return clean_base.title(), "", s_num, 0

    def update_duration(self, new_duration_seconds: int) -> None:
        """Atualiza a duração real do programa e recalcula o horário de término."""
        self.duration_seconds = max(60, int(new_duration_seconds))
        self.end_dt = self.start_dt + timedelta(seconds=self.duration_seconds)

    @property
    def display_time(self) -> str:
        return f"{self.start_dt.strftime('%H:%M')} - {self.end_dt.strftime('%H:%M')}"

    @property
    def full_display_title(self) -> str:
        if self.episode_tag:
            return f"{self.clean_title} — {self.episode_tag}"
        return self.clean_title


class TVChannel:
    """Representa um canal de TV temático com sua programação."""

    def __init__(
        self,
        channel_id: str,
        number: int,
        name: str,
        icon: str,
        category: str = "video",
        mode: str = "random",  # "random" ou "sequential"
        folders: Optional[List[str]] = None,
        folder_groups: Optional[List[str]] = None,
        auto_filter_tag: Optional[str] = None,
        default_item_duration: int = 2700
    ):
        self.id = channel_id
        self.number = number
        self.name = name
        self.icon = icon
        self.category = category
        self.mode = mode
        self.folders = folders or []
        self.folder_groups = folder_groups or []
        self.auto_filter_tag = auto_filter_tag
        self.default_item_duration = default_item_duration
        self.schedule: List[ScheduleItem] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "name": self.name,
            "icon": self.icon,
            "category": self.category,
            "mode": self.mode,
            "folders": self.folders,
            "folder_groups": self.folder_groups,
            "auto_filter_tag": self.auto_filter_tag
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TVChannel':
        return cls(
            channel_id=data.get("id", f"ch_{random.randint(100, 999)}"),
            number=data.get("number", 1),
            name=data.get("name", "Canal Personalizado"),
            icon=data.get("icon", "📺"),
            category=data.get("category", "video"),
            mode=data.get("mode", "random"),
            folders=data.get("folders", []),
            folder_groups=data.get("folder_groups", []),
            auto_filter_tag=data.get("auto_filter_tag")
        )


    def get_current_item(self, now: Optional[datetime] = None) -> Optional[ScheduleItem]:
        """Retorna o programa que está no ar neste momento."""
        if not self.schedule:
            return None
        if now is None:
            now = datetime.now()

        for item in self.schedule:
            if item.start_dt <= now < item.end_dt:
                return item

        # Se passou de todos ou está antes, busca o item mais próximo no tempo
        best_item = self.schedule[0]
        min_diff = abs((now - best_item.start_dt).total_seconds())
        for item in self.schedule:
            diff = abs((now - item.start_dt).total_seconds())
            if diff < min_diff:
                min_diff = diff
                best_item = item
        return best_item

    def get_upcoming_items(self, limit: int = 5, now: Optional[datetime] = None) -> List[ScheduleItem]:
        """Retorna os próximos programas a serem exibidos."""
        if not self.schedule:
            return []
        if now is None:
            now = datetime.now()

        upcoming = [item for item in self.schedule if item.end_dt > now]
        return upcoming[:limit]


class TVScheduleManager:
    """Gerencia canais temáticos e constrói grades inteligentes (aleatórias ou sequenciais)."""

    def __init__(self, db: MediaDatabase, config: Optional[AppConfig] = None):
        self.db = db
        self.config = config or AppConfig()
        self.channels: List[TVChannel] = []
        self.load_channels_from_config()

    def load_channels_from_config(self) -> None:
        """Carrega os canais a partir da configuração do usuário ou inicializa os padrões."""
        raw_channels = self.config.get_tv_channels()
        self.channels = [TVChannel.from_dict(c) for c in raw_channels]
        # Ordena canais por número
        self.channels.sort(key=lambda c: c.number)

    def save_channels_to_config(self) -> None:
        """Salva os canais atuais no arquivo de preferências do usuário."""
        channels_data = [c.to_dict() for c in self.channels]
        self.config.set_tv_channels(channels_data)

    def _normalize_path(self, p: str) -> str:
        return os.path.normpath(p).lower().replace('\\', '/')

    def _classify_video_file(self, f: Dict[str, Any]) -> str:
        """Classifica o arquivo de vídeo com base em pastas e padrões de nome."""
        p = self._normalize_path(f.get("path", ""))
        name = f.get("name", "").lower()

        # 1. Documentários
        if any(k in p for k in ['/documentarios/', '/documentario/', '/documentários/', '/documentário/', '/documentaries/', '/documentary/', '/docs/']):
            return 'documentaries'

        # 2. Animes Japoneses
        if any(k in p for k in ['/animes/', '/anime/', 'animestotais']):
            return 'animes'

        # 3. Desenhos Ocidentais / Cartoons
        if any(k in p for k in ['/desenhos/', '/desenho/', '/cartoons/', '/cartoon/']):
            return 'cartoons'

        # 4. Séries e Temporadas
        if any(k in p for k in ['/series/', '/serie/', '/séries/', '/série/', '/tv shows/', '/tv show/']):
            return 'series'

        # 5. Filmes e Cinema
        if any(k in p for k in ['/filmes/', '/filme/', '/movies/', '/movie/', '/cinema/']):
            return 'movies'

        # 6. Detecção por padrão de episódio (S01E02 / 1x04 / Ep 01)
        if re.search(r'\b[sS]\d+[eE]\d+\b', name) or re.search(r'\b\d+x\d+\b', name) or re.search(r'\bep\s*\d+\b', name):
            return 'series'

        # 7. Padrão: Filmes
        return 'movies'

    def _clean_show_name(self, folder_name: str) -> str:
        """Limpa prefixos de temporada e tags para agrupar todas as temporadas da mesma série/show."""
        s = folder_name.replace('ª', ' ').replace('º', ' ').replace('°', ' ')
        s = re.sub(r'[\(\[\{].*?[\)\]\}]', ' ', s)
        s = re.sub(r'\b\d+\s*temporada\b', ' ', s, flags=re.IGNORECASE)
        s = re.sub(r'\btemporada\s*\d*\b', ' ', s, flags=re.IGNORECASE)
        s = re.sub(r'\bseason\s*\d*\b', ' ', s, flags=re.IGNORECASE)
        s = re.sub(r'\b[sS]\d+\b', ' ', s)
        s = re.sub(r'\b(?:1080p|720p|480p|web-dl|bluray|dvdrip|dublado|dual|legendado|dub)\b', ' ', s, flags=re.IGNORECASE)
        s = re.sub(r'[-_.]+', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s.title() if s else folder_name.title()

    def _extract_show_group(self, file_path: str) -> str:
        """Identifica o show/franquia a que o arquivo pertence de forma consistente."""
        p = self._normalize_path(file_path)
        parts = p.split('/')
        for i, part in enumerate(parts[:-1]):
            low = part.lower()
            if low in ('desenhos', 'desenho', 'animes', 'anime', 'series', 'serie', 'séries', 'série', 'documentarios', 'documentários', 'cartoons'):
                if i + 1 < len(parts) - 1:
                    return self._clean_show_name(parts[i + 1])
        # Pega a pasta avó se o pai for "Temporada 1" ou "Season 1"
        parent = os.path.basename(os.path.dirname(file_path))
        if re.search(r'\b(?:temporada|season|s\d+)\b', parent, re.IGNORECASE):
            grandparent = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
            if grandparent:
                return self._clean_show_name(grandparent)
        return self._clean_show_name(parent)

    def _natural_sort_key(self, text: str):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

    def _estimate_duration(self, f_data: Dict[str, Any], is_movie: bool = False, is_audio: bool = False) -> int:
        """Estima a duração real de um arquivo com base em tamanho e categoria."""
        if is_audio or f_data.get("category") == "audio":
            return 240  # 4 min

        size_mb = f_data.get("size", 0) / (1024 * 1024)

        if is_movie:
            if size_mb > 3500:
                return 7500  # 2h05m
            elif size_mb > 2000:
                return 6600  # 1h50m
            elif size_mb > 1200:
                return 5700  # 1h35m
            elif size_mb > 600:
                return 5100  # 1h25m
            else:
                return 4500  # 1h15m

        # Episódios / Vídeos normais
        if size_mb > 2500:
            return 5400  # 1h30m (episódio especial/filme)
        elif size_mb > 1000:
            return 3600  # 1h00m (série 50-60min)
        elif size_mb > 450:
            return 2700  # 45min (série padrão)
        elif size_mb > 200:
            return 1500  # 25min (anime / desenho)
        else:
            return 1320  # 22min

    def _generate_sequential_schedule(
        self,
        channel: TVChannel,
        pool: List[Dict[str, Any]],
        start_dt: datetime,
        rng: random.Random
    ) -> List[ScheduleItem]:
        """Gera grade sequencial cronológica estrita (S01E01 -> S01E02 -> ... -> S02E01)."""
        if not pool:
            return []

        # Agrupa arquivos por show / franquia
        show_dict: Dict[str, List[Dict[str, Any]]] = {}
        for f in pool:
            grp = self._extract_show_group(f.get("path", ""))
            show_dict.setdefault(grp, []).append(f)

        # Ordena cada série de forma cronológica rigorosa
        for s, files in show_dict.items():
            def episode_sort_key(item: Dict[str, Any]):
                path = item.get("path", "")
                name = item.get("name", "")
                # Extrai temporada e episódio
                dummy_item = ScheduleItem(item, start_dt=start_dt)
                parent_dir = os.path.normpath(item.get("parent_dir", "")).lower()
                return (
                    dummy_item.season_number,
                    dummy_item.episode_number if dummy_item.episode_number > 0 else 99999,
                    parent_dir,
                    self._natural_sort_key(name)
                )

            files.sort(key=episode_sort_key)

        shows = list(show_dict.keys())
        # Embaralha apenas a ordem dos shows no rodízio do dia
        rng.shuffle(shows)

        # Monta lista intercalada preservando rigorosamente a sequência de episódios de cada série
        interleaved_files: List[Dict[str, Any]] = []
        max_episodes = max(len(v) for v in show_dict.values())

        for ep_idx in range(max_episodes):
            for s in shows:
                series_eps = show_dict[s]
                if ep_idx < len(series_eps):
                    interleaved_files.append(series_eps[ep_idx])

        # Constrói a linha do tempo de 24 horas a partir de 00:00
        schedule: List[ScheduleItem] = []
        curr_time = start_dt
        end_of_day = start_dt + timedelta(days=1)
        file_idx = 0
        total_files = len(interleaved_files)

        while curr_time < end_of_day and total_files > 0:
            f_data = interleaved_files[file_idx % total_files]
            exact_dur = f_data.get("duration", 0)
            if exact_dur and exact_dur > 0:
                dur = exact_dur
            else:
                dur = self._estimate_duration(f_data, is_movie=False)

            item = ScheduleItem(
                file_data=f_data,
                start_dt=curr_time,
                duration_seconds=dur,
                channel_name=channel.name
            )
            schedule.append(item)
            curr_time = item.end_dt
            file_idx += 1

        return schedule

    def _generate_random_schedule(
        self,
        channel: TVChannel,
        pool: List[Dict[str, Any]],
        start_dt: datetime,
        rng: random.Random
    ) -> List[ScheduleItem]:
        """Gera grade totalmente aleatória (Shuffle) sem repetições imediatas."""
        if not pool:
            return []

        shuffled_pool = list(pool)
        rng.shuffle(shuffled_pool)

        is_movie_ch = ("filme" in channel.name.lower() or "cine" in channel.name.lower() or channel.auto_filter_tag == "movies")
        is_audio_ch = (channel.category == "audio" or channel.auto_filter_tag == "music")

        schedule: List[ScheduleItem] = []
        curr_time = start_dt
        end_of_day = start_dt + timedelta(days=1)
        file_idx = 0
        total_files = len(shuffled_pool)

        while curr_time < end_of_day and total_files > 0:
            f_data = shuffled_pool[file_idx % total_files]
            exact_dur = f_data.get("duration", 0)
            if exact_dur and exact_dur > 0:
                dur = exact_dur
            else:
                dur = self._estimate_duration(f_data, is_movie=is_movie_ch, is_audio=is_audio_ch)

            item = ScheduleItem(
                file_data=f_data,
                start_dt=curr_time,
                duration_seconds=dur,
                channel_name=channel.name
            )
            schedule.append(item)
            curr_time = item.end_dt
            file_idx += 1

        return schedule

    def build_schedules_for_today(self, randomize: bool = False, seed: Optional[int] = None) -> None:
        """Gera a grade de 24 horas de hoje para todos os canais configurados."""
        today = datetime.now()
        start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0)

        if randomize:
            base_seed = seed if seed is not None else random.randint(1, 9999999)
        else:
            base_seed = start_of_day.toordinal()

        video_files, *_ = self.db.search_files(query="", category="video", limit=30000)
        audio_files, *_ = self.db.search_files(query="", category="audio", limit=5000)

        # Categorização em pools para canais sem pastas específicas
        classified_pools: Dict[str, List[Dict[str, Any]]] = {
            "movies": [],
            "series": [],
            "cartoons": [],
            "animes": [],
            "documentaries": [],
            "music": audio_files,
            "mixed": video_files
        }

        for f in video_files:
            genre = self._classify_video_file(f)
            if genre in classified_pools:
                classified_pools[genre].append(f)

        for idx, channel in enumerate(self.channels):
            channel_seed = base_seed + (idx + 1) * 137
            rng = random.Random(channel_seed)

            # 1. Resolve dinamicamente as pastas do canal (pastas individuais + grupos multi-HD)
            resolved_folders = self.config.resolve_channel_folders(channel.folders, channel.folder_groups)

            if resolved_folders:
                channel_pool = self.db.get_files_for_channel(
                    categories=[channel.category] if channel.category != "all" else None,
                    folders=resolved_folders,
                    limit=20000
                )
            else:
                # 2. Caso contrário, usa pool classificado ou categoria geral
                tag = channel.auto_filter_tag
                if tag and tag in classified_pools and classified_pools[tag]:
                    channel_pool = classified_pools[tag]
                elif channel.category == "audio":
                    channel_pool = audio_files
                else:
                    channel_pool = video_files

            # 3. Constrói a grade conforme o modo do canal (Sequencial ou Aleatório)
            if channel.mode == "sequential":
                channel.schedule = self._generate_sequential_schedule(channel, channel_pool, start_of_day, rng)
            else:
                channel.schedule = self._generate_random_schedule(channel, channel_pool, start_of_day, rng)

