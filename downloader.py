import sys
import subprocess
import threading
import os
import shutil
import math
import re
import tempfile
import webbrowser  # ✅ NOUVEAU : pour ouvrir le lien web

# --- AUTO INSTALL DEPENDENCIES ---
def install_if_missing(package, import_name=None):
    try:
        __import__(import_name or package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_if_missing("customtkinter")
install_if_missing("yt_dlp", "yt_dlp")
install_if_missing("requests")

# --- MISE À JOUR AUTOMATIQUE DE YT-DLP ---
def update_ytdlp():
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default]"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

# --- VÉRIFICATION DE FFMPEG ---
def check_ffmpeg():
    if shutil.which("ffmpeg"):
        return True
    print("[WARNING] FFmpeg n'est pas installé. La conversion MP3/WAV et le merge MP4 échoueront.")
    print("          Windows : winget install ffmpeg")
    print("          macOS   : brew install ffmpeg")
    print("          Linux   : sudo apt install ffmpeg")
    return False

# --- FILTRAGE DES EXTRACTEURS BLACKLISTÉS (mode UNRESTRICTED) ---
_FILTERED_IES_CACHE = None

def build_filtered_extractors():
    global _FILTERED_IES_CACHE
    if _FILTERED_IES_CACHE is not None:
        return _FILTERED_IES_CACHE
    try:
        from yt_dlp.extractor import gen_extractors
    except Exception as e:
        return [], [f"<import error: {e}>"]
    all_ies = gen_extractors()
    blocked_patterns = ("knownpiracy", "knownliability", "liability")
    filtered, blocked = [], []
    for ie in all_ies:
        cls_name = type(ie).__name__.lower()
        if any(p in cls_name for p in blocked_patterns):
            blocked.append(type(ie).__name__)
            continue
        filtered.append(ie)
    _FILTERED_IES_CACHE = (filtered, blocked)
    return _FILTERED_IES_CACHE

# --- DÉTECTION SUNO ---
def is_suno_url(url):
    return "suno.com/song/" in url.lower() or "suno.ai/song/" in url.lower()

def extract_suno_id(url):
    match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', url, re.I)
    if match:
        return match.group(0)
    return url.rstrip("/").split("/")[-1].split("?")[0]

# --- SANITIZE NOM DE FICHIER ---
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)[:150].strip() or "audio"


import customtkinter as ctk
import yt_dlp
from yt_dlp.utils import UnsupportedError, DownloadError

ctk.set_appearance_mode("Dark")


