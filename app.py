from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import BooleanVar, DoubleVar, IntVar, StringVar, filedialog, messagebox, ttk
import tkinter as tk

try:
    from PIL import ExifTags, Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
except ImportError as exc:
    raise SystemExit(
        "Pillow is required. Install dependencies with: pip install -r requirements.txt"
    ) from exc

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


SUPPORTED_INPUTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
APP_DIR_NAME = "AIImageMetadataCleaner"
DEFAULT_OUTPUT_DIR = Path.cwd() / "converted"


@dataclass(frozen=True)
class ConvertOptions:
    output_format: str
    output_dir: Path
    rename_pattern: str
    save_to_source_dir: bool
    open_output_dir: bool
    jpeg_quality: int
    png_compress_level: int
    overwrite: bool
    enhance_enabled: bool
    sharpness: float
    contrast: float
    color: float


def natural_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return sanitized or "image"


def config_path() -> Path:
    base_dir = Path(os.getenv("APPDATA") or Path.home())
    return base_dir / APP_DIR_NAME / "settings.json"


def load_settings() -> dict[str, str]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict[str, str]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def open_folder(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def discover_images(paths: list[str]) -> list[Path]:
    images: set[Path] = set()
    for raw in paths:
        path = Path(raw.strip()).expanduser()
        if not path.exists():
            continue
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in SUPPORTED_INPUTS:
                    images.add(child.resolve())
        elif path.is_file() and path.suffix.lower() in SUPPORTED_INPUTS:
            images.add(path.resolve())
    return sorted(images, key=natural_key)


def format_metadata_value(value: object) -> str:
    if isinstance(value, bytes):
        decoded = value.decode("utf-8", errors="replace")
        if decoded.strip("\x00").strip():
            return decoded
        return value.hex()
    if isinstance(value, (list, tuple)):
        return ", ".join(format_metadata_value(item) for item in value)
    return str(value)


def read_image_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    with Image.open(path) as image:
        for key, value in image.info.items():
            if key.lower() == "exif":
                continue
            metadata[f"info.{key}"] = format_metadata_value(value)

        exif = image.getexif()
        for tag_id, value in exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            metadata[f"exif.{tag_name}"] = format_metadata_value(value)

    return metadata


def build_output_path(source: Path, index: int, total: int, options: ConvertOptions) -> Path:
    extension = ".png" if options.output_format == "PNG" else ".jpg"
    digits = max(3, len(str(total)))
    stem = options.rename_pattern.strip()
    if stem:
        stem = stem.format(
            name=source.stem,
            index=index,
            number=str(index).zfill(digits),
            ext=extension.lstrip("."),
        )
    else:
        stem = source.stem
    stem = sanitize_filename(stem)
    output_dir = source.parent if options.save_to_source_dir else options.output_dir
    output_path = output_dir / f"{stem}{extension}"
    if options.overwrite or not output_path.exists():
        return output_path

    counter = 2
    while True:
        candidate = output_dir / f"{stem}_{counter}{extension}"
        if not candidate.exists():
            return candidate
        counter += 1


def apply_enhancements(image: Image.Image, options: ConvertOptions) -> Image.Image:
    if not options.enhance_enabled:
        return image
    result = image
    if options.sharpness != 1.0:
        result = ImageEnhance.Sharpness(result).enhance(options.sharpness)
        if options.sharpness > 1.0:
            result = result.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))
    if options.contrast != 1.0:
        result = ImageEnhance.Contrast(result).enhance(options.contrast)
    if options.color != 1.0:
        result = ImageEnhance.Color(result).enhance(options.color)
    return result


def convert_image(source: Path, output_path: Path, options: ConvertOptions) -> None:
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        image.load()
        image = apply_enhancements(image, options)

        if options.output_format == "PNG":
            if image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                image = image.convert("RGBA")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(
                output_path,
                format="PNG",
                optimize=True,
                compress_level=options.png_compress_level,
            )
            return

        if image.mode in ("RGBA", "LA", "P"):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(
            output_path,
            format="JPEG",
            quality=options.jpeg_quality,
            optimize=True,
            progressive=True,
        )


