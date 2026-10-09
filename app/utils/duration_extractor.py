import os
import struct
from typing import Optional


def extract_media_duration(file_path: str) -> Optional[int]:
    """Extrai a duração em segundos de arquivos de vídeo e áudio lendo apenas os cabeçalhos.
    
    Suporta: MP4, M4V, MOV, MKV, WEBM, AVI, WAV, MP3.
    Retorna a duração inteira em segundos (ex: 3600 para 1h) ou None se não for possível determinar.
    """
    if not os.path.isfile(file_path):
        return None

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext in ('.mp4', '.m4v', '.mov'):
            return _parse_mp4_duration(file_path)
        elif ext in ('.mkv', '.webm'):
            return _parse_mkv_duration(file_path)
        elif ext == '.avi':
            return _parse_avi_duration(file_path)
        elif ext == '.wav':
            return _parse_wav_duration(file_path)
        elif ext == '.mp3':
            return _parse_mp3_duration(file_path)
    except Exception:
        pass

    # Fallback no Windows usando Shell Property se disponível
    try:
        return _parse_windows_shell_duration(file_path)
    except Exception:
        pass

    return None


def _parse_mp4_duration(file_path: str) -> Optional[int]:
    """Lê atom 'moov' -> 'mvhd' de arquivos MP4/MOV."""
    with open(file_path, 'rb') as f:
        # Percorre caixas no nível raiz (ftyp, moov, etc.)
        while True:
            header = f.read(8)
            if len(header) < 8:
                break
            size = struct.unpack('>I', header[0:4])[0]
            box_type = header[4:8]

            if size == 1:
                # 64-bit size
                ext_size = f.read(8)
                if len(ext_size) < 8:
                    break
                size = struct.unpack('>Q', ext_size)[0]
                content_size = size - 16
            else:
                content_size = size - 8

            if box_type == b'moov':
                # Lê o conteúdo do moov procurando por mvhd
                moov_bytes = f.read(min(content_size, 2 * 1024 * 1024))
                idx = moov_bytes.find(b'mvhd')
                if idx != -1:
                    mvhd_data = moov_bytes[idx + 4 : idx + 4 + 32]
                    if len(mvhd_data) >= 20:
                        version = mvhd_data[0]
                        if version == 0 and len(mvhd_data) >= 20:
                            timescale = struct.unpack('>I', mvhd_data[12:16])[0]
                            duration = struct.unpack('>I', mvhd_data[16:20])[0]
                            if timescale > 0:
                                return max(1, int(duration / timescale))
                        elif version == 1 and len(mvhd_data) >= 28:
                            timescale = struct.unpack('>I', mvhd_data[20:24])[0]
                            duration = struct.unpack('>Q', mvhd_data[24:32])[0]
                            if timescale > 0:
                                return max(1, int(duration / timescale))
                return None
            else:
                if content_size <= 0:
                    break
                f.seek(content_size, os.SEEK_CUR)

    return None


def _parse_mkv_duration(file_path: str) -> Optional[int]:
    """Lê elementos EBML Segment Info -> Duration de arquivos Matroska (MKV/WebM)."""
    with open(file_path, 'rb') as f:
        # Lê os primeiros 128KB onde normalmente se encontra o Segment Information
        data = f.read(128 * 1024)

    # Identificadores EBML
    # TimecodeScale: 0x2AD7B1
    # Duration: 0x4489
    timecode_scale = 1000000.0  # Padrão: 1ms (1.000.000 ns)

    ts_idx = data.find(b'\x2a\xd7\xb1')
    if ts_idx != -1:
        try:
            # Lê o tamanho do inteiro que segue
            val_len = data[ts_idx + 3] & 0x7F
            if val_len in (1, 2, 3, 4, 8) and ts_idx + 4 + val_len <= len(data):
                raw_ts = data[ts_idx + 4 : ts_idx + 4 + val_len]
                int_val = int.from_bytes(raw_ts, byteorder='big')
                if int_val > 0:
                    timecode_scale = float(int_val)
        except Exception:
            pass

    dur_idx = data.find(b'\x44\x89')
    if dur_idx != -1:
        try:
            # Duração em MKV é armazenada como float32 (4 bytes) ou float64 (8 bytes)
            # O tamanho do elemento EBML vem após o ID
            # 0x44 0x89 [tamanho 0x84 ou 0x88] [dados float]
            size_byte = data[dur_idx + 2]
            if size_byte in (0x84, 4):
                dur_raw = data[dur_idx + 3 : dur_idx + 7]
                if len(dur_raw) == 4:
                    raw_float = struct.unpack('>f', dur_raw)[0]
                    sec = (raw_float * timecode_scale) / 1000000000.0
                    return max(1, int(sec))
            elif size_byte in (0x88, 8):
                dur_raw = data[dur_idx + 3 : dur_idx + 11]
                if len(dur_raw) == 8:
                    raw_float = struct.unpack('>d', dur_raw)[0]
                    sec = (raw_float * timecode_scale) / 1000000000.0
                    return max(1, int(sec))
        except Exception:
            pass

    return None


