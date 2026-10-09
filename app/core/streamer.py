import os
import sys
import time
import socket
import logging
import mimetypes
import uuid
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import threading
import urllib.parse

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("MediaFinder.Streamer")

EXTRA_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".ts": "video/mp2t",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".vtt": "text/vtt; charset=utf-8",
    ".srt": "text/plain; charset=utf-8",
}


def convert_srt_to_vtt(srt_path: str, vtt_path: str) -> bool:
    """Converte legenda .srt para formato WebVTT com detecção automática de encoding (UTF-8, Windows-1252, ISO-8859-1)."""
    try:
        with open(srt_path, "rb") as f:
            raw = f.read()

        text = None
        for enc in ("utf-8", "windows-1252", "iso-8859-1", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            text = raw.decode("utf-8", errors="replace")

        import re
        vtt_content = "WEBVTT\n\n" + re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text)
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(vtt_content)
        return True
    except Exception as e:
        logger.debug(f"Erro ao converter legenda para VTT: {e}")
        return False


def get_local_ip() -> str:
    """Retorna o IP da máquina na rede local (LAN)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class RangeHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    Handler HTTP com suporte a Range Requests (Status 206 Partial Content),
    cabeçalhos CORS e HEAD requests, indispensável para Smart TVs e Chromecast.
    """

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self._process_request(send_body=False)

    def do_GET(self):
        self._process_request(send_body=True)

    def _process_request(self, send_body: bool = True):
        media_server = getattr(self.server, "media_server", None)
        if not media_server:
            self.send_error(500, "Servidor de mídia não configurado")
            return

        parsed_url = urllib.parse.urlparse(self.path)
        token = parsed_url.path.strip("/").split("/")[-1]

        file_path = media_server.get_file_path(token)
        if not file_path or not os.path.isfile(file_path):
            self.send_error(404, "Arquivo não encontrado")
            return

        try:
            total_size = os.path.getsize(file_path)
            _, ext = os.path.splitext(file_path)
            content_type = EXTRA_MIME_TYPES.get(ext.lower()) or mimetypes.guess_type(file_path)[0] or "video/mp4"

            range_header = self.headers.get("Range")
            start = 0
            end = total_size - 1

            if range_header and range_header.startswith("bytes="):
                range_str = range_header[6:].strip()
                try:
                    if range_str.startswith("-"):
                        suffix_len = int(range_str[1:])
                        start = max(0, total_size - suffix_len)
                        end = total_size - 1
                    else:
                        parts = range_str.split("-")
                        if parts[0]:
                            start = int(parts[0])
                        if len(parts) > 1 and parts[1]:
                            end = int(parts[1])
                except (ValueError, IndexError):
                    self.send_error(400, "Header Range inválido")
                    return

                if start >= total_size or end >= total_size or start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{total_size}")
                    self.end_headers()
                    return

                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
                self.send_header("Content-Length", str(length))
            else:
                length = total_size
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(length))

            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
            self.end_headers()

            if not send_body:
                return

            chunk_size = 512 * 1024  # 512 KB por bloco para streaming fluido e sem engasgos em 1080p
            bytes_left = length
            with open(file_path, "rb") as f:
                f.seek(start)
                while bytes_left > 0:
                    to_read = min(chunk_size, bytes_left)
                    data = f.read(to_read)
                    if not data:
                        break
                    self.wfile.write(data)
                    bytes_left -= len(data)

        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            logger.debug(f"Erro ao transmitir arquivo HTTP: {e}")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class MediaStreamServer:
    """Servidor HTTP embutido para disponibilizar mídias na rede local para as TVs."""

    def __init__(self, port: int = 1745):
        self.desired_port = port
        self.host_ip = get_local_ip()
        self.httpd: Optional[ThreadedHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.active_tokens: Dict[str, str] = {}
        self._path_to_token: Dict[str, str] = {}
        self.actual_port: int = port
        self._lock = threading.Lock()

    def start(self) -> int:
        if self.httpd is not None:
            return self.actual_port

        self.host_ip = get_local_ip()

        try:
            self.httpd = ThreadedHTTPServer((self.host_ip, self.desired_port), RangeHTTPRequestHandler)
            self.actual_port = self.httpd.server_address[1]
        except OSError:
            self.httpd = ThreadedHTTPServer((self.host_ip, 0), RangeHTTPRequestHandler)
            self.actual_port = self.httpd.server_address[1]

        self.httpd.media_server = self
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        logger.info(f"Servidor de streaming iniciado em http://{self.host_ip}:{self.actual_port}/")
        return self.actual_port

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self.server_thread = None
        self.clear_tokens()

    def register_file(self, file_path: str) -> str:
        """Gera um token criptograficamente seguro e aleatório (não previsível) para a mídia."""
        self.start()
        abs_p = os.path.abspath(file_path)
        with self._lock:
            token = self._path_to_token.get(abs_p)
            if not token:
                import secrets
                token = secrets.token_urlsafe(24)
                self.active_tokens[token] = abs_p
                self._path_to_token[abs_p] = token
        return f"http://{self.host_ip}:{self.actual_port}/stream/{token}"

    def unregister_file(self, file_path: str):
        """Remove o acesso HTTP de um arquivo específico."""
        abs_p = os.path.abspath(file_path)
        with self._lock:
            token = self._path_to_token.pop(abs_p, None)
            if token:
                self.active_tokens.pop(token, None)

    def clear_tokens(self):
        """Revoga todos os tokens ativos liberados na rede."""
        with self._lock:
            self.active_tokens.clear()
            self._path_to_token.clear()

    def get_file_path(self, token: str) -> Optional[str]:
        with self._lock:
            return self.active_tokens.get(token)


@dataclass
class TVDevice:
    name: str
    host: str
    model: str
    device_type: str  # "cast" ou "dlna"
    device_id: str
    raw_device: Any = None


class TVCastManager(QObject):
    """
    Controlador de descoberta e transmissão para Smart TVs (Chromecast, LG webOS, DLNA).
    """

    device_found = Signal(object)      # TVDevice
    discovery_finished = Signal(int)    # total_found
    cast_started = Signal(str, str)    # device_name, file_name
    cast_stopped = Signal()
    status_updated = Signal(str, float, float)  # state ('PLAYING', 'PAUSED', 'IDLE'), current_sec, duration_sec
    volume_updated = Signal(float, bool)        # volume (0.0 to 1.0), is_muted
    error_occurred = Signal(str)

    _instance: Optional["TVCastManager"] = None

    @classmethod
    def get_instance(cls) -> "TVCastManager":
        if cls._instance is None:
            cls._instance = TVCastManager()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stream_server = MediaStreamServer()
        self.discovered_devices: Dict[str, TVDevice] = {}
        self.active_cast_device: Optional[TVDevice] = None
        self.active_chromecast = None
        self.is_casting: bool = False
        self._current_media_url: Optional[str] = None
        self._current_file_path: Optional[str] = None
        self._browser = None
        self._discovery_thread: Optional[threading.Thread] = None
        self._stop_polling = threading.Event()

    def start_discovery(self):
        """Inicia a busca por TVs na rede local em segundo plano."""
        if self._discovery_thread and self._discovery_thread.is_alive():
            return

        self._discovery_thread = threading.Thread(target=self._run_discovery, daemon=True)
        self._discovery_thread.start()

    def _run_discovery(self):
        found_count = 0
        try:
            import pychromecast

            arp_candidates = self._get_arp_candidates()

            # 1. Sondagem ultra-rápida HTTP/Eureka nos IPs conhecidos (exibe na UI em ~50ms)
            for ip in arp_candidates:
                try:
                    import urllib.request
                    import json
                    req = urllib.request.urlopen(f"http://{ip}:8008/setup/eureka_info?params=name,device_info", timeout=0.8)
                    data = json.loads(req.read().decode())
                    name = data.get("name") or f"TV ({ip})"
                    model_str = "LG webOS TV (Google Cast)" if "lg" in name.lower() or "webos" in name.lower() else "Chromecast (Google Cast)"
                    dev_id = ip
                    device = TVDevice(
                        name=name,
                        host=ip,
                        model=model_str,
                        device_type="cast",
                        device_id=dev_id,
                        raw_device=None
                    )
                    if dev_id not in self.discovered_devices:
                        self.discovered_devices[dev_id] = device
                        found_count += 1
                        self.device_found.emit(device)
                except Exception:
                    pass

            def on_device_found(chromecast):
                nonlocal found_count
                cast_info = chromecast.cast_info
                name = chromecast.name or cast_info.friendly_name or "TV Cast"
                dev_id = str(cast_info.host)
                model = cast_info.model_name or "Google Cast / Smart TV"

                if "webos" in model.lower() or "lg" in name.lower():
                    friendly_model = "LG webOS TV (Google Cast)"
                else:
                    friendly_model = f"{model} (Google Cast)"

                device = TVDevice(
                    name=name,
                    host=cast_info.host,
                    model=friendly_model,
                    device_type="cast",
                    device_id=dev_id,
                    raw_device=chromecast
                )

                if dev_id not in self.discovered_devices:
                    self.discovered_devices[dev_id] = device
                    found_count += 1
                    self.device_found.emit(device)
                else:
                    # Atualiza com a instância viva do pychromecast
                    self.discovered_devices[dev_id].raw_device = chromecast

            try:
                chromecasts, browser = pychromecast.get_chromecasts(
                    timeout=3.5,
                    known_hosts=arp_candidates if arp_candidates else None,
                    callback=on_device_found
                )
                self._browser = browser
                for cc in chromecasts:
                    on_device_found(cc)
            except Exception as e:
                logger.debug(f"Aviso durante get_chromecasts: {e}")

        except ImportError:
            logger.warning("pychromecast não instalado.")
        except Exception as e:
            logger.error(f"Erro na descoberta de TVs: {e}")

        self.discovery_finished.emit(len(self.discovered_devices))

    def _get_arp_candidates(self) -> List[str]:
        candidates = []
        try:
            if os.path.exists("/proc/net/arp"):
                with open("/proc/net/arp", "r") as f:
                    lines = f.readlines()[1:]
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
                            ip = parts[0]
                            s = socket.socket()
                            s.settimeout(0.15)
                            if s.connect_ex((ip, 8008)) == 0:
                                candidates.append(ip)
                            s.close()
        except Exception:
            pass
        return candidates

    def add_manual_device(self, host: str):
        host = host.strip()
        if not host:
            return

        def _worker():
            try:
                import pychromecast

                cc = pychromecast.get_chromecast_from_host(
                    (host, 8009, None, None, None),
                    timeout=3.0
                )
                if cc:
                    dev_id = f"manual_{host}"
                    device = TVDevice(
                        name=cc.name or f"TV ({host})",
                        host=host,
                        model=cc.model_name or "Smart TV / Cast",
                        device_type="cast",
                        device_id=dev_id,
                        raw_device=cc
                    )
                    self.discovered_devices[dev_id] = device
                    self.device_found.emit(device)
            except Exception as e:
                self.error_occurred.emit(f"Não foi possível conectar ao IP {host}: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def cast_media(self, device: TVDevice, file_path: str):
        if not os.path.isfile(file_path):
            self.error_occurred.emit(f"Arquivo não encontrado: {file_path}")
            return

        def _cast_thread():
            try:
                self.active_cast_device = device
                self._current_file_path = file_path
                file_name = os.path.basename(file_path)

                media_url = self.stream_server.register_file(file_path)
                self._current_media_url = media_url

                _, ext = os.path.splitext(file_path)
                mime = EXTRA_MIME_TYPES.get(ext.lower(), "video/mp4")

                cast_device = device.raw_device
                if cast_device is None:
                    import pychromecast
                    cast_device = pychromecast.get_chromecast_from_host(
                        (device.host, 8009, None, None, None),
                        timeout=5.0
                    )
                    device.raw_device = cast_device

                cast_device.wait()
                self.active_chromecast = cast_device

                import pychromecast
                if cast_device.app_id != pychromecast.APP_MEDIA_RECEIVER:
                    try:
                        cast_device.start_app(pychromecast.APP_MEDIA_RECEIVER)
                        cast_device.wait()
                        time.sleep(1.0)
                    except Exception as app_err:
                        logger.debug(f"Aviso ao iniciar APP_MEDIA_RECEIVER: {app_err}")

                # Detecta legendas correspondentes (.srt ou .vtt)
                base_no_ext, _ = os.path.splitext(file_path)
                sub_url = None
                srt_candidate = base_no_ext + ".srt"
                vtt_candidate = base_no_ext + ".vtt"

                if os.path.exists(srt_candidate):
                    if convert_srt_to_vtt(srt_candidate, vtt_candidate):
                        sub_url = self.stream_server.register_file(vtt_candidate)
                elif os.path.exists(vtt_candidate):
                    sub_url = self.stream_server.register_file(vtt_candidate)

                mc = cast_device.media_controller
                mc.play_media(
                    media_url,
                    content_type=mime,
                    title=file_name,
                    stream_type="BUFFERED",
                    subtitles=sub_url,
                    subtitles_lang="pt-BR"
                )
                mc.block_until_active(timeout=8.0)

                self.is_casting = True
                self.cast_started.emit(device.name, file_name)

                self._start_status_polling()

            except Exception as e:
                self.is_casting = False
                logger.error(f"Erro ao transmitir para TV: {e}")
                self.error_occurred.emit(f"Falha ao transmitir para a TV: {e}")

        threading.Thread(target=_cast_thread, daemon=True).start()

    def _start_status_polling(self):
        self._stop_polling.clear()

        def _poll():
            while not self._stop_polling.is_set() and self.is_casting:
                try:
                    if self.active_chromecast and self.active_chromecast.media_controller:
                        mc = self.active_chromecast.media_controller
                        try:
                            mc.update_status()
                        except Exception:
                            pass
                        status = mc.status
                        if status:
                            state = status.player_state or "IDLE"
                            curr = float(status.current_time or 0.0)
                            dur = float(status.duration or 0.0)
                            self.status_updated.emit(state, curr, dur)

                        cast_status = self.active_chromecast.status
                        if cast_status:
                            vol = float(cast_status.volume_level or 1.0)
                            muted = bool(cast_status.volume_muted)
                            self.volume_updated.emit(vol, muted)

                except Exception:
                    pass
                time.sleep(1.0)

        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    def play(self):
        if self.active_chromecast and self.active_chromecast.media_controller:
            try:
                self.active_chromecast.media_controller.play()
            except Exception as e:
                logger.debug(f"Erro ao reproduzir: {e}")

    def pause(self):
        if self.active_chromecast and self.active_chromecast.media_controller:
            try:
                self.active_chromecast.media_controller.pause()
            except Exception as e:
                logger.debug(f"Erro ao pausar: {e}")

    def stop_cast(self):
        self._stop_polling.set()
        if self.active_chromecast and self.active_chromecast.media_controller:
            try:
                self.active_chromecast.media_controller.stop()
            except Exception:
                pass
        self.is_casting = False
        self.stream_server.clear_tokens()
        self.cast_stopped.emit()

    def seek(self, position_seconds: float):
        if self.active_chromecast and self.active_chromecast.media_controller:
            try:
                self.active_chromecast.media_controller.seek(position_seconds)
            except Exception as e:
                logger.debug(f"Erro ao avançar: {e}")

    def set_volume(self, level: float):
        if self.active_chromecast:
            try:
                self.active_chromecast.set_volume(max(0.0, min(1.0, level)))
            except Exception as e:
                logger.debug(f"Erro ao mudar volume: {e}")

    def toggle_mute(self):
        if self.active_chromecast and self.active_chromecast.status:
            try:
                curr = bool(self.active_chromecast.status.volume_muted)
                self.active_chromecast.set_volume_muted(not curr)
            except Exception as e:
                logger.debug(f"Erro ao mutar: {e}")
