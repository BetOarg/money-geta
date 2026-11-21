"""Tkinter desktop application for the local Money-Geta workflow."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tkinter import BOTH, END, LEFT, X, filedialog, messagebox, simpledialog, ttk
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
VENDORED_GTAVI = ROOT / "vendor" / "gtavi-claudecode"
APPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
APP_DIR = APPDATA / "Money-Geta"
SETTINGS_FILE = APP_DIR / "settings.json"
DEFAULT_MPT = Path(os.environ.get("MONEYPRINTERTURBO_DIR", r"C:\MoneyPrinterTurbo"))
DEFAULT_JOBS = APP_DIR / "jobs"
DEFAULT_PROJECTS = APP_DIR / "projects"


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



def build_campaign_payload(name, platform, sources, rights_evidence, disclosures, credits,
                           permissions, credits_confirmed, no_credits_required):
    clean_sources = [x.strip() for x in sources if x.strip()]
    evidence = [x.strip() for x in rights_evidence if x.strip()]
    clean_credits = [x.strip() for x in credits if x.strip()]
    clean_disclosures = [x.strip() for x in disclosures if x.strip()]
    if not name.strip() or not platform.strip() or not clean_sources:
        raise ValueError("Completa nombre, plataforma y al menos una fuente.")
    if len(clean_sources) != len(evidence):
        raise ValueError("Debe existir una referencia de evidencia de derechos por cada fuente.")
    if not permissions or not credits_confirmed:
        raise ValueError("Confirma permisos y revisión de créditos.")
    if not clean_credits and not no_credits_required:
        raise ValueError("Indica créditos o confirma explícitamente que no son requeridos.")
    if clean_credits and no_credits_required:
        raise ValueError("No puedes agregar créditos y confirmar que no son requeridos.")
    now = datetime.now(timezone.utc).isoformat()
    campaign_id = "render-" + uuid.uuid4().hex
    project_id = "gui-" + uuid.uuid4().hex
    payload = {
        "schema_version": 1, "project_id": project_id, "campaign_id": campaign_id,
        "profile_id": "viral", "factual_claims_required": False,
        "campaign_name": name.strip(), "platform": platform.strip(), "status": "draft",
        "created_at": now, "updated_at": now,
        "sources": clean_sources,
        "source_evidence": [{"source": source, "reference": ref} for source, ref in zip(clean_sources, evidence)],
        "rights_ledger": [{"source": source, "evidence": ref, "status": "operator_attested", "attested_at": now}
                           for source, ref in zip(clean_sources, evidence)],
        "required_disclosures": clean_disclosures,
        "permissions_confirmed": True,
        "permission_attestation": {"confirmed": True, "actor": "operator", "confirmed_at": now, "source_count": len(clean_sources)},
        "credit_records": clean_credits,
        "credits_confirmed": True,
        "credit_attestation": {"confirmed": True, "actor": "operator", "confirmed_at": now,
                               "no_credits_required": bool(no_credits_required), "credit_count": len(clean_credits)},
        "review": {"status": "pending", "approved_artifact_hash": None},
        "distribution": {"mode": "draft_only", "human_approval_required": True},
    }
    return payload


def save_campaign_manifest(payload, campaigns_root: Path) -> Path:
    project_id, campaign_id = payload["project_id"], payload["campaign_id"]
    folder = campaigns_root / project_id / "campaigns" / campaign_id
    folder.mkdir(parents=True, exist_ok=False)
    target = folder / "campaign.json"
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        try:
            folder.rmdir()
        except OSError:
            pass
        raise
    return target


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
        self.qc_records: list[dict] = []
        self.qc_selected_record: dict | None = None
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
        self.projects = ttk.Frame(self.tabs, padding=14)
        self.config = ttk.Frame(self.tabs, padding=14)
        self.history = ttk.Frame(self.tabs, padding=14)
        self.qc = ttk.Frame(self.tabs, padding=14)
        self.research = ttk.Frame(self.tabs, padding=14)
        self.script = ttk.Frame(self.tabs, padding=14)
        self.images = ttk.Frame(self.tabs, padding=14)
        self.library = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(self.home, text="Analizar y cortar")
        self.tabs.add(self.render, text="Render final · MPT")
        self.tabs.add(self.projects, text="Proyectos")
        self.tabs.add(self.config, text="Configuración")
        self.tabs.add(self.history, text="Clips y sesiones")
        self.tabs.add(self.qc, text="QC y revisión")
        self.tabs.add(self.research, text="Investigación")
        self.tabs.add(self.script, text="Guion")
        self.tabs.add(self.images, text="Imágenes")
        self.tabs.add(self.library, text="Biblioteca local")
        self._build_home()
        self._build_render()
        self._build_projects()
        self._build_config()
        self._build_history()
        self._build_qc()
        self._build_research()
        self._build_script()
        self._build_image_search()
        self._build_media_library()
        self._set_status("Iniciando diagnóstico automático…")
        self.refresh_projects()
        self.refresh_research_options()
        self.refresh_qc()
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
        self.sources_text = tk.Text(self.render, height=2)
        self.sources_text.grid(row=4, column=1, columnspan=2, sticky="ew")
        ttk.Label(self.render, text="Evidencia de derechos (una referencia por fuente, mismo orden)").grid(row=5, column=0, sticky="nw", pady=5)
        self.rights_evidence_text = tk.Text(self.render, height=2)
        self.rights_evidence_text.grid(row=5, column=1, columnspan=2, sticky="ew")
        ttk.Label(self.render, text="Avisos requeridos (uno por línea)").grid(row=6, column=0, sticky="nw", pady=5)
        self.disclosures_text = tk.Text(self.render, height=2)
        self.disclosures_text.grid(row=6, column=1, columnspan=2, sticky="ew")
        ttk.Label(self.render, text="Créditos/atribuciones (uno por línea)").grid(row=7, column=0, sticky="nw", pady=5)
        self.credit_records_text = tk.Text(self.render, height=2)
        self.credit_records_text.grid(row=7, column=1, columnspan=2, sticky="ew")
        self.permissions_var = tk.BooleanVar(value=False)
        self.credits_var = tk.BooleanVar(value=False)
        self.no_credits_required_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.render, text="Confirmo permisos de uso de los materiales", variable=self.permissions_var).grid(row=8, column=1, columnspan=2, sticky="w")
        ttk.Checkbutton(self.render, text="Confirmo que créditos y atribuciones están completos", variable=self.credits_var).grid(row=9, column=1, columnspan=2, sticky="w")
        ttk.Checkbutton(self.render, text="No se requieren créditos", variable=self.no_credits_required_var).grid(row=10, column=1, columnspan=2, sticky="w")
        opts = ttk.Frame(self.render)
        opts.grid(row=11, column=0, columnspan=3, sticky="ew", pady=8)
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
        ttk.Button(self.render, text="Validar campaña y renderizar", command=self.start_render).grid(row=12, column=1, sticky="w")
        ttk.Label(self.render, text="Salida local; la publicación automática permanece deshabilitada.").grid(row=13, column=1, columnspan=2, sticky="w")

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
        if any("," in str(p) for p in self.render_materials):
            messagebox.showerror("Ruta no compatible", "MoneyPrinterTurbo usa comas como separador de materiales. Renombra o mueve los archivos a rutas sin comas.")
            return
        try:
            count = int(self.count_var.get())
            if not 1 <= count <= 20:
                raise ValueError("Cantidad válida: de 1 a 20.")
            campaign = build_campaign_payload(self.campaign_name_var.get(), self.platform_var.get(),
                self.sources_text.get("1.0", "end").splitlines(),
                self.rights_evidence_text.get("1.0", "end").splitlines(),
                self.disclosures_text.get("1.0", "end").splitlines(),
                self.credit_records_text.get("1.0", "end").splitlines(),
                self.permissions_var.get(), self.credits_var.get(), self.no_credits_required_var.get())
        except ValueError as exc:
            messagebox.showerror("Campaña incompleta", str(exc))
            return
        campaign_dir = APP_DIR / "campaigns"
        try:
            campaign_path = save_campaign_manifest(campaign, campaign_dir)
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo guardar la campaña", str(exc))
            return
        args = ["render", "--mpt-dir", self.mpt_var.get(), "--campaign", str(campaign_path),
            "--subject", self.subject_var.get().strip(), "--materials", *[str(p) for p in self.render_materials],
            "--language", self.language_var.get().strip() or "es", "--aspect", self.aspect_var.get(),
            "--count", str(count), "--jobs-root", self.jobs_var.get()]
        if self.voice_var.get().strip():
            args.extend(["--voice", self.voice_var.get().strip()])
        self._run_async(self._command(*args), "Renderizando con MoneyPrinterTurbo…")


    def _build_image_search(self):
        self.images.columnconfigure(1, weight=1)
        self.images.rowconfigure(5, weight=1)
        ttk.Label(self.images, text="Openverse · búsqueda de imágenes reutilizables", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(self.images, text="Proyecto (ID)").grid(row=1, column=0, sticky="w", pady=5)
        self.image_project_combo = ttk.Combobox(self.images, textvariable=self.research_project_var, state="readonly")
        self.image_project_combo.grid(row=1, column=1, sticky="ew", pady=5)
        self.image_project_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_research_campaigns())
        ttk.Label(self.images, text="Campaña (ID)").grid(row=2, column=0, sticky="w", pady=5)
        self.image_campaign_combo = ttk.Combobox(self.images, textvariable=self.research_campaign_var, state="readonly")
        self.image_campaign_combo.grid(row=2, column=1, sticky="ew", pady=5)
        query_frame = ttk.Frame(self.images)
        query_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Label(query_frame, text="Buscar").pack(side=LEFT)
        self.image_query_var = tk.StringVar()
        ttk.Entry(query_frame, textvariable=self.image_query_var, width=42).pack(side=LEFT, padx=6)
        ttk.Label(query_frame, text="Formato").pack(side=LEFT, padx=(8, 3))
        self.image_aspect_var = tk.StringVar(value="tall")
        ttk.Combobox(query_frame, textvariable=self.image_aspect_var, values=("tall", "wide", "square"), state="readonly", width=8).pack(side=LEFT)
        actions = ttk.Frame(self.images)
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(actions, text="Buscar imágenes", command=self.image_search_ui).pack(side=LEFT)
        ttk.Button(actions, text="Abrir fuente seleccionada", command=self.open_image_source).pack(side=LEFT, padx=6)
        self.image_download_btn = ttk.Button(actions, text="Descargar aprobada", command=self.download_image_candidate_ui, state="disabled")
        self.image_download_btn.pack(side=LEFT, padx=6)
        self.image_status_var = tk.StringVar(value="PENDIENTE · DERECHOS SIN VERIFICAR")
        ttk.Label(actions, textvariable=self.image_status_var).pack(side=LEFT, padx=8)
        ttk.Label(self.images, text="Resultados · seleccionar para ver metadatos").grid(row=5, column=0, columnspan=2, sticky="w")
        result_frame = ttk.Frame(self.images)
        result_frame.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=4)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        self.image_results_list = tk.Listbox(result_frame, height=8, exportselection=False)
        self.image_results_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.image_results_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.image_results_list.configure(yscrollcommand=scrollbar.set)
        self.image_results_list.bind("<<ListboxSelect>>", self.show_image_candidate)
        review = ttk.LabelFrame(self.images, text="Revisión de derechos · después de abrir la fuente", padding=6)
        review.grid(row=8, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Label(review, text="Revisor").grid(row=0, column=0, sticky="w")
        self.media_reviewer_var = tk.StringVar(value="Operador")
        ttk.Entry(review, textvariable=self.media_reviewer_var, width=18).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(review, text="Licencia revisada").grid(row=1, column=0, sticky="w")
        self.media_license_var = tk.StringVar()
        ttk.Entry(review, textvariable=self.media_license_var, width=34).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(review, text="Evidencia de derechos").grid(row=2, column=0, sticky="w")
        self.media_rights_evidence_var = tk.StringVar()
        ttk.Entry(review, textvariable=self.media_rights_evidence_var, width=50).grid(row=2, column=1, sticky="ew", padx=4)
        ttk.Label(review, text="Atribución").grid(row=3, column=0, sticky="w")
        self.media_attribution_var = tk.StringVar()
        ttk.Entry(review, textvariable=self.media_attribution_var, width=50).grid(row=3, column=1, sticky="ew", padx=4)
        review_actions = ttk.Frame(review)
        review_actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=3)
        self.media_approve_btn = ttk.Button(review_actions, text="Aprobar derechos", command=lambda: self.review_media_ui("approved"), state="disabled")
        self.media_approve_btn.pack(side=LEFT)
        self.media_reject_btn = ttk.Button(review_actions, text="Rechazar", command=lambda: self.review_media_ui("rejected"), state="disabled")
        self.media_reject_btn.pack(side=LEFT, padx=5)
        ttk.Label(self.images, text="Detalle/atribución · revisar licencia en la fuente original").grid(row=7, column=0, columnspan=2, sticky="w")
        self.image_details = tk.Text(self.images, height=5, wrap="word", font=("Consolas", 9), state="disabled")
        self.image_details.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(3, 4))
        self.images.rowconfigure(9, weight=1)
        self.image_candidates = []

    def image_search_ui(self):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        query = self.image_query_var.get().strip()
        project_id = self.research_project_var.get().strip()
        campaign_id = self.research_campaign_var.get().strip()
        aspect = self.image_aspect_var.get()
        if not query or len(query) > 200 or not project_id or not campaign_id:
            messagebox.showwarning("Datos incompletos", "Completa query (máximo 200 caracteres), proyecto y campaña.")
            return
        if os.environ.get("MONEY_GETA_IMAGE_SEARCH_ALLOW_REQUESTS", "").lower() != "true":
            messagebox.showwarning("Búsqueda desactivada", "Revisa las limitaciones de Openverse y activa MONEY_GETA_IMAGE_SEARCH_ALLOW_REQUESTS=true en el entorno local.")
            return
        if not messagebox.askyesno("Confirmar búsqueda", f"Se enviará la consulta a Openverse: {query}. La búsqueda no descarga archivos y sus metadatos de licencia no son verificación legal. ¿Continuar?"):
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.image_status_var.set("BUSCANDO…")
        self.image_details.configure(state="normal")
        self.image_details.delete("1.0", END)
        self.image_details.insert(END, "Buscando candidatos. Derechos: SIN VERIFICAR.")
        self.image_details.configure(state="disabled")
        def worker():
            try:
                from scripts.providers.openverse import ImageSearchConfig, search_openverse, save_image_candidates
                from scripts.media_registry import media_review_status
                config = ImageSearchConfig.from_env()
                candidates = search_openverse(query, config=config, aspect_ratio=aspect)
                saved = save_image_candidates(project_id, campaign_id, candidates)
                candidate_records = []
                for item in candidates:
                    record = item.to_dict()
                    try:
                        record["rights_status"] = media_review_status(project_id, campaign_id, item.candidate_id)
                    except Exception:
                        record["rights_status"] = "review_unavailable"
                    candidate_records.append(record)
                self.events.put(("image_search_done", {"candidates": candidate_records, "saved": saved}))
            except Exception as exc:
                self.events.put(("image_search_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def review_media_ui(self, decision):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        selection = self.image_results_list.curselection()
        if not selection or selection[0] >= len(self.image_candidates):
            messagebox.showwarning("Selecciona candidato", "Selecciona una imagen de los resultados.")
            return
        candidate = self.image_candidates[selection[0]]
        project_id = self.research_project_var.get().strip()
        campaign_id = self.research_campaign_var.get().strip()
        reviewer = self.media_reviewer_var.get().strip()
        license_text = self.media_license_var.get().strip()
        rights_evidence = self.media_rights_evidence_var.get().strip()
        attribution = self.media_attribution_var.get().strip() or candidate.get("attribution", "")
        if not project_id or not campaign_id or not reviewer:
            messagebox.showwarning("Datos incompletos", "Selecciona proyecto/campaña e indica el revisor.")
            return
        if decision == "approved" and (not license_text or not rights_evidence):
            messagebox.showwarning("Evidencia requerida", "Para aprobar, completa licencia revisada y evidencia de derechos después de abrir la fuente original.")
            return
        if not messagebox.askyesno("Confirmar revisión", f"Decisión: {decision.upper()}\nCandidato: {candidate.get('title')}\nFuente: {candidate.get('source_page_url')}\n\nConfirma que revisaste la página original y sus condiciones. Esta decisión quedará registrada localmente. ¿Continuar?"):
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.image_status_var.set("REGISTRANDO REVISIÓN…")
        def worker():
            try:
                from scripts.media_registry import review_media_candidate, check_media_candidate
                event = review_media_candidate(project_id, campaign_id, candidate["candidate_id"],
                    decision=decision, reviewer=reviewer, rights_evidence=rights_evidence,
                    reviewed_license=license_text, attribution=attribution,
                    source_reviewed=(decision == "approved"), notes="")
                passed, problems = check_media_candidate(project_id, campaign_id, candidate["candidate_id"])
                self.events.put(("media_review_done", {"event": event, "passed": passed, "problems": problems,
                    "candidate_id": candidate["candidate_id"], "decision": decision}))
            except Exception as exc:
                self.events.put(("media_review_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def download_image_candidate_ui(self):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        selection = self.image_results_list.curselection()
        if not selection or selection[0] >= len(self.image_candidates):
            messagebox.showwarning("Selecciona candidato", "Selecciona una imagen.")
            return
        candidate = self.image_candidates[selection[0]]
        if candidate.get("rights_status") != "reviewed_approved":
            messagebox.showwarning("Derechos pendientes", "Solo se descargan candidatos con revisión vigente.")
            return
        project_id = self.research_project_var.get().strip()
        campaign_id = self.research_campaign_var.get().strip()
        if not project_id or not campaign_id:
            messagebox.showwarning("Datos incompletos", "Selecciona proyecto y campaña.")
            return
        prompt = ("Descargar esta imagen localmente?\n\n" + str(candidate.get("title")) +
            "\nFuente: " + str(candidate.get("source_page_url")) +
            "\n\nSe usará la red y se guardará en media_assets. No se añadirá automáticamente al render.")
        if not messagebox.askyesno("Confirmar descarga", prompt):
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.image_download_btn.configure(state="disabled")
        self.image_status_var.set("DESCARGANDO…")
        def worker():
            try:
                from scripts.approved_media_download import download_approved_candidate
                record = download_approved_candidate(project_id, campaign_id, candidate["candidate_id"],
                    allow_network=True, confirm_download=True)
                self.events.put(("media_download_done", record))
            except Exception as exc:
                self.events.put(("media_download_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def show_image_candidate(self, _event=None):
        selection = self.image_results_list.curselection()
        if not selection or selection[0] >= len(self.image_candidates):
            return
        item = self.image_candidates[selection[0]]
        self.image_download_btn.configure(state="normal" if item.get("rights_status") == "reviewed_approved" else "disabled")
        details = {
            "title": item.get("title"), "creator": item.get("creator"),
            "license": item.get("license"), "license_version": item.get("license_version"),
            "license_url": item.get("license_url"), "creator_url": item.get("creator_url"),
            "source_page_url": item.get("source_page_url"), "attribution": item.get("attribution"),
            "dimensions": f"{item.get('width')}x{item.get('height')}", "rights_status": item.get("rights_status", "unverified").upper(),
        }
        self.image_details.configure(state="normal")
        self.image_details.delete("1.0", END)
        self.image_details.insert(END, json.dumps(details, ensure_ascii=False, indent=2))
        self.image_details.configure(state="disabled")

    def open_image_source(self):
        selection = self.image_results_list.curselection()
        if not selection or selection[0] >= len(self.image_candidates):
            messagebox.showinfo("Fuente", "Selecciona primero un resultado.")
            return
        source_url = self.image_candidates[selection[0]].get("source_page_url")
        if isinstance(source_url, str) and source_url.startswith(("https://", "http://")):
            import webbrowser
            webbrowser.open(source_url)
        else:
            messagebox.showerror("Fuente inválida", "No se puede abrir esta URL.")

    def _build_media_library(self):
        self.library.columnconfigure(0, weight=1)
        self.library.rowconfigure(2, weight=1)
        ttk.Label(self.library, text="Biblioteca multimedia local · catálogo de solo lectura", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.library, text="Filtros: usa el proyecto y campaña seleccionados en la pestaña Imágenes.").grid(row=1, column=0, sticky="w", pady=(3, 6))
        toolbar = ttk.Frame(self.library)
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.library_query_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.library_query_var, width=32).pack(side=LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Buscar", command=lambda: self.media_library_load_ui(search=True)).pack(side=LEFT)
        ttk.Button(toolbar, text="Actualizar catálogo", command=self.media_library_load_ui).pack(side=LEFT, padx=5)
        ttk.Button(toolbar, text="Verificar integridad y derechos", command=self.media_library_verify_ui).pack(side=LEFT, padx=5)
        self.library_status_var = tk.StringVar(value="PENDIENTE · catálogo sin cargar")
        ttk.Label(toolbar, textvariable=self.library_status_var).pack(side=LEFT, padx=8)
        table_frame = ttk.Frame(self.library)
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.library_tree = ttk.Treeview(table_frame, columns=("creator", "campaign", "license", "rights", "integrity"), show="tree headings", height=9)
        self.library_tree.heading("#0", text="Recurso")
        self.library_tree.heading("creator", text="Autor")
        self.library_tree.heading("campaign", text="Campaña")
        self.library_tree.heading("license", text="Licencia")
        self.library_tree.heading("rights", text="Derechos")
        self.library_tree.heading("integrity", text="SHA")
        self.library_tree.column("#0", width=240)
        self.library_tree.column("creator", width=150)
        self.library_tree.column("campaign", width=130)
        self.library_tree.column("license", width=100)
        self.library_tree.column("rights", width=140)
        self.library_tree.column("integrity", width=120)
        self.library_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.library_tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.library_tree.configure(yscrollcommand=scroll.set)
        self.library_tree.bind("<<TreeviewSelect>>", self.show_media_library_asset)
        self.library_details = tk.Text(self.library, height=6, wrap="word", font=("Consolas", 9), state="disabled")
        self.library_details.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.media_library_items = []

    def media_library_load_ui(self, search=False):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        project = self.research_project_var.get().strip() or None
        campaign = self.research_campaign_var.get().strip() or None
        query = self.library_query_var.get().strip()
        if search and not query:
            messagebox.showwarning("Búsqueda vacía", "Introduce términos para buscar en el catálogo.")
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.library_status_var.set("BUSCANDO…" if search else "ACTUALIZANDO…")
        def worker():
            try:
                from scripts.media_library import list_media_assets, search_media_assets
                items = search_media_assets(query, project_id=project, campaign_id=campaign) if search else list_media_assets(project_id=project, campaign_id=campaign)
                self.events.put(("media_library_done", items))
            except Exception as exc:
                self.events.put(("media_library_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def media_library_verify_ui(self):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        project = self.research_project_var.get().strip() or None
        campaign = self.research_campaign_var.get().strip() or None
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.library_status_var.set("VERIFICANDO…")
        def worker():
            try:
                from scripts.media_library import verify_media_library
                report = verify_media_library(project_id=project, campaign_id=campaign)
                self.events.put(("media_library_verify_done", report))
            except Exception as exc:
                self.events.put(("media_library_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def show_media_library_asset(self, _event=None):
        selection = self.library_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if index < 0 or index >= len(self.media_library_items):
            return
        item = self.media_library_items[index]
        self.library_details.configure(state="normal")
        self.library_details.delete("1.0", END)
        self.library_details.insert(END, json.dumps(item, ensure_ascii=False, indent=2))
        self.library_details.configure(state="disabled")

    def _build_script(self):
        self.script.columnconfigure(1, weight=1)
        self.script.rowconfigure(5, weight=1)
        ttk.Label(self.script, text="Guion draft-only desde fuentes capturadas", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(self.script, text="Proyecto (ID)").grid(row=1, column=0, sticky="w", pady=5)
        self.script_project_combo = ttk.Combobox(self.script, textvariable=self.research_project_var, state="readonly")
        self.script_project_combo.grid(row=1, column=1, sticky="ew", pady=5)
        self.script_project_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_research_campaigns())
        ttk.Label(self.script, text="Campaña (ID)").grid(row=2, column=0, sticky="w", pady=5)
        self.script_campaign_combo = ttk.Combobox(self.script, textvariable=self.research_campaign_var, state="readonly")
        self.script_campaign_combo.grid(row=2, column=1, sticky="ew", pady=5)
        settings = ttk.Frame(self.script)
        settings.grid(row=3, column=1, sticky="ew", pady=5)
        ttk.Label(self.script, text="Idioma").grid(row=3, column=0, sticky="w", pady=5)
        self.script_language_var = tk.StringVar(value="es-AR")
        ttk.Combobox(settings, textvariable=self.script_language_var, values=("es-AR", "en-US", "pt-BR"), state="readonly", width=10).pack(side=LEFT)
        ttk.Label(settings, text="Tokens").pack(side=LEFT, padx=(12, 4))
        self.script_tokens_var = tk.StringVar(value="2000")
        ttk.Combobox(settings, textvariable=self.script_tokens_var, values=("1000", "1500", "2000", "2500", "3000", "4000"), state="readonly", width=8).pack(side=LEFT)
        actions = ttk.Frame(self.script)
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 8))
        ttk.Button(actions, text="Actualizar proyectos/campañas", command=self.refresh_research_options).pack(side=LEFT)
        ttk.Button(actions, text="Generar guion", command=self.generate_script_ui).pack(side=LEFT, padx=8)
        ttk.Button(actions, text="Abrir draft", command=self.open_script_draft).pack(side=LEFT)
        self.script_reregister_btn = ttk.Button(actions, text="Re-registrar edición", command=self.reregister_script_ui, state="disabled")
        self.script_reregister_btn.pack(side=LEFT, padx=5)
        self.script_status_var = tk.StringVar(value="PENDIENTE")
        ttk.Label(actions, textvariable=self.script_status_var).pack(side=LEFT, padx=8)
        review = ttk.Frame(self.script)
        review.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        ttk.Label(review, text="Script ID").pack(side=LEFT)
        self.script_review_id_var = tk.StringVar(value="")
        ttk.Entry(review, textvariable=self.script_review_id_var, width=24, state="readonly").pack(side=LEFT, padx=4)
        ttk.Label(review, text="SHA-256").pack(side=LEFT)
        self.script_review_sha_var = tk.StringVar(value="")
        ttk.Entry(review, textvariable=self.script_review_sha_var, width=18, state="readonly").pack(side=LEFT, padx=4)
        ttk.Label(review, text="Revisor").pack(side=LEFT)
        self.script_reviewer_var = tk.StringVar(value="Operador")
        ttk.Entry(review, textvariable=self.script_reviewer_var, width=14).pack(side=LEFT, padx=4)
        self.script_approve_btn = ttk.Button(review, text="Aprobar", command=lambda: self.review_script_ui("approved"), state="disabled")
        self.script_approve_btn.pack(side=LEFT, padx=3)
        self.script_reject_btn = ttk.Button(review, text="Rechazar", command=lambda: self.review_script_ui("rejected"), state="disabled")
        self.script_reject_btn.pack(side=LEFT, padx=3)
        ttk.Label(self.script, text="Guion y referencias · requiere revisión humana").grid(row=6, column=0, columnspan=2, sticky="w")
        self.script_report = tk.Text(self.script, height=12, wrap="word", font=("Consolas", 9), state="disabled")
        self.script_report.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(4, 4))
        self.script.rowconfigure(7, weight=1)

    def generate_script_ui(self):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        if os.environ.get("MONEY_GETA_LLM_ALLOW_REQUESTS", "").lower() != "true":
            messagebox.showwarning("LLM desactivado", "No hay permiso de red. Revisa proveedor, modelo, cuota y costos antes de activar MONEY_GETA_LLM_ALLOW_REQUESTS=true.")
            return
        if not os.environ.get("MONEY_GETA_LLM_BASE_URL") or not os.environ.get("MONEY_GETA_LLM_MODEL"):
            messagebox.showwarning("Configuración incompleta", "Configura MONEY_GETA_LLM_BASE_URL y MONEY_GETA_LLM_MODEL en el entorno local.")
            return
        project_id = self.research_project_var.get().strip()
        campaign_id = self.research_campaign_var.get().strip()
        language = self.script_language_var.get().strip()
        try:
            max_tokens = int(self.script_tokens_var.get())
        except ValueError:
            messagebox.showerror("Tokens inválidos", "Selecciona un límite de tokens válido.")
            return
        if not project_id or not campaign_id:
            messagebox.showwarning("Selecciona campaña", "Selecciona proyecto y campaña.")
            return
        from scripts.providers.llm import LLMConfig, ProviderConfigurationError
        try:
            config = LLMConfig.from_env()
            config.validate()
            if not config.allow_requests:
                raise ProviderConfigurationError("LLM requests are disabled.")
        except ValueError as exc:
            messagebox.showerror("Configuración LLM", str(exc))
            return
        if not messagebox.askyesno("Confirmar generación", f"Se enviarán fuentes capturadas y claims al modelo {config.model}. Puede consumir cuota o generar cargos. ¿Generar el guion?"):
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.script_status_var.set("GENERANDO…")
        self.script_report.configure(state="normal")
        self.script_report.delete("1.0", END)
        self.script_report.insert(END, "Generando draft. No se aprobará ni publicará automáticamente.\\n")
        self.script_report.configure(state="disabled")
        def worker():
            try:
                from scripts.scriptwriter import draft_campaign_script
                result = draft_campaign_script(project_id, campaign_id, language=language, config=config, max_tokens=max_tokens)
                try:
                    from scripts.script_registry import register_script
                    registration = register_script(project_id, campaign_id, Path(result["report_path"]))
                    result["review_registration"] = registration
                    result["review_registration_error"] = None
                except Exception as review_exc:
                    result["review_registration"] = None
                    result["review_registration_error"] = f"{type(review_exc).__name__}: {review_exc}"
                self.events.put(("script_done", result))
            except Exception as exc:
                self.events.put(("script_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def review_script_ui(self, decision):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        script_id = self.script_review_id_var.get().strip()
        sha256 = self.script_review_sha_var.get().strip()
        reviewer = self.script_reviewer_var.get().strip()
        project_id = self.research_project_var.get().strip()
        campaign_id = self.research_campaign_var.get().strip()
        if not script_id or not sha256 or not project_id or not campaign_id or not reviewer:
            messagebox.showwarning("Revisión incompleta", "Selecciona proyecto/campaña y registra el draft antes de decidir.")
            return
        if not messagebox.askyesno("Confirmar decisión", f"Decisión: {decision.upper()}\nScript: {script_id}\nSHA-256: {sha256}\nRevisor: {reviewer}\n\nEsta decisión quedará registrada localmente. ¿Continuar?"):
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.script_status_var.set("REGISTRANDO DECISIÓN…")
        def worker():
            try:
                from scripts.script_registry import approve_script, check_script
                approve_script(project_id, campaign_id, script_id, sha256, reviewer=reviewer, decision=decision)
                passed, problems = check_script(project_id, campaign_id, script_id, sha256)
                self.events.put(("script_review_done", {"decision": decision, "passed": passed, "problems": problems}))
            except Exception as exc:
                self.events.put(("script_review_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def reregister_script_ui(self):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        path_text = getattr(self, "script_last_report_path", "")
        project_id = self.research_project_var.get().strip()
        campaign_id = self.research_campaign_var.get().strip()
        if not path_text or not Path(path_text).is_file() or not project_id or not campaign_id:
            messagebox.showwarning("Draft no disponible", "Genera o abre un draft local válido para el proyecto/campaña seleccionados.")
            return
        if not messagebox.askyesno("Validar edición", "Se volverá a validar el JSON editado y se registrará su hash. Si el contenido cambió, será una nueva versión con aprobación pendiente. ¿Continuar?"):
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.script_status_var.set("VALIDANDO EDICIÓN…")
        def worker():
            try:
                from scripts.script_registry import register_script
                result = register_script(project_id, campaign_id, Path(path_text))
                self.events.put(("script_reregister_done", result))
            except Exception as exc:
                self.events.put(("script_reregister_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def open_script_draft(self):
        if not getattr(self, "script_last_report_path", None):
            messagebox.showinfo("Draft", "Genera primero un guion.")
            return
        path = Path(self.script_last_report_path)
        if path.is_file():
            os.startfile(str(path))
        else:
            messagebox.showerror("Draft no encontrado", str(path))

    def _build_research(self):
        self.research.columnconfigure(1, weight=1)
        ttk.Label(self.research, text="Radar de descubrimiento por campaña", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(self.research, text="Proyecto (ID)").grid(row=1, column=0, sticky="w", pady=5)
        self.research_project_var = tk.StringVar()
        self.research_project_combo = ttk.Combobox(self.research, textvariable=self.research_project_var, state="readonly")
        self.research_project_combo.grid(row=1, column=1, sticky="ew", pady=5)
        self.research_project_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_research_campaigns())
        ttk.Label(self.research, text="Campaña (ID)").grid(row=2, column=0, sticky="w", pady=5)
        self.research_campaign_var = tk.StringVar()
        self.research_campaign_combo = ttk.Combobox(self.research, textvariable=self.research_campaign_var, state="readonly")
        self.research_campaign_combo.grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(self.research, text="Consultas (una por línea; máximo 10)").grid(row=3, column=0, sticky="nw", pady=5)
        self.research_queries = tk.Text(self.research, height=4, wrap="word")
        self.research_queries.grid(row=3, column=1, sticky="ew", pady=5)
        actions = ttk.Frame(self.research)
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 8))
        ttk.Button(actions, text="Actualizar proyectos/campañas", command=self.refresh_research_options).pack(side=LEFT)
        ttk.Button(actions, text="Buscar señales", command=self.run_campaign_research_ui).pack(side=LEFT, padx=8)
        self.research_status_var = tk.StringVar(value="PENDIENTE")
        ttk.Label(actions, textvariable=self.research_status_var).pack(side=LEFT, padx=8)
        ttk.Label(self.research, text="Informe · el score de descubrimiento no es popularidad ni verificación").grid(row=5, column=0, columnspan=2, sticky="w")
        self.research_output = tk.Text(self.research, height=10, wrap="word", font=("Consolas", 9), state="disabled")
        self.research_output.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=(4, 4))
        self.research.rowconfigure(6, weight=1)

    def refresh_research_options(self):
        if not hasattr(self, "research_project_combo"):
            return
        projects = []
        if DEFAULT_PROJECTS.is_dir() and not DEFAULT_PROJECTS.is_symlink():
            for manifest in sorted(DEFAULT_PROJECTS.glob("*/project.json")):
                if manifest.is_symlink() or not manifest.is_file():
                    continue
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    project_id = data.get("project_id")
                    if isinstance(project_id, str) and project_id:
                        projects.append(project_id)
                except (OSError, ValueError):
                    continue
        self.research_project_combo["values"] = projects
        self.script_project_combo["values"] = projects
        self.image_project_combo["values"] = projects
        if self.research_project_var.get() not in projects:
            self.research_project_var.set(projects[0] if projects else "")
        self.refresh_research_campaigns()

    def refresh_research_campaigns(self):
        if not hasattr(self, "research_campaign_combo"):
            return
        project_id = self.research_project_var.get().strip()
        campaigns = []
        folder = DEFAULT_PROJECTS / project_id / "campaigns" if project_id else None
        if folder and folder.is_dir() and not folder.is_symlink():
            for manifest in sorted(folder.glob("*/campaign.json")):
                if manifest.is_symlink() or not manifest.is_file():
                    continue
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    campaign_id = data.get("campaign_id")
                    if isinstance(campaign_id, str) and campaign_id:
                        campaigns.append(campaign_id)
                except (OSError, ValueError):
                    continue
        self.research_campaign_combo["values"] = campaigns
        self.script_campaign_combo["values"] = campaigns
        self.image_campaign_combo["values"] = campaigns
        if self.research_campaign_var.get() not in campaigns:
            self.research_campaign_var.set(campaigns[0] if campaigns else "")

    def run_campaign_research_ui(self):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        if os.environ.get("MONEY_GETA_SEARCH_ALLOW_REQUESTS", "").lower() != "true":
            messagebox.showwarning("Búsqueda desactivada", "La red está desactivada. Revisa proveedor, API key, cuota y costos; solo entonces habilita MONEY_GETA_SEARCH_ALLOW_REQUESTS=true en el entorno.")
            return
        if not os.environ.get("MONEY_GETA_SEARCH_PROVIDER") or not os.environ.get("MONEY_GETA_SEARCH_API_KEY"):
            messagebox.showwarning("Configuración incompleta", "Configura MONEY_GETA_SEARCH_PROVIDER y MONEY_GETA_SEARCH_API_KEY en el entorno local.")
            return
        project_id = self.research_project_var.get().strip()
        campaign_id = self.research_campaign_var.get().strip()
        queries = [line.strip() for line in self.research_queries.get("1.0", "end").splitlines() if line.strip()]
        if not project_id or not campaign_id:
            messagebox.showwarning("Selecciona campaña", "Selecciona proyecto y campaña.")
            return
        if not 1 <= len(queries) <= 10 or any(len(query) > 600 for query in queries):
            messagebox.showerror("Consultas inválidas", "Introduce entre 1 y 10 consultas de hasta 600 caracteres.")
            return
        from scripts.providers.search import SearchConfig, SearchConfigurationError
        try:
            config = SearchConfig.from_env()
            config.validate()
            if not config.allow_requests:
                raise SearchConfigurationError("Search requests are disabled.")
        except ValueError as exc:
            messagebox.showerror("Configuración de búsqueda", str(exc))
            return
        if not messagebox.askyesno("Confirmar búsqueda externa", f"Se realizarán {len(queries)} consultas a {config.provider}. Puede consumir cuota o generar cargos. ¿Continuar?"):
            return
        self.busy = True
        self.process_btn.configure(state="disabled")
        self.research_status_var.set("BUSCANDO…")
        self.research_output.configure(state="normal")
        self.research_output.delete("1.0", END)
        self.research_output.insert(END, "Consulta en curso; los leads no son métricas de popularidad ni validación factual/legal.\n")
        self.research_output.configure(state="disabled")
        def worker():
            try:
                from scripts.campaign_research import run_campaign_research
                result = run_campaign_research(project_id, campaign_id, queries, config=config)
                self.events.put(("research_done", result))
            except Exception as exc:
                self.events.put(("research_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def _build_qc(self):
        self.qc.columnconfigure(0, weight=1)
        self.qc.rowconfigure(2, weight=1)
        ttk.Label(self.qc, text="Control de calidad de artefactos registrados", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        toolbar = ttk.Frame(self.qc)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(8, 6))
        ttk.Button(toolbar, text="Actualizar", command=self.refresh_qc).pack(side=LEFT)
        ttk.Button(toolbar, text="Ejecutar QC completo", command=self.run_selected_qc).pack(side=LEFT, padx=6)
        ttk.Button(toolbar, text="Abrir video", command=self.open_qc_video).pack(side=LEFT, padx=6)
        ttk.Button(toolbar, text="Aprobar tras revisión", command=self.approve_qc_video).pack(side=LEFT)
        self.qc_tree = ttk.Treeview(self.qc, columns=("status", "file", "campaign", "hash"), show="headings", height=8)
        for col, label in (("status", "QC central"), ("file", "Video"), ("campaign", "Campaña"), ("hash", "SHA-256")):
            self.qc_tree.heading(col, text=label)
        self.qc_tree.column("status", width=190, stretch=False)
        self.qc_tree.column("file", width=260)
        self.qc_tree.column("campaign", width=170)
        self.qc_tree.column("hash", width=150, stretch=False)
        self.qc_tree.grid(row=2, column=0, sticky="nsew")
        self.qc_tree.bind("<<TreeviewSelect>>", self._qc_selected)
        subtitle = ttk.Frame(self.qc)
        subtitle.grid(row=3, column=0, sticky="ew", pady=(8, 4))
        self.qc_subtitle_var = tk.BooleanVar(value=False)
        self.qc_subtitle_path_var = tk.StringVar()
        ttk.Checkbutton(subtitle, text="Incluir QC de subtítulos", variable=self.qc_subtitle_var).pack(side=LEFT)
        ttk.Entry(subtitle, textvariable=self.qc_subtitle_path_var).pack(side=LEFT, fill=X, expand=True, padx=6)
        ttk.Button(subtitle, text="Buscar SRT/VTT…", command=self.browse_qc_subtitle).pack(side=LEFT)
        self.qc_reviewed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.qc, text="Confirmo que revisé visualmente el video completo antes de aprobar.", variable=self.qc_reviewed_var).grid(row=4, column=0, sticky="w", pady=(4, 6))
        ttk.Label(self.qc, text="Informe del artefacto seleccionado").grid(row=5, column=0, sticky="w")
        self.qc_report = tk.Text(self.qc, height=10, wrap="word", font=("Consolas", 9), state="disabled")
        self.qc_report.grid(row=6, column=0, sticky="nsew", pady=(4, 4))
        self.qc.rowconfigure(6, weight=1)

    def refresh_qc(self):
        if not hasattr(self, "qc_tree"):
            return
        from scripts.gui_qc import discover_registered_artifacts
        previous = self.qc_tree.selection()
        previous_id = previous[0] if previous else None
        for row in self.qc_tree.get_children():
            self.qc_tree.delete(row)
        records, errors = discover_registered_artifacts(APP_DIR / "campaigns", DEFAULT_PROJECTS)
        self.qc_records = records
        for error in errors:
            self._append("QC discovery warning: " + error)
        for item in records:
            central = item.get("latest_central_qc", {}).get("status", "PENDIENTE")
            self.qc_tree.insert("", END, iid=item["artifact_id"], values=(
                central, Path(item["path"]).name, Path(item["campaign_path"]).parent.name,
                str(item.get("sha256", ""))[:12]))
        if previous_id and previous_id in self.qc_tree.get_children():
            self.qc_tree.selection_set(previous_id)
        elif records:
            self.qc_tree.selection_set(records[0]["artifact_id"])
        self._qc_selected()

    def _qc_selected(self, _event=None):
        selected = self.qc_tree.selection() if hasattr(self, "qc_tree") else ()
        self.qc_selected_record = next((item for item in self.qc_records if selected and item["artifact_id"] == selected[0]), None)
        self.qc_reviewed_var.set(False)
        if not self.qc_selected_record or not hasattr(self, "qc_report"):
            return
        record = self.qc_selected_record
        details = {
            "video": record.get("path"), "campaign_manifest": record.get("campaign_path"),
            "artifact_id": record.get("artifact_id"), "sha256": record.get("sha256"),
            "latest_technical_qc": record.get("latest_qc"),
            "latest_central_qc": record.get("latest_central_qc"),
            "latest_human_decision": record.get("latest_decision"),
        }
        self.qc_report.configure(state="normal")
        self.qc_report.delete("1.0", END)
        self.qc_report.insert(END, json.dumps(details, ensure_ascii=False, indent=2, default=str))
        self.qc_report.configure(state="disabled")

    def browse_qc_subtitle(self):
        path = filedialog.askopenfilename(filetypes=[("Subtitles", "*.srt *.vtt"), ("All files", "*.*")])
        if path:
            self.qc_subtitle_path_var.set(path)
            self.qc_subtitle_var.set(True)

    def run_selected_qc(self):
        if self.busy:
            messagebox.showinfo("Proceso en curso", "Espera a que termine el proceso actual.")
            return
        record = self.qc_selected_record
        if not record:
            messagebox.showwarning("Selecciona un video", "Elige un artefacto registrado.")
            return
        subtitle = None
        if self.qc_subtitle_var.get():
            raw = self.qc_subtitle_path_var.get().strip()
            if not raw or not Path(raw).expanduser().is_file():
                messagebox.showerror("Subtítulos no encontrados", "Selecciona un archivo SRT o VTT válido.")
                return
            subtitle = Path(raw).expanduser().resolve()
        campaign = Path(record["campaign_path"])
        artifact_id, sha256 = record["artifact_id"], record["sha256"]
        self.busy = True
        self.process_btn.configure(state="disabled")
        self._set_status("Ejecutando QC técnico, perceptual y subtítulos…")
        self._append(f"QC iniciado para {Path(record['path']).name} · hash {sha256[:12]}")
        def worker():
            try:
                from scripts.gui_qc import run_registered_artifact_qc
                result = run_registered_artifact_qc(campaign, artifact_id, sha256, subtitle_path=subtitle)
                self.events.put(("qc_done", result))
            except Exception as exc:
                self.events.put(("qc_error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def open_qc_video(self):
        record = self.qc_selected_record
        if not record:
            messagebox.showinfo("Video", "Selecciona un artefacto registrado.")
            return
        path = Path(record["path"])
        if path.is_file():
            os.startfile(str(path))
        else:
            messagebox.showerror("Video no encontrado", str(path))

    def approve_qc_video(self):
        record = self.qc_selected_record
        if not record:
            messagebox.showwarning("Selecciona un video", "Elige un artefacto registrado.")
            return
        latest = record.get("latest_central_qc", {})
        if latest.get("sha256") != record.get("sha256") or latest.get("status") != "READY_FOR_HUMAN_REVIEW":
            messagebox.showerror("Aprobación bloqueada", "El QC central debe estar VERDE y coincidir con el hash actual.")
            return
        if not self.qc_reviewed_var.get():
            messagebox.showwarning("Revisión humana requerida", "Abre y revisa el video completo; luego confirma la casilla.")
            return
        reviewer = simpledialog.askstring("Revisor", "Nombre o identificador del revisor:", parent=self.root)
        if not reviewer or not reviewer.strip():
            return
        notes = simpledialog.askstring("Notas", "Notas de revisión (opcional):", parent=self.root) or ""
        if not messagebox.askyesno("Confirmar aprobación", f"¿Aprobar el video revisado con hash {record['sha256'][:12]}?"):
            return
        try:
            from scripts.artifact_registry import approve_artifact
            approve_artifact(Path(record["campaign_path"]), record["artifact_id"], record["sha256"],
                            reviewer=reviewer.strip(), decision="approved", notes=notes.strip())
            self._append(f"APROBADO POR HUMANO: {record['artifact_id']} · {record['sha256']}")
            self.refresh_qc()
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Aprobación fallida", str(exc))

    def _build_projects(self):
        self.projects.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(self.projects)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="Crear proyecto", command=self.create_project_ui).pack(side=LEFT)
        ttk.Button(toolbar, text="Crear campaña", command=self.create_campaign_ui).pack(side=LEFT, padx=8)
        ttk.Button(toolbar, text="Actualizar", command=self.refresh_projects).pack(side=LEFT)
        self.projects_tree = ttk.Treeview(self.projects, columns=("name", "profile", "status", "topic"), show="headings", height=8)
        for col, title in (("name", "Proyecto"), ("profile", "Perfil"), ("status", "Estado"), ("topic", "Tema")):
            self.projects_tree.heading(col, text=title)
        self.projects_tree.column("name", width=280)
        self.projects_tree.column("profile", width=110, stretch=False)
        self.projects_tree.column("status", width=90, stretch=False)
        self.projects_tree.column("topic", width=320)
        self.projects_tree.grid(row=1, column=0, sticky="nsew")
        self.projects.rowconfigure(1, weight=1)
        self.projects_tree.bind("<<TreeviewSelect>>", self._project_selected)
        ttk.Label(self.projects, text="Campañas del proyecto seleccionado").grid(row=2, column=0, sticky="w", pady=(10, 4))
        self.campaigns_tree = ttk.Treeview(self.projects, columns=("name", "platform", "status"), show="headings", height=6)
        for col, title in (("name", "Campaña"), ("platform", "Plataforma"), ("status", "Estado")):
            self.campaigns_tree.heading(col, text=title)
        self.campaigns_tree.grid(row=3, column=0, sticky="ew")
        ttk.Label(self.projects, text="Las campañas se crean como borradores. No se publica ni programa desde esta pestaña.").grid(row=4, column=0, sticky="w", pady=(6, 0))

    def create_project_ui(self):
        name = simpledialog.askstring("Nuevo proyecto", "Nombre del proyecto:", parent=self.root)
        if not name or not name.strip():
            return
        profile = simpledialog.askstring("Perfil temático", "Perfil: gaming, viral, news o education", initialvalue="gaming", parent=self.root)
        if not profile:
            return
        profile = profile.strip().lower()
        if profile not in {"gaming", "viral", "news", "education"}:
            messagebox.showerror("Perfil no válido", "Usa gaming, viral, news o education.")
            return
        self._run_async(self._command("projects", "create", "--name", name.strip(), "--profile", profile),
                        "Creando proyecto…")

    def create_campaign_ui(self):
        selected = self.projects_tree.selection()
        if not selected:
            messagebox.showwarning("Selecciona un proyecto", "Selecciona el proyecto al que pertenecerá la campaña.")
            return
        name = simpledialog.askstring("Nueva campaña", "Nombre de la campaña:", parent=self.root)
        if not name or not name.strip():
            return
        platform = simpledialog.askstring("Plataforma", "Destino (YouTube Shorts, TikTok, Instagram Reels, X):",
                                          initialvalue="YouTube Shorts", parent=self.root)
        if not platform or not platform.strip():
            return
        self._run_async(self._command("campaigns", "create", "--project", selected[0],
                        "--name", name.strip(), "--platform", platform.strip()),
                        "Creando borrador de campaña…")

    def refresh_projects(self):
        if not hasattr(self, "projects_tree"):
            return
        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)
        if DEFAULT_PROJECTS.is_dir():
            for manifest in sorted(DEFAULT_PROJECTS.glob("*/project.json")):
                try:
                    item = json.loads(manifest.read_text(encoding="utf-8"))
                    if item.get("schema_version") != 1:
                        continue
                    self.projects_tree.insert("", END, iid=item["project_id"],
                        values=(item.get("name", ""), item.get("profile_id", ""),
                                item.get("status", "unknown"), item.get("topic", "")))
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    self._append(f"Proyecto ignorado por manifiesto inválido: {exc}")
        self.refresh_research_options()

    def _project_selected(self, _event=None):
        self.refresh_campaigns()

    def refresh_campaigns(self):
        if not hasattr(self, "campaigns_tree"):
            return
        for item in self.campaigns_tree.get_children():
            self.campaigns_tree.delete(item)
        selected = self.projects_tree.selection()
        if not selected:
            return
        folder = DEFAULT_PROJECTS / selected[0] / "campaigns"
        if not folder.is_dir():
            return
        for manifest in sorted(folder.glob("*/campaign.json")):
            try:
                item = json.loads(manifest.read_text(encoding="utf-8"))
                if item.get("schema_version") != 1:
                    continue
                self.campaigns_tree.insert("", END, iid=item["campaign_id"],
                    values=(item.get("campaign_name", ""), item.get("platform", ""),
                            item.get("status", "unknown")))
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self._append(f"Campaña ignorada por manifiesto inválido: {exc}")

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
        ttk.Button(toolbar, text="Enviar a render MPT", command=self.send_selected_output_to_render).pack(side="left", padx=8)
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
        env["MONEY_GETA_PROJECTS_DIR"] = str(DEFAULT_PROJECTS)
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
                    self.refresh_projects()
                    self.refresh_campaigns()
                    self.refresh_research_options()
                    self.refresh_qc()
                elif kind == "image_search_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.image_candidates = value.get("candidates", [])
                    self.image_download_btn.configure(state="disabled")
                    self.media_approve_btn.configure(state="normal" if self.image_candidates else "disabled")
                    self.media_reject_btn.configure(state="normal" if self.image_candidates else "disabled")
                    self.image_results_list.delete(0, END)
                    for index, item in enumerate(self.image_candidates, start=1):
                        title = item.get("title", "Untitled")
                        creator = item.get("creator", "Unknown creator")
                        status_label = item.get("rights_status", "unverified").upper()
                        self.image_results_list.insert(END, f"{index}. {title} · {creator} · {item.get('license', 'unknown')} · {status_label}")
                    saved = value.get("saved", {})
                    self.image_status_var.set(f"{len(self.image_candidates)} candidatos · {saved.get('added', 0)} nuevos · derechos sin verificar")
                    self.image_details.configure(state="normal")
                    self.image_details.delete("1.0", END)
                    self.image_details.insert(END, f"Ledger local: {saved.get('path', '')}\\nSelecciona un resultado para revisar atribución y fuente. Verifica la licencia original antes de usarlo.")
                    self.image_details.configure(state="disabled")
                    self._append(f"OPENVERSE IMAGE SEARCH: {len(self.image_candidates)} candidates · {saved.get('path', '')}")
                elif kind == "media_review_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    passed = value.get("passed")
                    status = "RIGHTS REVIEW PASS · OPERATOR ATTESTATION" if passed else "RIGHTS REVIEW BLOCKED"
                    self.image_status_var.set(status)
                    for index, item in enumerate(self.image_candidates):
                        if item.get("candidate_id") == value.get("candidate_id"):
                            item["rights_status"] = "reviewed_approved" if passed else ("reviewed_rejected" if value.get("decision") == "rejected" else "review_blocked")
                            base_title = item.get("title", "Untitled")
                            creator = item.get("creator", "Unknown creator")
                            self.image_results_list.delete(index)
                            license_name = item.get("license", "unknown")
                            self.image_results_list.insert(index, f"{index + 1}. {base_title} · {creator} · {license_name} · {item['rights_status'].upper()}")
                    selected = self.image_results_list.curselection()
                    selected_candidate = self.image_candidates[selected[0]] if selected and selected[0] < len(self.image_candidates) else None
                    self.image_download_btn.configure(state="normal" if passed and selected_candidate and selected_candidate.get("candidate_id") == value.get("candidate_id") else "disabled")
                    self._append(f"MEDIA RIGHTS REVIEW: {value.get('decision')} · {'PASS' if passed else 'BLOCKED'} · {value.get('candidate_id')}")
                    if value.get("problems"):
                        messagebox.showwarning("Revisión", "; ".join(value["problems"]))
                elif kind == "media_library_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.media_library_items = value
                    for row in self.library_tree.get_children():
                        self.library_tree.delete(row)
                    for index, item in enumerate(value):
                        self.library_tree.insert("", "end", iid=str(index), text=item.get("title") or item.get("candidate_id"),
                            values=(item.get("creator", ""), item.get("campaign_id", ""), item.get("license", ""),
                            item.get("rights_status", ""), item.get("integrity_status", "")))
                    usable = sum(item.get("usable_for_selection") is True for item in value)
                    self.library_status_var.set(f"{len(value)} recursos · {usable} utilizables")
                    self._append(f"MEDIA LIBRARY: {len(value)} local assets · {usable} current approved and integrity-verified")
                elif kind == "media_library_verify_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    report = value
                    self.library_status_var.set(f"LIBRARY {report.get('status')} · {report.get('usable_count', 0)} utilizables · {report.get('blocked_count', 0)} bloqueados")
                    self.library_details.configure(state="normal")
                    self.library_details.delete("1.0", END)
                    self.library_details.insert(END, json.dumps(report, ensure_ascii=False, indent=2))
                    self.library_details.configure(state="disabled")
                    self._append(f"MEDIA LIBRARY VERIFY: {report.get('status')} · {report.get('asset_count', 0)} assets · {report.get('usable_count', 0)} usable")
                elif kind == "media_library_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.library_status_var.set("ROJO · ERROR DE CATÁLOGO")
                    self._append("MEDIA LIBRARY ERROR: " + value)
                    messagebox.showerror("Biblioteca local", value)
                elif kind == "media_download_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.image_status_var.set("DESCARGA VERIFICADA · VERDE")
                    self.image_details.configure(state="normal")
                    self.image_details.insert(END, "\n\nLocal: " + value.get("local_path", "") + "\nSHA-256: " + value.get("sha256", ""))
                    self.image_details.configure(state="disabled")
                    self._append(f"APPROVED IMAGE SAVED: {value.get('local_path')} · SHA256 {value.get('sha256')}")
                elif kind == "media_download_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.image_status_var.set("ROJO · DESCARGA FALLIDA")
                    self._append("MEDIA DOWNLOAD ERROR: " + value)
                    messagebox.showerror("Descarga fallida", value)
                elif kind == "media_review_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.image_status_var.set("ROJO · ERROR DE REVISIÓN")
                    self._append("MEDIA REVIEW ERROR: " + value)
                elif kind == "image_search_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.image_status_var.set("ROJO · ERROR")
                    self.image_details.configure(state="normal")
                    self.image_details.delete("1.0", END)
                    self.image_details.insert(END, value)
                    self.image_details.configure(state="disabled")
                    self._append("IMAGE SEARCH ERROR: " + value)
                elif kind == "script_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.refresh_qc()
                    self.script_status_var.set("DRAFT · REVISIÓN PENDIENTE")
                    registration = value.get("review_registration") or {}
                    self.script_review_id_var.set(registration.get("script_id", ""))
                    self.script_review_sha_var.set(registration.get("sha256", ""))
                    registered_ok = bool(registration.get("script_id") and registration.get("sha256"))
                    self.script_approve_btn.configure(state="normal" if registered_ok else "disabled")
                    self.script_reject_btn.configure(state="normal" if registered_ok else "disabled")
                    if value.get("review_registration_error"):
                        self._append("SCRIPT REGISTRATION BLOCKED: " + value["review_registration_error"])
                    self.script_last_report_path = value.get("report_path")
                    self.script_reregister_btn.configure(state="normal" if self.script_last_report_path else "disabled")
                    self.script_report.configure(state="normal")
                    self.script_report.delete("1.0", END)
                    display = {
                        "status": value.get("status"), "title": value.get("script", {}).get("title"),
                        "hook": value.get("script", {}).get("hook"), "narration": value.get("script", {}).get("narration"),
                        "scenes": value.get("script", {}).get("scenes"), "cta": value.get("script", {}).get("cta"),
                        "source_ids": value.get("source_ids"), "supported_claim_ids": value.get("supported_claim_ids"),
                        "report_path": value.get("report_path"), "approval": value.get("approval"),
                    }
                    self.script_report.insert(END, json.dumps(display, ensure_ascii=False, indent=2, default=str))
                    self.script_report.configure(state="disabled")
                    self._append(f"SCRIPT DRAFT: {value.get('script', {}).get('title', '')} · {value.get('report_path', '')}")
                elif kind == "script_reregister_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.script_review_id_var.set(value.get("script_id", ""))
                    self.script_review_sha_var.set(value.get("sha256", ""))
                    registered_ok = bool(value.get("script_id") and value.get("sha256"))
                    self.script_approve_btn.configure(state="normal" if registered_ok else "disabled")
                    self.script_reject_btn.configure(state="normal" if registered_ok else "disabled")
                    self.script_status_var.set("EDICIÓN REGISTRADA · REVISIÓN PENDIENTE" if registered_ok else "ROJO")
                    try:
                        edited_payload = json.loads(Path(self.script_last_report_path).read_text(encoding="utf-8"))
                        self.script_report.configure(state="normal")
                        self.script_report.delete("1.0", END)
                        self.script_report.insert(END, json.dumps(edited_payload, ensure_ascii=False, indent=2))
                        self.script_report.configure(state="disabled")
                    except (OSError, ValueError, TypeError) as exc:
                        self._append(f"EDITED DRAFT DISPLAY WARNING: {exc}")
                    self._append(f"SCRIPT RE-REGISTERED: {value.get('script_id')} · {value.get('sha256')}")
                elif kind == "script_reregister_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.script_status_var.set("ROJO · EDICIÓN INVALIDA")
                    self._append("SCRIPT RE-REGISTER ERROR: " + value)
                elif kind == "script_review_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.script_status_var.set("APROBADO · PASS" if value.get("passed") else "RECHAZADO/BLOQUEADO")
                    self._append(f"SCRIPT REVIEW: {value.get('decision')} · check={'PASS' if value.get('passed') else 'BLOCKED'}")
                    if value.get("problems"):
                        self.script_report.configure(state="normal")
                        self.script_report.insert(END, "\\n\\nReview check: " + "; ".join(value["problems"]))
                        self.script_report.configure(state="disabled")
                elif kind == "script_review_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.script_status_var.set("ROJO · ERROR REVISIÓN")
                    self._append("SCRIPT REVIEW ERROR: " + value)
                elif kind == "script_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.script_status_var.set("ROJO")
                    self.script_report.configure(state="normal")
                    self.script_report.delete("1.0", END)
                    self.script_report.insert(END, value)
                    self.script_report.configure(state="disabled")
                    self._append("SCRIPT ERROR: " + value)
                elif kind == "research_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.refresh_qc()
                    status = value.get("status", "failed").upper()
                    self.research_status_var.set(status)
                    display = {
                        "status": value.get("status"), "queries": value.get("queries"),
                        "results": value.get("result_count"), "unique_sources": value.get("unique_source_count"),
                        "report_path": value.get("report_path"), "provider_errors": value.get("provider_errors"),
                        "top_results": value.get("ranked_results", [])[:10],
                    }
                    self.research_output.configure(state="normal")
                    self.research_output.delete("1.0", END)
                    self.research_output.insert(END, json.dumps(display, ensure_ascii=False, indent=2, default=str))
                    self.research_output.configure(state="disabled")
                    self._append(f"RESEARCH: {status} · {value.get('unique_source_count', 0)} fuentes · {value.get('report_path', '')}")
                elif kind == "research_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.research_status_var.set("ROJO")
                    self.research_output.configure(state="normal")
                    self.research_output.delete("1.0", END)
                    self.research_output.insert(END, value)
                    self.research_output.configure(state="disabled")
                    self._append("RESEARCH ERROR: " + value)
                elif kind == "qc_done":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self.refresh_qc()
                    central = value.get("central", {})
                    qc_status = central.get("status", "FAILED")
                    label = {"READY_FOR_HUMAN_REVIEW": "VERDE", "REVIEW_REQUIRED": "REVISAR", "FAILED": "ROJO"}.get(qc_status, "ROJO")
                    self._set_status(f"QC central: {label} · {qc_status}")
                    self._append(f"QC completado para {value.get('artifact', {}).get('path', '')}: {qc_status}")
                    self.qc_report.configure(state="normal")
                    self.qc_report.delete("1.0", END)
                    self.qc_report.insert(END, json.dumps(value, ensure_ascii=False, indent=2, default=str))
                    self.qc_report.configure(state="disabled")
                    self.qc_reviewed_var.set(False)
                elif kind == "qc_error":
                    self.busy = False
                    self.process_btn.configure(state="normal")
                    self._append("QC ERROR: " + value)
                    self._set_status("QC ROJO · no se pudo completar el control.")
                    self.qc_report.configure(state="normal")
                    self.qc_report.delete("1.0", END)
                    self.qc_report.insert(END, value)
                    self.qc_report.configure(state="disabled")
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
        for item in self.outputs.get_children():
            self.outputs.delete(item)
        if not selected:
            return
        session = Path(selected[0])
        jobs = sorted(session.rglob("candidates.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if jobs:
            self.current_job = jobs[0].parent
            try:
                rows = candidate_rows(self.current_job)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self._append(f"No se pudieron leer candidatos: {exc}")
                rows = []
            for row in rows:
                start, end = float(row["start"]), float(row["end"])
                self.candidates.insert("", END, values=(row["n"], f"{start:.1f}s – {end:.1f}s", row["title"], row["score"]))
        for output in session_video_outputs(session):
            self.outputs.insert("", END, iid=str(output), values=(output.name, str(output.parent)))

    def send_selected_output_to_render(self):
        selected = self.outputs.selection()
        if not selected:
            messagebox.showinfo("Render MPT", "Selecciona primero un clip o video generado.")
            return
        path = Path(selected[0])
        if not path.is_file():
            messagebox.showerror("Archivo no encontrado", str(path))
            return
        if path not in self.render_materials:
            self.render_materials.append(path)
            self.materials_list.insert(END, str(path))
        self.tabs.select(self.render)
        self._set_status(f"Material agregado al render MPT: {path.name}")

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