def _parse_avi_duration(file_path: str) -> Optional[int]:
    """Lê header 'avih' de arquivos AVI."""
    with open(file_path, 'rb') as f:
        data = f.read(64 * 1024)

    idx = data.find(b'avih')
    if idx != -1 and idx + 4 + 32 <= len(data):
        try:
            avih_data = data[idx + 8 : idx + 8 + 48]
            microsec_per_frame = struct.unpack('<I', avih_data[0:4])[0]
            total_frames = struct.unpack('<I', avih_data[16:20])[0]
            if microsec_per_frame > 0 and total_frames > 0:
                duration_sec = int((microsec_per_frame * total_frames) / 1000000)
                return max(1, duration_sec)
        except Exception:
            pass

    return None


def _parse_wav_duration(file_path: str) -> Optional[int]:
    """Lê duração de arquivos WAV padrão RIFF."""
    with open(file_path, 'rb') as f:
        data = f.read(1024)

    if data.startswith(b'RIFF') and b'WAVE' in data[:12]:
        fmt_idx = data.find(b'fmt ')
        data_idx = data.find(b'data')
        if fmt_idx != -1 and data_idx != -1:
            try:
                byte_rate = struct.unpack('<I', data[fmt_idx + 16 : fmt_idx + 20])[0]
                data_size = struct.unpack('<I', data[data_idx + 4 : data_idx + 8])[0]
                if byte_rate > 0 and data_size > 0:
                    return max(1, int(data_size / byte_rate))
            except Exception:
                pass

    return None


def _parse_mp3_duration(file_path: str) -> Optional[int]:
    """Lê tag ID3 TLEN ou calcula estimativa através de headers MPEG/Xing."""
    file_size = os.path.getsize(file_path)
    with open(file_path, 'rb') as f:
        data = f.read(64 * 1024)

    # Verifica se tem tag ID3v2 com frame TLEN (duração em ms)
    if data.startswith(b'ID3'):
        tlen_idx = data.find(b'TLEN')
        if tlen_idx != -1:
            try:
                frame_size = struct.unpack('>I', data[tlen_idx + 4 : tlen_idx + 8])[0]
                raw_text = data[tlen_idx + 10 : tlen_idx + 10 + frame_size]
                text = raw_text.decode('utf-8', errors='ignore').strip('\x00\x01\x02\x03\r\n ')
                if text.isdigit():
                    ms = int(text)
                    if ms > 0:
                        return max(1, int(ms / 1000))
            except Exception:
                pass

    # Estimativa de MP3 padrão (128 kbps ou 192 kbps se não achar frame)
    if file_size > 0:
        return max(1, int(file_size / (16000)))  # ~128kbps approx

    return None


def _parse_windows_shell_duration(file_path: str) -> Optional[int]:
    """Fallback no Windows utilizando Shell.Application."""
    import win32com.client  # type: ignore
    shell = win32com.client.Dispatch("Shell.Application")
    folder_path = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    folder = shell.NameSpace(folder_path)
    if folder:
        item = folder.ParseName(file_name)
        if item:
            # 27 é tipicamente a propriedade de duração no Windows Explorer (HH:MM:SS)
            dur_str = folder.GetDetailsOf(item, 27)
            if dur_str and ":" in dur_str:
                parts = dur_str.split(":")
                if len(parts) == 3:
                    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                    return h * 3600 + m * 60 + s
                elif len(parts) == 2:
                    m, s = int(parts[0]), int(parts[1])
                    return m * 60 + s
    return None