class MetadataCleanerApp:
    def __init__(self) -> None:
        root_cls = TkinterDnD.Tk if TkinterDnD else tk.Tk
        self.root = root_cls()
        self.root.title("AI Image Metadata Cleaner")
        self.root.geometry("1040x700")
        self.root.minsize(900, 580)

        self.files: list[Path] = []
        self.log_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.settings = load_settings()

        self.output_format = StringVar(value="PNG")
        self.output_dir = StringVar(value=self.settings.get("output_dir", str(DEFAULT_OUTPUT_DIR)))
        self.rename_pattern = StringVar(value="{name}_clean")
        self.save_to_source_dir = BooleanVar(value=False)
        self.open_output_dir = BooleanVar(value=False)
        self.jpeg_quality = IntVar(value=95)
        self.png_compress_level = IntVar(value=6)
        self.overwrite = BooleanVar(value=False)
        self.enhance_enabled = BooleanVar(value=False)
        self.sharpness = DoubleVar(value=1.0)
        self.contrast = DoubleVar(value=1.0)
        self.color = DoubleVar(value=1.0)
        self.status = StringVar(value="画像ファイルまたはフォルダを追加してください")
        self.progress = IntVar(value=0)

        self._build_ui()
        self._sync_output_dir_controls()
        self._setup_drop()
        self.root.after(120, self._poll_queue)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=(12, 12, 12, 8))
        toolbar.grid(row=0, column=0, sticky="ew")
        for idx in range(8):
            toolbar.columnconfigure(idx, weight=0)
        toolbar.columnconfigure(8, weight=1)

        ttk.Button(toolbar, text="ファイル追加", command=self.add_files).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(toolbar, text="フォルダ追加", command=self.add_folder).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(toolbar, text="メタデータ表示", command=self.show_selected_metadata).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(toolbar, text="選択削除", command=self.remove_selected).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(toolbar, text="一覧クリア", command=self.clear_files).grid(row=0, column=4, padx=(0, 16))
        ttk.Label(toolbar, textvariable=self.status).grid(row=0, column=8, sticky="e")

        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        file_frame = ttk.Frame(main, padding=0)
        file_frame.columnconfigure(0, weight=1)
        file_frame.rowconfigure(0, weight=1)
        main.add(file_frame, weight=3)

        self.file_list = tk.Listbox(file_frame, selectmode=tk.EXTENDED, activestyle="none")
        self.file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(file_frame, orient=tk.VERTICAL, command=self.file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scrollbar.set)

        option_frame = ttk.Frame(main, padding=(16, 0, 0, 0))
        option_frame.columnconfigure(1, weight=1)
        main.add(option_frame, weight=2)

        ttk.Label(option_frame, text="出力形式").grid(row=0, column=0, sticky="w", pady=(0, 6))
        format_box = ttk.Combobox(option_frame, textvariable=self.output_format, values=("PNG", "JPEG"), state="readonly", width=12)
        format_box.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        ttk.Label(option_frame, text="保存先").grid(row=1, column=0, sticky="w", pady=6)
        self.output_dir_entry = ttk.Entry(option_frame, textvariable=self.output_dir)
        self.output_dir_entry.grid(row=1, column=1, sticky="ew", pady=6)
        self.output_dir_button = ttk.Button(option_frame, text="参照", command=self.choose_output_dir)
        self.output_dir_button.grid(row=1, column=2, padx=(8, 0), pady=6)

        ttk.Label(option_frame, text="保存名").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(option_frame, textvariable=self.rename_pattern).grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)

        hint = ttk.Label(option_frame, text="{name}, {index}, {number}, {ext} が使えます")
        hint.grid(row=3, column=1, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Checkbutton(
            option_frame,
            text="元画像と同じフォルダに保存する",
            variable=self.save_to_source_dir,
            command=self._sync_output_dir_controls,
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(option_frame, text="変換後フォルダを開く", variable=self.open_output_dir).grid(row=5, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(option_frame, text="同名ファイルを上書き", variable=self.overwrite).grid(row=6, column=1, columnspan=2, sticky="w", pady=4)

        ttk.Label(option_frame, text="JPEG品質").grid(row=7, column=0, sticky="w", pady=(16, 6))
        ttk.Scale(option_frame, from_=70, to=100, variable=self.jpeg_quality, orient=tk.HORIZONTAL).grid(row=7, column=1, sticky="ew", pady=(16, 6))
        ttk.Label(option_frame, textvariable=self.jpeg_quality).grid(row=7, column=2, padx=(8, 0), pady=(16, 6))

        ttk.Label(option_frame, text="PNG圧縮").grid(row=8, column=0, sticky="w", pady=6)
        ttk.Scale(option_frame, from_=0, to=9, variable=self.png_compress_level, orient=tk.HORIZONTAL).grid(row=8, column=1, sticky="ew", pady=6)
        ttk.Label(option_frame, textvariable=self.png_compress_level).grid(row=8, column=2, padx=(8, 0), pady=6)

        ttk.Separator(option_frame).grid(row=9, column=0, columnspan=3, sticky="ew", pady=16)

        ttk.Checkbutton(option_frame, text="簡易画質改善を使う", variable=self.enhance_enabled).grid(row=10, column=0, columnspan=3, sticky="w", pady=4)
        self._add_slider(option_frame, 11, "シャープ", self.sharpness, 0.5, 2.0)
        self._add_slider(option_frame, 12, "コントラスト", self.contrast, 0.7, 1.5)
        self._add_slider(option_frame, 13, "彩度", self.color, 0.7, 1.5)

        ttk.Button(option_frame, text="変換開始", command=self.start_conversion).grid(row=14, column=0, columnspan=3, sticky="ew", pady=(24, 8), ipady=8)

        bottom = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        self.progressbar = ttk.Progressbar(bottom, variable=self.progress, maximum=100)
        self.progressbar.grid(row=0, column=0, sticky="ew")

    def _add_slider(self, frame: ttk.Frame, row: int, label: str, variable: DoubleVar, start: float, end: float) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Scale(frame, from_=start, to=end, variable=variable, orient=tk.HORIZONTAL).grid(row=row, column=1, sticky="ew", pady=6)
        value = ttk.Label(frame, width=4)
        value.grid(row=row, column=2, padx=(8, 0), pady=6)

        def refresh(*_: object) -> None:
            value.configure(text=f"{variable.get():.1f}")

        variable.trace_add("write", refresh)
        refresh()

    def _sync_output_dir_controls(self) -> None:
        state = "disabled" if self.save_to_source_dir.get() else "normal"
        self.output_dir_entry.configure(state=state)
        self.output_dir_button.configure(state=state)

    def _setup_drop(self) -> None:
        if not DND_FILES:
            return
        self.file_list.drop_target_register(DND_FILES)
        self.file_list.dnd_bind("<<Drop>>", self._on_drop)
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event: object) -> None:
        raw = self.root.tk.splitlist(getattr(event, "data", ""))
        self.add_paths(list(raw))

    def add_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="画像ファイルを選択",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")),
        )
        self.add_paths(list(selected))

    def add_folder(self) -> None:
        selected = filedialog.askdirectory(title="画像フォルダを選択")
        if selected:
            self.add_paths([selected])

    def add_paths(self, paths: list[str]) -> None:
        discovered = discover_images(paths)
        existing = set(self.files)
        added = [path for path in discovered if path not in existing]
        self.files.extend(added)
        self.files.sort(key=natural_key)
        self._refresh_file_list()
        self.status.set(f"{len(added)} 件追加 / 合計 {len(self.files)} 件")

    def show_selected_metadata(self) -> None:
        path = self._metadata_target()
        if not path:
            return
        try:
            metadata = read_image_metadata(path)
        except Exception as exc:
            messagebox.showerror("メタデータ読み取りエラー", str(exc))
            return
        self._open_metadata_window(path, metadata)

    def _metadata_target(self) -> Path | None:
        selected = self.file_list.curselection()
        if selected:
            return self.files[selected[0]]
        selected_file = filedialog.askopenfilename(
            title="メタデータを確認する画像を選択",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")),
        )
        return Path(selected_file) if selected_file else None

    def _open_metadata_window(self, path: Path, metadata: dict[str, str]) -> None:
        window = tk.Toplevel(self.root)
        window.title(f"メタデータ: {path.name}")
        window.geometry("760x520")
        window.minsize(560, 360)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)

        ttk.Label(window, text=str(path), padding=(10, 10, 10, 6)).grid(row=0, column=0, sticky="ew")

        text_frame = ttk.Frame(window, padding=(10, 0, 10, 10))
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        text = tk.Text(text_frame, wrap="word", height=18)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)

        if metadata:
            lines = []
            for key in sorted(metadata):
                lines.append(f"{key}: {metadata[key]}")
            text.insert("1.0", "\n\n".join(lines))
        else:
            text.insert("1.0", "メタデータはありません。")
        text.configure(state="disabled")

    def remove_selected(self) -> None:
        selected = set(self.file_list.curselection())
        if not selected:
            return
        self.files = [path for index, path in enumerate(self.files) if index not in selected]
        self._refresh_file_list()
        self.status.set(f"合計 {len(self.files)} 件")

    def clear_files(self) -> None:
        self.files.clear()
        self._refresh_file_list()
        self.progress.set(0)
        self.status.set("一覧をクリアしました")

    def choose_output_dir(self) -> None:
        selected = filedialog.askdirectory(title="保存先フォルダを選択")
        if selected:
            self.output_dir.set(selected)
            self._save_output_dir_setting()

    def _save_output_dir_setting(self) -> None:
        self.settings["output_dir"] = str(Path(self.output_dir.get()).expanduser())
        try:
            save_settings(self.settings)
        except OSError:
            pass

    def _refresh_file_list(self) -> None:
        self.file_list.delete(0, tk.END)
        for path in self.files:
            self.file_list.insert(tk.END, str(path))

    def _current_options(self) -> ConvertOptions:
        return ConvertOptions(
            output_format=self.output_format.get(),
            output_dir=Path(self.output_dir.get()).expanduser(),
            rename_pattern=self.rename_pattern.get(),
            save_to_source_dir=self.save_to_source_dir.get(),
            open_output_dir=self.open_output_dir.get(),
            jpeg_quality=int(self.jpeg_quality.get()),
            png_compress_level=int(self.png_compress_level.get()),
            overwrite=self.overwrite.get(),
            enhance_enabled=self.enhance_enabled.get(),
            sharpness=round(float(self.sharpness.get()), 2),
            contrast=round(float(self.contrast.get()), 2),
            color=round(float(self.color.get()), 2),
        )

    def start_conversion(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("変換中", "現在の変換が完了するまでお待ちください。")
            return
        if not self.files:
            messagebox.showwarning("画像がありません", "変換する画像を追加してください。")
            return
        try:
            options = self._current_options()
            if not options.save_to_source_dir:
                options.output_dir.mkdir(parents=True, exist_ok=True)
                self._save_output_dir_setting()
        except Exception as exc:
            messagebox.showerror("保存先エラー", str(exc))
            return

        files = list(self.files)
        self.progress.set(0)
        self.status.set("変換を開始しました")
        self.worker = threading.Thread(target=self._convert_worker, args=(files, options), daemon=True)
        self.worker.start()

    def _convert_worker(self, files: list[Path], options: ConvertOptions) -> None:
        errors: list[str] = []
        output_dirs: set[str] = set()
        total = len(files)
        for index, source in enumerate(files, start=1):
            try:
                output_path = build_output_path(source, index, total, options)
                convert_image(source, output_path, options)
                output_dirs.add(str(output_path.parent))
                self.log_queue.put(("status", f"{index}/{total} 変換済み: {output_path.name}"))
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                errors.append(f"{source.name}: {exc}")
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")
            finally:
                self.log_queue.put(("progress", int(index / total * 100)))
        self.log_queue.put(("done", {"errors": errors, "output_dirs": sorted(output_dirs), "open_output_dir": options.open_output_dir}))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "status":
                    self.status.set(str(payload))
                elif kind == "progress":
                    self.progress.set(int(payload))
                elif kind == "done":
                    result = payload if isinstance(payload, dict) else {}
                    errors = result.get("errors", []) if isinstance(result.get("errors", []), list) else []
                    if errors:
                        self.status.set(f"完了: エラー {len(errors)} 件")
                        if result.get("open_output_dir"):
                            self._open_output_dirs(result.get("output_dirs", []))
                        messagebox.showwarning("一部変換できませんでした", "\n".join(errors[:20]))
                    else:
                        self.status.set("変換が完了しました")
                        if result.get("open_output_dir"):
                            self._open_output_dirs(result.get("output_dirs", []))
                        messagebox.showinfo("完了", "すべての画像を変換しました。")
        except queue.Empty:
            pass
        self.root.after(120, self._poll_queue)

    def _open_output_dirs(self, output_dirs: object) -> None:
        if not isinstance(output_dirs, list):
            return
        for raw_dir in output_dirs[:5]:
            try:
                open_folder(Path(str(raw_dir)))
            except OSError as exc:
                messagebox.showwarning("フォルダを開けませんでした", str(exc))
                break

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    app = MetadataCleanerApp()
    app.run()
