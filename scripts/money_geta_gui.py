"""Tkinter desktop application for the local Money-Geta workflow."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from tkinter import BOTH, END, LEFT, X, filedialog, messagebox, ttk
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
VENDORED_GTAVI = ROOT / "vendor" / "gtavi-claudecode"
APPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
APP_DIR = APPDATA / "Money-Geta"
SETTINGS_FILE = APP_DIR / "settings.json"
DEFAULT_MPT = Path(os.environ.get("MONEYPRINTERTURBO_DIR", r"C:\MoneyPrinterTurbo"))
DEFAULT_JOBS = APP_DIR / "jobs"


def load_settings() -> dict:
    data = {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "mpt_dir": str(data.get("mpt_dir") or DEFAULT_MPT),
        "gtavi_dir": str(data.get("gtavi_dir") or VENDORED_GTAVI),
        "jobs_dir": str(data.get("jobs_dir") or DEFAULT_JOBS),
    }


def save_settings(data: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(SETTINGS_FILE)


def candidate_rows(job_dir: Path) -> list[dict]:
    payload = json.loads((job_dir / "candidates.json").read_text(encoding="utf-8"))
    rows = []
    for item in payload.get("candidates", []):
        rows.append({
            "n": int(item["n"]),
            "start": item.get("start", 0),
            "end": item.get("end", 0),
            "title": str(item.get("title") or item.get("hook") or item.get("summary") or item.get("reason") or "Momento detectado"),
            "score": item.get("score", ""),
        })
    return rows



def build_campaign_payload(name, platform, sources, disclosures, permissions, credits):
    payload = {"campaign_name": name.strip(), "platform": platform.strip(),
        "permissions_confirmed": permissions is True, "credits_confirmed": credits is True,
        "sources": [x.strip() for x in sources if x.strip()],
        "required_disclosures": [x.strip() for x in disclosures if x.strip()]}
    if not payload["campaign_name"] or not payload["platform"] or not payload["sources"] or not permissions or not credits:
        raise ValueError("Completa nombre, plataforma y fuentes; confirma permisos y créditos.")
    return payload


def session_video_outputs(session_dir):
    found = {p.resolve() for p in session_dir.rglob("*.mp4") if p.is_file()}
    for manifest in session_dir.rglob("money-geta.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for raw in data.get("output_videos", []):
            p = Path(raw).expanduser()
            if p.is_file():
                found.add(p.resolve())
        raw = data.get("clip_path")
        if raw and Path(raw).expanduser().is_file():
            found.add(Path(raw).expanduser().resolve())
    return sorted(found, key=lambda p: p.name.casefold())


class MoneyGetaApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Money-Geta | Centro de procesamiento")
        self.root.geometry("1040x760")
        self.root.minsize(860, 620)
        self.settings = load_settings()
        self.events: queue.Queue = queue.Queue()
        self.current_job: Path | None = None
        self.busy = False

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Action.TButton", padding=8)

        header = ttk.Frame(root, padding=(18, 14))
        header.pack(fill=X)
        ttk.Label(header, text="MONEY-GETA", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Procesamiento local · análisis de momentos · clips verticales").pack(anchor="w", pady=(3, 0))

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill=BOTH, expand=True, padx=14, pady=(0, 12))
        self.home = ttk.Frame(self.tabs, padding=14)
        self.render = ttk.Frame(self.tabs, padding=14)
        self.config = ttk.Frame(self.tabs, padding=14)
        self.history = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(self.home, text="Analizar y cortar")
        self.tabs.add(self.render, text="Render final · MPT")
        self.tabs.add(self.config, text="Configuración")
        self.tabs.add(self.history, text="Clips y sesiones")
        self._build_home()
        self._build_render()
        self._build_config()
        self._build_history()
        self._set_status("Iniciando diagnóstico automático…")
        self.root.after(300, self.run_doctor)
        self.root.after(150, self._poll_events)

    def _build_home(self):
        self.home.columnconfigure(0, weight=1)
        ttk.Label(self.home, text="1. Elegir el material", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        source_frame = ttk.LabelFrame(self.home, text="Video local o URL autorizada", padding=10)
        source_frame.grid(row=1, column=0, sticky="ew", pady=(8, 12))
        source_frame.columnconfigure(1, weight=1)
        ttk.Label(source_frame, text="Video local").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.video_var = tk.StringVar()
        ttk.Entry(source_frame, textvariable=self.video_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(source_frame, text="Examinar…", command=self._browse_video).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(source_frame, text="URL").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.url_var = tk.StringVar()
        ttk.Entry(source_frame, textvariable=self.url_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)
        self.rights_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(source_frame, text="Confirmo que tengo autorización para descargar, editar y utilizar este material.", variable=self.rights_var).grid(row=2, column=0, columnspan=3, sticky="w", pady=(7, 2))

        actions = ttk.Frame(self.home)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.doctor_btn = ttk.Button(actions, text="Ejecutar diagnóstico", command=self.run_doctor)
        self.doctor_btn.pack(side="left")
        self.process_btn = ttk.Button(actions, text="Analizar / procesar", style="Action.TButton", command=self.start_processing)
        self.process_btn.pack(side="left", padx=8)
        ttk.Button(actions, text="Abrir carpeta de trabajos", command=self.open_jobs).pack(side="left")

        ttk.Label(self.home, text="2. Salida y diagnóstico", style="Section.TLabel").grid(row=3, column=0, sticky="w")
        self.log = tk.Text(self.home, height=18, wrap="word", font=("Consolas", 9), state="disabled")
        self.log.grid(row=4, column=0, sticky="nsew", pady=(8, 8))
        self.home.rowconfigure(4, weight=1)
        self.status_var = tk.StringVar(value="Preparando…")
        ttk.Label(self.home, textvariable=self.status_var).grid(row=5, column=0, sticky="w")


    def _build_render(self):
        self.render.columnconfigure(1, weight=1)
        ttk.Label(self.render, text="Render final con MoneyPrinterTurbo", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self.render, text="Tema del video").grid(row=1, column=0, sticky="w", pady=5)
        self.subject_var = tk.StringVar()
        ttk.Entry(self.render, textvariable=self.subject_var).grid(row=1, column=1, columnspan=2, sticky="ew")
        ttk.Label(self.render, text="Campaña").grid(row=2, column=0, sticky="w", pady=5)
        self.campaign_name_var = tk.StringVar()
        ttk.Entry(self.render, textvariable=self.campaign_name_var).grid(row=2, column=1, sticky="ew")
        self.platform_var = tk.StringVar(value="YouTube Shorts")
        ttk.Combobox(self.render, textvariable=self.platform_var, values=("YouTube Shorts","TikTok","Instagram Reels","Facebook Reels","Otra"), width=20).grid(row=2, column=2, sticky="w")
        ttk.Label(self.render, text="Videos locales").grid(row=3, column=0, sticky="nw", pady=5)
        self.render_materials = []
        self.materials_list = tk.Listbox(self.render, height=5, selectmode="extended")
        self.materials_list.grid(row=3, column=1, sticky="ew", pady=5)
        buttons = ttk.Frame(self.render)
        buttons.grid(row=3, column=2, sticky="n")
        ttk.Button(buttons, text="Agregar…", command=self._add_render_materials).pack(fill=X, pady=2)
        ttk.Button(buttons, text="Quitar", command=self._remove_render_materials).pack(fill=X, pady=2)
        ttk.Label(self.render, text="Fuentes (una por línea)").grid(row=4, column=0, sticky="nw", pady=5)
        self.sources_text = tk.Text(self.render, height=3)
        self.sources_text.grid(row=4, column=1, columnspan=2, sticky="ew")
        ttk.Label(self.render, text="Avisos requeridos (uno por línea)").grid(row=5, column=0, sticky="nw", pady=5)
        self.disclosures_text = tk.Text(self.render, height=2)
        self.disclosures_text.grid(row=5, column=1, columnspan=2, sticky="ew")
        self.permissions_var = tk.BooleanVar(value=False)
        self.credits_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.render, text="Confirmo permisos de uso de los materiales", variable=self.permissions_var).grid(row=6, column=1, columnspan=2, sticky="w")
        ttk.Checkbutton(self.render, text="Confirmo que créditos y atribuciones están completos", variable=self.credits_var).grid(row=7, column=1, columnspan=2, sticky="w")
        opts = ttk.Frame(self.render)
        opts.grid(row=8, column=0, columnspan=3, sticky="ew", pady=8)
        self.aspect_var = tk.StringVar(value="9:16")
        self.count_var = tk.StringVar(value="1")
        self.language_var = tk.StringVar(value="es")
        self.voice_var = tk.StringVar()
        ttk.Label(opts, text="Formato").pack(side=LEFT)
        ttk.Combobox(opts, textvariable=self.aspect_var, values=("9:16","16:9","1:1"), state="readonly", width=7).pack(side=LEFT, padx=5)
        ttk.Label(opts, text="Cantidad").pack(side=LEFT)
        ttk.Spinbox(opts, from_=1, to=20, textvariable=self.count_var, width=4).pack(side=LEFT, padx=5)
        ttk.Label(opts, text="Idioma").pack(side=LEFT)
        ttk.Entry(opts, textvariable=self.language_var, width=8).pack(side=LEFT, padx=5)
        ttk.Label(opts, text="Voz (opcional)").pack(side=LEFT)
        ttk.Entry(opts, textvariable=self.voice_var, width=16).pack(side=LEFT, padx=5)
        ttk.Button(self.render, text="Validar campaña y renderizar", command=self.start_render).grid(row=9, column=1, sticky="w")
        ttk.Label(self.render, text="Salida local; la publicación automática permanece deshabilitada.").grid(row=10, column=1, columnspan=2, sticky="w")

    def _add_render_materials(self):
        for raw in filedialog.askopenfilenames(filetypes=[("Videos", "*.mp4 *.mkv *.mov *.webm *.avi"), ("Todos", "*.*")]):
            p = Path(raw).resolve()
            if p not in self.render_materials:
                self.render_materials.append(p)
                self.materials_list.insert(END, str(p))

    def _remove_render_materials(self):
        for i in reversed(self.materials_list.curselection()):
            self.materials_list.delete(i)
            del self.render_materials[i]

    def start_render(self):
        if not self.save_config():
            return
        if not self.subject_var.get().strip() or not self.render_materials:
            messagebox.showwarning("Datos incompletos", "Indica el tema y agrega videos locales.")
            return
        missing = [str(p) for p in self.render_materials if not p.is_file()]
        if missing:
            messagebox.showerror("Videos no encontrados", "\n".join(missing))
            return
        try:
            count = int(self.count_var.get())
            if not 1 <= count <= 20:
                raise ValueError("Cantidad válida: de 1 a 20.")
            campaign = build_campaign_payload(self.campaign_name_var.get(), self.platform_var.get(),
                self.sources_text.get("1.0", "end").splitlines(),
                self.disclosures_text.get("1.0", "end").splitlines(),
                self.permissions_var.get(), self.credits_var.get())
        except ValueError as exc:
            messagebox.showerror("Campaña incompleta", str(exc))
            return
        campaign_dir = APP_DIR / "campaigns"
        campaign_dir.mkdir(parents=True, exist_ok=True)
        campaign_path = campaign_dir / ("campaign-" + uuid.uuid4().hex + ".json")
        campaign_path.write_text(json.dumps(campaign, ensure_ascii=False, indent=2), encoding="utf-8")
        args = ["render", "--mpt-dir", self.mpt_var.get(), "--campaign", str(campaign_path),
            "--subject", self.subject_var.get().strip(), "--materials", *[str(p) for p in self.render_materials],
            "--language", self.language_var.get().strip() or "es", "--aspect", self.aspect_var.get(),
            "--count", str(count), "--jobs-root", self.jobs_var.get()]
        if self.voice_var.get().strip():
            args.extend(["--voice", self.voice_var.get().strip()])
        self._run_async(self._command(*args), "Renderizando con MoneyPrinterTurbo…")

    def _build_config(self):
        self.config.columnconfigure(1, weight=1)
        ttk.Label(self.config, text="Rutas y almacenamiento", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        self.mpt_var = tk.StringVar(value=self.settings["mpt_dir"])
        self.gtavi_var = tk.StringVar(value=self.settings["gtavi_dir"])
        self.jobs_var = tk.StringVar(value=self.settings["jobs_dir"])
        self._path_row(1, "MoneyPrinterTurbo", self.mpt_var, self._browse_mpt)
        self._path_row(2, "GTA VI ClaudeCode", self.gtavi_var, self._browse_gtavi)
        self._path_row(3, "Carpeta de trabajos", self.jobs_var, self._browse_jobs)
        ttk.Label(self.config, text="GTA VI ClaudeCode viene integrado dentro de Money-Geta. La ruta predeterminada es la copia revisada incluida en el repositorio.").grid(row=4, column=0, columnspan=3, sticky="w", pady=(12, 4))
        ttk.Label(self.config, text="La grabación en vivo no se habilita desde esta interfaz.").grid(row=5, column=0, columnspan=3, sticky="w")
        ttk.Button(self.config, text="Guardar configuración", style="Action.TButton", command=self.save_config).grid(row=6, column=0, sticky="w", pady=18)
        ttk.Button(self.config, text="Guardar y diagnosticar", command=lambda: (self.save_config() and self.run_doctor())).grid(row=6, column=1, sticky="w", pady=18)

    def _path_row(self, row, label, variable, command):
        ttk.Label(self.config, text=label).grid(row=row, column=0, sticky="w", pady=7, padx=(0, 10))
        ttk.Entry(self.config, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=7)
        ttk.Button(self.config, text="Examinar…", command=command).grid(row=row, column=2, padx=(8, 0))

    def _build_history(self):
        self.history.columnconfigure(0, weight=1)
        self.history.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(self.history)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="Actualizar", command=self.refresh_jobs).pack(side="left")
        ttk.Button(toolbar, text="Abrir video seleccionado", command=self.open_selected_output).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Abrir carpeta del trabajo", command=self.open_selected_folder).pack(side="left")
        columns = ("stage", "name", "path")
        self.jobs_tree = ttk.Treeview(self.history, columns=columns, show="headings", height=9)
        for col, title in zip(columns, ("Estado", "Trabajo", "Ruta")):
            self.jobs_tree.heading(col, text=title)
        self.jobs_tree.column("stage", width=130, stretch=False)
        self.jobs_tree.column("name", width=220)
        self.jobs_tree.column("path", width=540)
        self.jobs_tree.grid(row=1, column=0, sticky="nsew")
        self.jobs_tree.bind("<<TreeviewSelect>>", self._job_selected)
        lower = ttk.LabelFrame(self.history, text="Candidatos del análisis seleccionado", padding=8)
        lower.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        lower.columnconfigure(0, weight=1)
        ttk.Label(self.history, text="Videos generados (clips y renders)").grid(row=3, column=0, sticky="w", pady=(10, 4))
        self.outputs = ttk.Treeview(self.history, columns=("file", "location"), show="headings", height=5)
        self.outputs.heading("file", text="Archivo")
        self.outputs.heading("location", text="Ubicación")
        self.outputs.column("file", width=260)
        self.outputs.column("location", width=650)
        self.outputs.grid(row=4, column=0, sticky="nsew")
        self.history.rowconfigure(4, weight=1)
        self.candidates = ttk.Treeview(lower, columns=("n", "time", "title", "score"), show="headings", height=5)
        for col, title in (("n", "#"), ("time", "Tiempo"), ("title", "Descripción"), ("score", "Puntuación")):
            self.candidates.heading(col, text=title)
        self.candidates.column("n", width=45, stretch=False)
        self.candidates.column("time", width=130, stretch=False)
        self.candidates.column("title", width=550)
        self.candidates.column("score", width=90, stretch=False)
        self.candidates.grid(row=0, column=0, columnspan=4, sticky="ew")
        ttk.Label(lower, text="Crédito del creador").grid(row=1, column=0, sticky="w", pady=(8, 2))
        self.credit_var = tk.StringVar()
        ttk.Entry(lower, textvariable=self.credit_var, width=24).grid(row=1, column=1, sticky="w", padx=6, pady=(8, 2))
        self.layout_var = tk.StringVar(value="blur")
        ttk.Combobox(lower, textvariable=self.layout_var, values=("blur", "fill", "facecam", "react"), state="readonly", width=12).grid(row=1, column=2, sticky="w", pady=(8, 2))
        self.caption_var = tk.StringVar(value="word")
        ttk.Combobox(lower, textvariable=self.caption_var, values=("word", "bubble", "none"), state="readonly", width=10).grid(row=1, column=3, sticky="w", pady=(8, 2))
        ttk.Button(lower, text="Crear clip del candidato", command=self.cut_selected).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _browse_video(self):
        path = filedialog.askopenfilename(filetypes=[("Videos", "*.mp4 *.mkv *.mov *.webm *.avi"), ("Todos", "*.*")])
        if path:
            self.video_var.set(path)

    def _browse_mpt(self):
        path = filedialog.askdirectory(initialdir=self.mpt_var.get() or str(DEFAULT_MPT))
        if path:
            self.mpt_var.set(path)

    def _browse_gtavi(self):
        path = filedialog.askdirectory(initialdir=self.gtavi_var.get() or str(VENDORED_GTAVI))
        if path:
            self.gtavi_var.set(path)

    def _browse_jobs(self):
        path = filedialog.askdirectory(initialdir=self.jobs_var.get() or str(DEFAULT_JOBS))
        if path:
            self.jobs_var.set(path)

    def save_config(self):
        data = {"mpt_dir": self.mpt_var.get().strip(), "gtavi_dir": self.gtavi_var.get().strip(), "jobs_dir": self.jobs_var.get().strip()}
        if not all(data.values()):
            messagebox.showerror("Configuración incompleta", "Completa las tres rutas.")
            return False
        try:
            save_settings(data)
            self.settings = data
            Path(data["jobs_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("No se pudo guardar", str(exc))
            return False
        self._append(f"Configuración guardada en {SETTINGS_FILE}")
        self._set_status("Configuración guardada.")
        return True

    def _environment(self):
        env = os.environ.copy()
        env["MONEYPRINTERTURBO_DIR"] = str(Path(self.mpt_var.get()).expanduser())
        env["GTAVI_CLAUDECODE_DIR"] = str(Path(self.gtavi_var.get()).expanduser())
        env["MONEY_GETA_JOBS_DIR"] = str(Path(self.jobs_var.get()).expanduser())
        return env

    def _command(self, *args):
        return [sys.executable, "-m", "scripts.money_geta", *map(str, args)]

    def _run_async(self, command, label):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self._set_status(label)
        env = self._environment()
        def worker():
            try:
                proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
                for line in proc.stdout:
                    self.events.put(("line", line.rstrip()))
                code = proc.wait()
                self.events.put(("done", (code, label)))
            except OSError as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def run_doctor(self):
        if not self.save_config():
            return
        self._run_async(self._command("doctor"), "Ejecutando diagnóstico de dependencias…")

    def start_processing(self):
        if not self.save_config():
            return
        url = self.url_var.get().strip()
        video = self.video_var.get().strip()
        if url:
            if not self.rights_var.get():
                messagebox.showwarning("Confirmación requerida", "Marca la casilla solo si tienes autorización para descargar y editar el material.")
                return
            args = ["process-source", "--url", url, "--confirm-rights", "--gtavi-dir", self.gtavi_var.get(), "--jobs-root", self.jobs_var.get()]
        elif video:
            if not Path(video).expanduser().is_file():
                messagebox.showerror("Video no encontrado", "Selecciona un archivo de video existente.")
                return
            args = ["analyze-video", "--source", video, "--gtavi-dir", self.gtavi_var.get(), "--jobs-root", self.jobs_var.get()]
        else:
            messagebox.showwarning("Falta el material", "Selecciona un video local o introduce una URL.")
            return
        self._run_async(self._command(*args), "Procesando material…")

    def cut_selected(self):
        selected = self.candidates.selection()
        if not selected or not self.current_job:
            messagebox.showwarning("Selecciona un candidato", "Elige primero un candidato del análisis.")
            return
        credit = self.credit_var.get().strip()
        if not credit:
            messagebox.showwarning("Crédito requerido", "Indica el creador que debe aparecer acreditado en el clip.")
            return
        number = self.candidates.item(selected[0], "values")[0]
        args = ["cut-video", "--job-dir", str(self.current_job), "--pick", number, "--layout", self.layout_var.get(), "--captions", self.caption_var.get(), "--credit", credit, "--gtavi-dir", self.gtavi_var.get()]
        self._run_async(self._command(*args), f"Creando clip #{number}…")

    def _poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "line":
                    self._append(value)
                elif kind == "done":
                    code, label = value
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self._set_status(f"{label} {'VERDE' if code == 0 else 'ROJO'} · código {code}")
                    self.refresh_jobs()
                elif kind == "error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self._append("ERROR: " + value)
                    self._set_status("Error al iniciar el proceso.")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_events)

    def _append(self, text):
        self.log.configure(state="normal")
        self.log.insert(END, text + "\n")
        self.log.see(END)
        self.log.configure(state="disabled")

    def _set_status(self, text):
        self.status_var.set(text)

    def open_jobs(self):
        path = Path(self.jobs_var.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def refresh_jobs(self):
        for item in self.jobs_tree.get_children():
            self.jobs_tree.delete(item)
        root = Path(self.jobs_var.get()).expanduser()
        if not root.is_dir():
            return
        manifests = sorted(root.rglob("money-geta.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for manifest in manifests[:100]:
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            label = data.get("source_path") or data.get("source_url") or data.get("subject") or data.get("workflow", "sesión")
            self.jobs_tree.insert("", END, iid=str(manifest.parent), values=(data.get("stage", "unknown"), label, str(manifest.parent)))

    def _job_selected(self, _event=None):
        selected = self.jobs_tree.selection()
        self.current_job = None
        for item in self.candidates.get_children():
            self.candidates.delete(item)
        if not selected:
            return
        session = Path(selected[0])
        jobs = sorted(session.rglob("candidates.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not jobs:
            return
        self.current_job = jobs[0].parent
        try:
            rows = candidate_rows(self.current_job)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self._append(f"No se pudieron leer candidatos: {exc}")
            return
        for row in rows:
            start, end = float(row["start"]), float(row["end"])
            self.candidates.insert("", END, values=(row["n"], f"{start:.1f}s – {end:.1f}s", row["title"], row["score"]))
        for output in session_video_outputs(session):
            self.outputs.insert("", END, iid=str(output), values=(output.name, str(output.parent)))

    def open_selected_output(self):
        selected = self.outputs.selection()
        if not selected:
            messagebox.showinfo("Video", "Selecciona un clip o render.")
            return
        path = Path(selected[0])
        if path.is_file():
            os.startfile(str(path))
        else:
            messagebox.showerror("Archivo no encontrado", str(path))

    def open_selected_folder(self):
        selected = self.jobs_tree.selection()
        if selected and Path(selected[0]).is_dir():
            os.startfile(selected[0])

    def open_selected_clip(self):
        selected = self.candidates.selection()
        if not selected or not self.current_job:
            messagebox.showinfo("Clip", "Selecciona un candidato.")
            return
        number = self.candidates.item(selected[0], "values")[0]
        clip = self.current_job / "edits" / f"clip_{number}.mp4"
        if clip.is_file():
            os.startfile(str(clip))
        else:
            messagebox.showinfo("Clip todavía no creado", "Primero crea el clip del candidato seleccionado.")


def main():
    root = tk.Tk()
    MoneyGetaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
