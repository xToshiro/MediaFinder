import os
import sys
import tempfile
import time
from pathlib import Path

# Suporte a caracteres UTF-8 no console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import AppConfig
from app.core.database import MediaDatabase
from app.core.scanner import IndexWorker
from app.core.tv_schedule import TVScheduleManager
from app.utils.media_helpers import get_category_for_extension, format_file_size, get_drive_letter

def run_tests():
    print("Iniciando testes unitários e de integração...")

    # 1. Teste de helpers
    assert get_category_for_extension(".mp4") == "video"
    assert get_category_for_extension(".PNG") == "image"
    assert get_category_for_extension(".mp3") == "audio"
    assert get_category_for_extension(".pdf") == "document"
    assert format_file_size(1024 * 1024 * 50) == "50.0 MB"
    print("✓ Media helpers validados.")

    # 2. Teste do Banco de Dados com SQLite em arquivo temporário
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        test_db_path = tmp.name

    try:
        db = MediaDatabase(test_db_path)
        
        # Inserção em lote
        test_files = [
            {
                "name": "filme_acao_2026.mp4",
                "path": "E:\\Midias\\Filmes\\filme_acao_2026.mp4",
                "parent_dir": "E:\\Midias\\Filmes",
                "extension": ".mp4",
                "category": "video",
                "size": 1024 * 1024 * 1500, # 1.5 GB
                "mtime": time.time(),
                "drive": "E:"
            },
            {
                "name": "foto_viagem.jpg",
                "path": "F:\\Midias\\Fotos\\foto_viagem.jpg",
                "parent_dir": "F:\\Midias\\Fotos",
                "extension": ".jpg",
                "category": "image",
                "size": 1024 * 1024 * 5, # 5 MB
                "mtime": time.time(),
                "drive": "F:"
            },
            {
                "name": "musica_rock.flac",
                "path": "H:\\Midias\\Musicas\\musica_rock.flac",
                "parent_dir": "H:\\Midias\\Musicas",
                "extension": ".flac",
                "category": "audio",
                "size": 1024 * 1024 * 30, # 30 MB
                "mtime": time.time(),
                "drive": "H:"
            }
        ]

        db.upsert_files_batch(test_files)
        
        # Teste de busca por termo
        results, total, size = db.search_files(query="acao")
        assert total == 1
        assert results[0]["name"] == "filme_acao_2026.mp4"

        # Teste de busca por categoria
        results, total, size = db.search_files(category="image")
        assert total == 1
        assert results[0]["name"] == "foto_viagem.jpg"

        # Teste de busca por drive
        results, total, size = db.search_files(drive="H:")
        assert total == 1
        assert results[0]["name"] == "musica_rock.flac"

        # Teste de estatísticas
        stats = db.get_stats()
        assert stats["total_files"] == 3
        assert "video" in stats["categories"]
        assert "E:" in stats["drives"]

        # Teste de sorteio aleatório (Modo Aleatório Rápido)
        rand_video = db.get_random_file(categories=["video"])
        assert rand_video is not None
        assert rand_video["category"] == "video"

        rand_folder = db.get_random_file(folders=["F:\\Midias\\Fotos"])
        assert rand_folder is not None
        assert rand_folder["name"] == "foto_viagem.jpg"

        subfolders = db.get_indexed_subfolders()
        assert len(subfolders) == 3

        # Teste de persistência e atualização de duração
        db.update_file_duration("E:\\Midias\\Filmes\\filme_acao_2026.mp4", 5432)
        res, total, _ = db.search_files(query="acao")
        assert res[0]["duration"] == 5432

        missing = db.get_media_files_missing_duration()
        assert isinstance(missing, list)

        # Teste do Modo TV com duração real (TVScheduleManager, canais sequenciais e customizados)
        tv_mgr = TVScheduleManager(db)
        assert len(tv_mgr.channels) >= 7
        tv_mgr.build_schedules_for_today()
        ch1 = tv_mgr.channels[0]
        assert len(ch1.schedule) > 0
        current_item = ch1.get_current_item()
        assert current_item is not None

        # Teste de get_files_for_channel
        ch_files = db.get_files_for_channel(categories=["video"], folders=["E:\\Midias\\Filmes"])
        assert len(ch_files) == 1
        assert ch_files[0]["name"] == "filme_acao_2026.mp4"
        assert ch_files[0]["duration"] == 5432

        # Teste de exclusão em lote
        deleted = db.delete_files_by_paths(["H:\\Midias\\Musicas\\musica_rock.flac"])
        assert deleted == 1
        stats_after = db.get_stats()
        assert stats_after["total_files"] == 2

        print("✓ Banco de dados, consultas SQLite/FTS, Duração Exata, Modo Aleatório, Modo TV e Exclusão em Lote validados.")
    finally:
        try:
            if os.path.exists(test_db_path):
                os.remove(test_db_path)
        except Exception:
            pass

    # 3. Teste de Configuração
    config = AppConfig()
    config.add_search_history("teste_busca_01")
    assert "teste_busca_01" in config.get_search_history()
    tv_chans = config.get_tv_channels()
    assert len(tv_chans) >= 7
    assert any(c["mode"] == "sequential" for c in tv_chans)
    assert any(c["mode"] == "random" for c in tv_chans)

    # Teste de Grupos de Mídia Multi-HD
    groups = config.get_folder_groups()
    assert "Filmes" in groups
    assert "Séries" in groups
    resolved = config.resolve_channel_folders(folders=["D:\\Custom"], folder_groups=["Filmes"])
    assert "D:\\Custom" in resolved
    print("✓ Persistência de configuração, canais de TV e Grupos Multi-HD validada.")


    # 4. Validação e Instanciação de Todos os Componentes de UI
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from app.ui.preview_panel import PreviewPanel
    from app.ui.tv_player_widget import TVPlayerWidget
    from app.ui.tv_mode_window import TVModeWindow
    from app.ui.channel_config_dialog import ChannelConfigDialog
    from app.ui.random_dialog import RandomMediaDialog
    from app.ui.settings_dialog import SettingsDialog
    from app.ui.stats_dialog import StatsDialog
    from app.ui.main_window import MainWindow

    # 4.1 PreviewPanel
    p = PreviewPanel()
    p.set_file_data({"name": "test.jpg", "path": "c:\\test.jpg", "category": "image", "extension": ".jpg", "size": 100, "mtime": 0, "drive": "C:"})
    p.set_file_data(None)

    # 4.2 TVPlayerWidget com OSD e Transições
    tv_player = TVPlayerWidget()
    tv_player.load_media("c:\\dummy.mp4", "Dummy Live", 120, channel_number=1, channel_name="Cinema")
    tv_player.trigger_channel_transition(1, "Cinema")
    tv_player.show_channel_osd(2, "Séries & Animes", "Rick and Morty")
    tv_player.show_volume_osd(70)
    tv_player.set_volume_relative(+5)
    tv_player.set_volume_relative(-10)
    tv_player.toggle_mute()
    tv_player.toggle_mute()
    tv_player.cycle_audio_track()
    tv_player.cycle_subtitle_track()
    tv_player.set_audio_track(0)
    tv_player.set_subtitle_track(-1)
    tv_player.show_track_osd("ÁUDIO", "Português 5.1")
    tv_player.show_track_osd("LEGENDA", "Português")

    # 4.3 TVModeWindow e Diálogos com banco temporário
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as ui_tmp:
        ui_db_path = ui_tmp.name

    try:
        ui_db = MediaDatabase(ui_db_path)
        tv_window = TVModeWindow(ui_db, config)
        assert tv_window is not None
        tv_window._tune_number_direct(1)
        tv_window._next_channel()
        tv_window._prev_channel()
        tv_window.toggle_sidebar()
        tv_window.toggle_sidebar()
        tv_window.regenerate_all_schedules()

        # Teste de resolução de duração real no Modo TV
        if tv_window.current_playing_item:
            old_dur = tv_window.current_playing_item.duration_seconds
            tv_window._on_media_duration_resolved(tv_window.current_playing_item.file_path, 7200)

        # 4.4 ChannelConfigDialog
        ch_dialog = ChannelConfigDialog(config)
        assert ch_dialog is not None
        ch_dialog._add_new_channel()
        ch_dialog._move_channel_up()
        ch_dialog._move_channel_down()

        # 4.5 RandomMediaDialog
        rand_dialog = RandomMediaDialog(config, ui_db)
        assert rand_dialog is not None

        # 4.6 SettingsDialog
        sett_dialog = SettingsDialog(config, ui_db)
        assert sett_dialog is not None

        # 4.7 StatsDialog e get_detailed_stats
        detailed = ui_db.get_detailed_stats()
        assert "categories" in detailed
        assert "drives" in detailed
        assert "top_extensions" in detailed
        assert "largest_files" in detailed
        stats_dialog = StatsDialog(ui_db)
        assert stats_dialog is not None

        # 4.8 MainWindow e IndexWorker
        main_win = MainWindow()
        assert main_win is not None

        # Teste do IndexWorker com pasta temporária
        with tempfile.TemporaryDirectory() as scan_dir:
            sample_file = os.path.join(scan_dir, "sample_video.mp4")
            with open(sample_file, "wb") as f:
                f.write(b"0" * 1024)

            worker = IndexWorker(folders=[scan_dir], db=ui_db)
            worker.run() # Execução síncrona do worker para validar run()
            stats_worker = ui_db.get_stats()
            assert stats_worker["total_files"] >= 1

        print("✓ Todos os componentes, diálogos, canais e IndexWorker validados com sucesso!")
    finally:
        try:
            if os.path.exists(ui_db_path):
                os.remove(ui_db_path)
        except Exception:
            pass

    print("\nTODOS OS TESTES PASSARAM COM SUCESSO!")

if __name__ == "__main__":
    run_tests()