class VortexMediaDownloader(ctk.CTk):
    FORMAT_VIDEO = "VIDEO (UNIVERSAL MP4)"
    FORMAT_MP3   = "AUDIO (MP3)"
    FORMAT_WAV   = "AUDIO (WAV)"

    VIDEO_QUALITIES = ["Best Available", "1080p", "720p", "480p", "360p"]
    MP3_BITRATES    = ["128", "192", "256", "320"]
    WAV_LABEL       = ["Lossless"]

    def __init__(self):
        super().__init__()

        self.title("🌀 PROJECT VORTEX // USER EXPERIENCE EXTENSION v1.6.0")
        self.geometry("750x580")
        self.configure(fg_color="#08090f")

        # ✅ NOUVEAU : URL du développeur (à modifier plus tard)
        self.DEV_URL = "https://bstudio136.github.io/mylink/" 

        self.anim_phase = 0.0
        self.spinner_idx = 0
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.downloading = False
        self.url_focused = False
        self.flash_active = False
        self.unrestricted_var = ctk.BooleanVar(value=False)
        self.sig_phase = 0.0
        self.is_hovering_sig = False  # ✅ NOUVEAU : pour gérer l'effet de survol

        self.creer_widgets()
        self.creer_menu_clic_droit()

        self.after(60,  self._anim_title_pulse)
        self.after(100, self._anim_entry_glow)
        self.after(100, self._anim_spinner)
        self.after(150, self._anim_progress_pulse)
        self.after(200, self._anim_clear_button)
        self.after(240, self._anim_signature)

    # ------------------------------------------------------------------ #
    #  ANIMATIONS
    # ------------------------------------------------------------------ #
    def _anim_title_pulse(self):
        i = (math.sin(self.anim_phase) + 1) / 2
        r = int(255 * i)
        g = int(255 * (1 - i))
        b = 204 + int(51 * i)
        try:
            self.title_lbl.configure(text_color=f"#{r:02x}{g:02x}{b:02x}")
        except Exception:
            pass
        self.anim_phase += 0.07
        self.after(60, self._anim_title_pulse)

    def _anim_entry_glow(self):
        if not self.flash_active and self.url_focused:
            i = (math.sin(self.anim_phase * 2) + 1) / 2
            color = "#00ffcc" if i > 0.5 else "#262b42"
            try:
                self.entry_url.configure(border_color=color)
            except Exception:
                pass
        self.after(100, self._anim_entry_glow)

    def _anim_spinner(self):
        if self.downloading:
            frame = self.spinner_frames[self.spinner_idx % len(self.spinner_frames)]
            try:
                self.btn_download.configure(text=f"{frame}  EXTRACTING...")
            except Exception:
                pass
            self.spinner_idx += 1
        self.after(100, self._anim_spinner)

    def _anim_progress_pulse(self):
        if self.downloading:
            i = (math.sin(self.anim_phase * 2.5) + 1) / 2
            r = int(0 + 80 * i)
            g = int(200 + 55 * (1 - i))
            b = int(200 + 55 * i)
            try:
                self.progress_bar.configure(progress_color=f"#{r:02x}{g:02x}{b:02x}")
            except Exception:
                pass
        self.after(150, self._anim_progress_pulse)

    def _anim_clear_button(self):
        try:
            if self.entry_url.get().strip():
                i = (math.sin(self.anim_phase * 1.5) + 1) / 2
                color = "#ff0055" if i > 0.4 else "#992f45"
                self.btn_clear.configure(text_color=color)
            else:
                self.btn_clear.configure(text_color="#444b66")
        except Exception:
            pass
        self.after(200, self._anim_clear_button)

    def _anim_signature(self):
        """Pulse la couleur de la signature, sauf si la souris est dessus."""
        if not self.is_hovering_sig: # ✅ NOUVEAU : on coupe l'animation au survol
            i = (math.sin(self.sig_phase) + 1) / 2
            color = f"#{int(255*i):02x}{int(80+175*(1-i)):02x}ff"
            try:
                self.signature_lbl.configure(text_color=color)
            except Exception:
                pass
            self.sig_phase += 0.08
        self.after(40, self._anim_signature)

    # ------------------------------------------------------------------ #
    #  GESTION DU LIEN DÉVELOPPEUR
    # ------------------------------------------------------------------ #
    def _open_dev_link(self, event=None):
        """Ouvre le lien du développeur dans le navigateur par défaut."""
        try:
            webbrowser.open_new_tab(self.DEV_URL)
            self.write_to_terminal(f"[SYSTEM] Opening developer link: {self.DEV_URL}", "cyan_init")
        except Exception as e:
            self.write_to_terminal(f"[ERROR] Impossible d'ouvrir le lien : {e}", "red_error")

    def _on_sig_hover_in(self, event=None):
        """Effet visuel quand la souris entre sur la signature."""
        self.is_hovering_sig = True
        try:
            self.signature_lbl.configure(text_color="#ffffff") # Devient blanc pur
            self.signature_shadow.configure(text_color="#00ffcc") # Ombre cyan
        except Exception:
            pass

    def _on_sig_hover_out(self, event=None):
        """Reprend l'animation quand la souris quitte."""
        self.is_hovering_sig = False
        try:
            self.signature_shadow.configure(text_color="#1a1a2a") # Remet l'ombre sombre
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #
    def creer_widgets(self):
        self.title_lbl = ctk.CTkLabel(
            self, text="🌀 VORTEX MEDIA EXTRACTOR",
            font=ctk.CTkFont(family="Courier", size=24, weight="bold"),
            text_color="#00ffcc",
        )
        self.title_lbl.pack(pady=(20, 5))

        self.subtitle_lbl = ctk.CTkLabel(
            self, text="AUTOMATED STREAM SCRAPER // SMART INTERFACE CORE",
            font=ctk.CTkFont(family="Courier", size=11), text_color="#525d7a",
        )
        self.subtitle_lbl.pack(pady=(0, 20))

        self.input_frame = ctk.CTkFrame(self, fg_color="#10121c", border_color="#1f2336", border_width=1)
        self.input_frame.pack(padx=30, pady=10, fill="x")

        self.search_bar_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.search_bar_frame.pack(fill="x", padx=15, pady=(15, 10))

        self.entry_url = ctk.CTkEntry(
            self.search_bar_frame,
            placeholder_text="PASTE YOUTUBE / TIKTOK / INSTAGRAM / SUNO LINK HERE...",
            font=ctk.CTkFont(size=12),
            fg_color="#08090f",
            text_color="#ffffff",
            placeholder_text_color="#444b66",
            border_color="#262b42",
            height=38,
            corner_radius=6,
        )
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_url.bind("<Button-3>", self.afficher_menu_clic_droit)
        self.entry_url.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry_url.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry_url.bind("<Return>", lambda e: self.start_download_thread())

        self.btn_paste = ctk.CTkButton(
            self.search_bar_frame, text="[ PASTE ]",
            font=ctk.CTkFont(family="Courier", size=11, weight="bold"),
            fg_color="#1f2336", text_color="#00ffcc", hover_color="#2c324d",
            width=80, height=38, corner_radius=6,
            command=self.paste_from_clipboard,
        )
        self.btn_paste.pack(side="right")

        self.btn_clear = ctk.CTkButton(
            self.search_bar_frame, text="✕",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#1f2336", text_color="#444b66", hover_color="#3a1a24",
            width=38, height=38, corner_radius=6,
            command=self.clear_url,
        )
        self.btn_clear.pack(side="right", padx=(0, 6))

        self.opt_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.opt_frame.pack(fill="x", padx=15, pady=(0, 8))

        self.format_lbl = ctk.CTkLabel(
            self.opt_frame, text="FORMAT :",
            font=ctk.CTkFont(family="Courier", size=12, weight="bold"),
            text_color="#ffffff",
        )
        self.format_lbl.pack(side="left", padx=(0, 10))

        self.format_menu = ctk.CTkOptionMenu(
            self.opt_frame,
            values=[self.FORMAT_VIDEO, self.FORMAT_MP3, self.FORMAT_WAV],
            fg_color="#1f2336", button_color="#262b42", button_hover_color="#343b59",
            dropdown_fg_color="#10121c", font=ctk.CTkFont(size=12), corner_radius=6,
            command=self.toggle_quality_menu,
        )
        self.format_menu.pack(side="left")

        self.quality_lbl = ctk.CTkLabel(
            self.opt_frame, text="QUALITY :",
            font=ctk.CTkFont(family="Courier", size=12, weight="bold"),
            text_color="#ffffff",
        )
        self.quality_lbl.pack(side="left", padx=(20, 10))

        self.quality_menu = ctk.CTkOptionMenu(
            self.opt_frame,
            values=self.VIDEO_QUALITIES,
            fg_color="#1f2336", button_color="#262b42", button_hover_color="#343b59",
            dropdown_fg_color="#10121c", font=ctk.CTkFont(size=12), corner_radius=6,
        )
        self.quality_menu.pack(side="left")

        self.btn_download = ctk.CTkButton(
            self.opt_frame, text="⚡ EXTRACT MEDIA",
            font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
            fg_color="#00ffcc", text_color="#08090f", hover_color="#00cc99",
            width=170, height=32, corner_radius=6,
            command=self.start_download_thread,
        )
        self.btn_download.pack(side="right")

        self.adv_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.adv_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.unrestricted_cb = ctk.CTkCheckBox(
            self.adv_frame,
            text="UNRESTRICTED MODE  (bypass yt-dlp blacklist)",
            variable=self.unrestricted_var,
            font=ctk.CTkFont(family="Courier", size=11, weight="bold"),
            fg_color="#ffcc00", hover_color="#ffaa00",
            text_color="#ffcc00",
            border_color="#5a4a00",
            checkbox_width=18, checkbox_height=18,
            corner_radius=4,
            command=self._on_unrestricted_toggle,
        )
        self.unrestricted_cb.pack(side="left")

        self.adv_hint_lbl = ctk.CTkLabel(
            self.adv_frame,
            text="⚠ Use at your own risk — may not work on all sites",
            font=ctk.CTkFont(family="Courier", size=10, slant="italic"),
            text_color="#525d7a",
        )
        self.adv_hint_lbl.pack(side="left", padx=(15, 0))

        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_frame.pack(padx=30, pady=5, fill="x")

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame, progress_color="#00ffcc", fg_color="#10121c", height=8
        )
        self.progress_bar.pack(fill="x", pady=(5, 5))
        self.progress_bar.set(0)

        self.txt_console = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Courier", size=11),
            fg_color="#05060a", text_color="#a9b2c3",
            border_color="#151724", border_width=1, corner_radius=6,
        )
        self.txt_console.pack(fill="both", expand=True, padx=30, pady=(5, 5))

        self.txt_console.tag_config("green_success", foreground="#00ff66")
        self.txt_console.tag_config("red_error", foreground="#ff0055")
        self.txt_console.tag_config("cyan_init", foreground="#00f0ff")
        self.txt_console.tag_config("yellow_warn", foreground="#ffcc00")
        self.txt_console.tag_config("orange_warn", foreground="#ff9900")
        self.txt_console.tag_config("magenta_suno", foreground="#ff66cc")

        self.write_to_terminal("[SYSTEM] Vortex core operational. Compatibility filter: H.264 active.")
        self.write_to_terminal("[SYSTEM] Suno support: enabled via direct CDN with browser headers.")
        self.write_to_terminal("[SYSTEM] yt-dlp will be auto-updated on next launch if needed.")
        if not shutil.which("ffmpeg"):
            self.write_to_terminal(
                "[WARNING] FFmpeg NOT FOUND. MP3/WAV conversion & MP4 merging will fail.\n"
                "          Windows: winget install ffmpeg | macOS: brew install ffmpeg | Linux: sudo apt install ffmpeg",
                "yellow_warn",
            )

        # ---------- SIGNATURE CLIQUABLE ----------
        sig_container = ctk.CTkFrame(self, fg_color="transparent", height=30)
        sig_container.pack(side="bottom", fill="x", pady=(0, 6))
        sig_container.pack_propagate(False)

        # Ombre (décalée de 1px)
        self.signature_shadow = ctk.CTkLabel(
            sig_container, text="by Bstudio136",
            font=ctk.CTkFont(family="Courier", size=12, slant="italic", underline=True),
            text_color="#1a1a2a",
            cursor="hand2" # ✅ Curseur main
        )
        self.signature_shadow.place(relx=0.5, rely=0.5, anchor="center", x=1, y=1)

        # Signature principale (animée)
        self.signature_lbl = ctk.CTkLabel(
            sig_container, text="by Bstudio136",
            font=ctk.CTkFont(family="Courier", size=11, slant="italic", underline=True),
            text_color="#ff00ff",
            cursor="hand2" # ✅ Curseur main
        )
        self.signature_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # ✅ Ajout des événements (Clic, Survol Entrant, Survol Sortant)
        for widget in (self.signature_shadow, self.signature_lbl):
            widget.bind("<Button-1>", self._open_dev_link)
            widget.bind("<Enter>", self._on_sig_hover_in)
            widget.bind("<Leave>", self._on_sig_hover_out)

    def _on_unrestricted_toggle(self):
        if self.unrestricted_var.get():
            self.write_to_terminal(
                "[UNRESTRICTED] ⚠ Mode ACTIVÉ. Les extracteurs blacklistés sont retirés.\n"
                "        ➔ yt-dlp utilisera l'extracteur générique en fallback.",
                "orange_warn",
            )
            filtered, blocked = build_filtered_extractors()
            if blocked:
                self.write_to_terminal(
                    f"[UNRESTRICTED] Extracteurs retirés ({len(blocked)}) : " + ", ".join(blocked),
                    "orange_warn",
                )
            else:
                self.write_to_terminal("[UNRESTRICTED] Aucun extracteur blacklisté détecté.", "yellow_warn")
        else:
            self.write_to_terminal("[UNRESTRICTED] Mode désactivé — comportement yt-dlp standard.", "cyan_init")

    def _on_entry_focus_in(self, _event):
        self.url_focused = True

    def _on_entry_focus_out(self, _event):
        self.url_focused = False
        try:
            self.entry_url.configure(border_color="#262b42")
        except Exception:
            pass

    def clear_url(self):
        self.entry_url.delete(0, "end")
        self.write_to_terminal("[SYSTEM] URL field cleared.", "yellow_warn")
        self.flash_active = True
        try:
            self.entry_url.configure(border_color="#ff0055")
        except Exception:
            pass
        self.after(220, self._end_flash)

    def _end_flash(self):
        self.flash_active = False
        try:
            self.entry_url.configure(border_color="#262b42")
        except Exception:
            pass

    def toggle_quality_menu(self, choice):
        if self.FORMAT_WAV in choice:
            self.quality_lbl.configure(text="BITRATE :")
            self.quality_menu.configure(state="disabled", values=self.WAV_LABEL)
            self.quality_menu.set(self.WAV_LABEL[0])
            self.write_to_terminal("[SYSTEM] WAV selected — lossless audio, bitrate locked.")
        elif self.FORMAT_MP3 in choice:
            self.quality_lbl.configure(text="BITRATE (kbps) :")
            self.quality_menu.configure(state="normal", values=self.MP3_BITRATES)
            self.quality_menu.set("320")
            self.write_to_terminal("[SYSTEM] MP3 selected — bitrate selector unlocked.")
        else:
            self.quality_lbl.configure(text="QUALITY :")
            self.quality_menu.configure(state="normal", values=self.VIDEO_QUALITIES)
            self.quality_menu.set("Best Available")
            self.write_to_terminal("[SYSTEM] Video selected — quality selector unlocked.")

    def creer_menu_clic_droit(self):
        import tkinter as tk
        self.context_menu = tk.Menu(
            self, tearoff=0, bg="#10121c", fg="#ffffff",
            activebackground="#00ffcc", activeforeground="#08090f", bd=1,
        )
        self.context_menu.add_command(label=" Coller (Paste) ", command=self.paste_from_clipboard)
        self.context_menu.add_command(label=" Vider (Clear) ", command=self.clear_url)

    def afficher_menu_clic_droit(self, event):
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def paste_from_clipboard(self):
        try:
            clipboard_content = self.clipboard_get()
            self.entry_url.delete(0, "end")
            self.entry_url.insert(0, clipboard_content)
            self.write_to_terminal("[SYSTEM] URL injected from system clipboard.")
        except Exception:
            self.write_to_terminal("[ERROR] Clipboard is empty or unreadable.", "red_error")

    def write_to_terminal(self, text, tag=None):
        self.txt_console.configure(state="normal")
        self.txt_console.insert("end", f"{text}\n", tag)
        self.txt_console.see("end")
        self.txt_console.configure(state="disabled")

    def update_progress(self, d):
        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded_bytes = d.get("downloaded_bytes", 0)
            if total_bytes > 0:
                percent = downloaded_bytes / total_bytes
                self.progress_bar.set(percent)
                speed = d.get("speed", 0)
                speed_mb = speed / 1024 / 1024 if speed else 0
                self.after(0, lambda: self.write_to_terminal(
                    f"[DOWNLOADING] {percent*100:.1f}% | Speed: {speed_mb:.2f} MB/s"))
        elif d["status"] == "finished":
            self.progress_bar.set(1.0)
            self.after(0, lambda: self.write_to_terminal(
                "[SUCCESS] File extraction complete. Finalizing...", "green_success"))

    def start_download_thread(self):
        url = self.entry_url.get().strip()
        if not url:
            self.write_to_terminal("[ERROR] URL entry field is blank.", "red_error")
            return
        if self.downloading:
            self.write_to_terminal("[WARNING] A download is already in progress.", "yellow_warn")
            return

        self.downloading = True
        self.btn_download.configure(state="disabled")
        self.progress_bar.set(0)

        if is_suno_url(url):
            self.write_to_terminal("[SYSTEM] Suno URL detected → using direct CDN extractor.", "magenta_suno")
            threading.Thread(target=self.download_suno, args=(url,), daemon=True).start()
        else:
            threading.Thread(target=self.download_media, args=(url,), daemon=True).start()

    def download_suno(self, url):
        import requests

        fmt_choice = self.format_menu.get()
        quality_choice = self.quality_menu.get()
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(download_path, exist_ok=True)

        try:
            song_id = extract_suno_id(url)
            if not song_id:
                raise ValueError("Impossible d'extraire l'ID Suno depuis l'URL.")

            self.after(0, lambda: self.write_to_terminal(
                f"[SUNO] Song ID: {song_id}", "magenta_suno"))

            cdn_url = f"https://cdn1.suno.ai/{song_id}.mp3"
            self.after(0, lambda u=cdn_url: self.write_to_terminal(
                f"[SUNO] CDN URL: {u}", "magenta_suno"))

            safe_title = song_id

            temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3", prefix="suno_", dir=download_path)
            os.close(temp_fd)

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://suno.com/",
                "Origin": "https://suno.com",
                "Accept": "audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5",
            }

            with requests.get(cdn_url, headers=headers, stream=True, timeout=60) as r:
                if r.status_code == 403:
                    raise PermissionError(
                        "Accès refusé par le CDN Suno (403). Le lien direct est bloqué. "
                        "Suno a peut-être renforcé ses protections. Essayez avec un VPN ou un autre réseau."
                    )
                if r.status_code == 404:
                    raise FileNotFoundError(
                        "Fichier introuvable sur le CDN (404). Vérifiez que la chanson est publique."
                    )
                if r.status_code != 200:
                    raise RuntimeError(f"Erreur HTTP Suno lors du téléchargement : {r.status_code}")

                total = int(r.headers.get("Content-Length", 0))
                downloaded = 0
                self.after(0, lambda: self.write_to_terminal(
                    "[DOWNLOADING] Downloading Suno audio stream...", "magenta_suno"))

                with open(temp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = downloaded / total
                                self.after(0, lambda p=pct: self.progress_bar.set(p))

            self.after(0, lambda: self.write_to_terminal(
                "[SUCCESS] Suno stream downloaded. Processing format...", "green_success"))

            if self.FORMAT_WAV in fmt_choice:
                final_path = os.path.join(download_path, f"{safe_title}.wav")
                self.after(0, lambda: self.write_to_terminal(
                    "[CONVERT] Converting MP3 source to WAV container...", "cyan_init"))
                subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_path, final_path],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            elif self.FORMAT_MP3 in fmt_choice:
                if quality_choice == "320":
                    final_path = os.path.join(download_path, f"{safe_title}.mp3")
                    os.replace(temp_path, final_path)
                else:
                    final_path = os.path.join(download_path, f"{safe_title}.mp3")
                    self.after(0, lambda q=quality_choice: self.write_to_terminal(
                        f"[CONVERT] Re-encoding MP3 to {q} kbps...", "cyan_init"))
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", temp_path, "-b:a", f"{quality_choice}k", final_path],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

            else:
                self.after(0, lambda: self.write_to_terminal(
                    "[SUNO] Video not available for Suno → falling back to MP3 320 kbps.",
                    "yellow_warn"))
                final_path = os.path.join(download_path, f"{safe_title}.mp3")
                os.replace(temp_path, final_path)

            self.progress_bar.set(1.0)
            self.after(0, lambda p=final_path: self.write_to_terminal(
                f"\n✨ [SUCCESS] SUNO TRACK SAVED ➔ {p}\n", "green_success"))

        except FileNotFoundError as e:
            self.after(0, lambda m=str(e): self.write_to_terminal(f"[SUNO ERROR] {m}", "red_error"))
        except PermissionError as e:
            self.after(0, lambda m=str(e): self.write_to_terminal(f"[SUNO ERROR] {m}", "red_error"))
        except ConnectionError as e:
            self.after(0, lambda m=str(e): self.write_to_terminal(f"[SUNO ERROR] {m}", "red_error"))
        except subprocess.CalledProcessError:
            self.after(0, lambda: self.write_to_terminal(
                "[SUNO ERROR] FFmpeg failed during conversion. Check that it is installed.",
                "red_error"))
        except Exception as e:
            self.after(0, lambda m=str(e): self.write_to_terminal(
                f"[SUNO ERROR] {m[:200]}", "red_error"))
        finally:
            self.downloading = False
            self.after(0, self._reset_download_button)

    def download_media(self, url):
        fmt_choice = self.format_menu.get()
        quality_choice = self.quality_menu.get()
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")

        ydl_opts = {
            "progress_hooks": [self.update_progress],
            "outtmpl": os.path.join(download_path, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "extractor_args": {
                "youtube": {
                    "player_client": ["android"],
                }
            },
        }

        if self.unrestricted_var.get():
            filtered, blocked = build_filtered_extractors()
            if filtered:
                ydl_opts["ies"] = filtered
                self.after(0, lambda: self.write_to_terminal(
                    f"[UNRESTRICTED] Using {len(filtered)} extractor(s) ({len(blocked)} removed).",
                    "orange_warn"))
            else:
                self.after(0, lambda: self.write_to_terminal(
                    "[UNRESTRICTED] Filtered list empty — fallback default.", "red_error"))

        if self.FORMAT_WAV in fmt_choice:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}]
            self.after(0, lambda: self.write_to_terminal(
                "[INIT] Requesting audio stream → WAV (lossless)...", "cyan_init"))

        elif self.FORMAT_MP3 in fmt_choice:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality_choice,
            }]
            self.after(0, lambda: self.write_to_terminal(
                f"[INIT] Requesting audio stream → MP3 ({quality_choice} kbps)...", "cyan_init"))

        else:
            ydl_opts["merge_output_format"] = "mp4"
            if quality_choice == "Best Available":
                ydl_opts["format"] = "bestvideo[vcodec^=avc]+bestaudio[ext=m4a]/best[vcodec^=avc]/best"
            else:
                height = quality_choice.replace("p", "")
                ydl_opts["format"] = (
                    f"bestvideo[height<={height}][vcodec^=avc]+bestaudio[ext=m4a]"
                    f"/best[height<={height}]/best"
                )
            self.after(0, lambda: self.write_to_terminal(
                f"[INIT] Requesting H.264 stream ({quality_choice})...", "cyan_init"))

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self.after(0, lambda: self.write_to_terminal(
                f"\n✨ [SUCCESS] FILE SAVED ➔ {download_path}\n", "green_success"))

        except DownloadError as e:
            err_msg = str(e)
            if "[Liability]" in err_msg or "[Piracy]" in err_msg:
                if self.unrestricted_var.get():
                    self.after(0, lambda: self.write_to_terminal(
                        "[ERROR] Site bloqué même en UNRESTRICTED.\n"
                        "        ➔ Essayez un plugin tiers ou un fork de yt-dlp.\n"
                        "        ➔ Pour Suno, le support natif est actif via le CDN direct.",
                        "red_error"))
                else:
                    self.after(0, lambda: self.write_to_terminal(
                        "[ERROR] Site volontairement NON SUPPORTÉ par yt-dlp.\n"
                        "        ➔ Activez UNRESTRICTED (case jaune) OU utilisez un lien Suno natif.",
                        "red_error"))
            elif "403" in err_msg or "Forbidden" in err_msg:
                self.after(0, lambda: self.write_to_terminal(
                    "[ERROR] HTTP 403 Forbidden. Changez de réseau, VPN, ou mettez à jour yt-dlp.",
                    "red_error"))
            elif ("ffmpeg" in err_msg.lower()
                  or "postprocessing" in err_msg.lower()
                  or "post-processor" in err_msg.lower()):
                self.after(0, lambda: self.write_to_terminal(
                    "[ERROR] FFmpeg manquant ou erreur de conversion.\n"
                    "        ➔ winget install ffmpeg | brew install ffmpeg | sudo apt install ffmpeg",
                    "red_error"))
            elif "Unsupported URL" in err_msg:
                self.after(0, lambda: self.write_to_terminal(
                    "[ERROR] URL non supportée (aucun extracteur).", "red_error"))
            elif "is not a valid URL" in err_msg:
                self.after(0, lambda: self.write_to_terminal(
                    "[ERROR] Format d'URL invalide.", "red_error"))
            elif "Private video" in err_msg or "login" in err_msg.lower():
                self.after(0, lambda: self.write_to_terminal(
                    "[ERROR] Contenu privé ou authentification requise.", "red_error"))
            else:
                self.after(0, lambda: self.write_to_terminal(
                    f"[DOWNLOAD ERROR] {err_msg[:200]}", "red_error"))

        except UnsupportedError:
            self.after(0, lambda: self.write_to_terminal(
                "[ERROR] Site NON SUPPORTÉ par le core yt-dlp.\n"
                "        ➔ Pour Suno, le support natif est actif via le CDN direct.",
                "red_error"))

        except Exception as e:
            self.after(0, lambda: self.write_to_terminal(
                f"[CRITICAL ERROR] {str(e)[:200]}", "red_error"))

        finally:
            self.downloading = False
            self.after(0, self._reset_download_button)

    def _reset_download_button(self):
        try:
            self.btn_download.configure(state="normal", text="⚡ EXTRACT MEDIA")
            self.progress_bar.configure(progress_color="#00ffcc")
        except Exception:
            pass


# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    print("Vérification de FFmpeg...")
    check_ffmpeg()
    print("Mise à jour de yt-dlp...")
    update_ytdlp()
    print("Lancement de l'application...")
    app = VortexMediaDownloader()
    app.mainloop()