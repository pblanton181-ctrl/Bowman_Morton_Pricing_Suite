import os, sys, json, time, zipfile, tempfile, subprocess, urllib.request
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox

def _parse_ver(v_str):
    parts = []
    for tok in str(v_str or "0.0.0").strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in tok if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])

def get_app_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_local_version():
    vp = os.path.join(get_app_dir(), "version.json")
    if os.path.exists(vp):
        try:
            with open(vp, "r", encoding="utf-8-sig") as f:
                return str(json.load(f).get("version", "1.0.0")).strip()
        except Exception:
            pass
    return "1.0.0"

class UpdateCheckWorker(QThread):
    update_available = Signal(dict)
    no_update = Signal(str)

    def __init__(self, manual=False, parent=None):
        super().__init__(parent)
        self.manual = manual

    def run(self):
        app_dir = get_app_dir()
        cur_ver = get_local_version()
        cfg_p = os.path.join(app_dir, "update_config.json")
        if not os.path.exists(cfg_p):
            if self.manual:
                self.no_update.emit(cur_ver)
            return
        try:
            with open(cfg_p, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
        except Exception:
            return

        remote_meta = None
        source_kind = ""

        # 1. Primary: GitHub Releases (works from anywhere over HTTPS)
        gh_url = str(cfg.get("github_version_url", "")).strip()
        if gh_url and "YOUR_GITHUB_USER" not in gh_url:
            try:
                req = urllib.request.Request(gh_url, headers={"User-Agent": "BowmanMortonUpdater/1.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    remote_meta = json.loads(resp.read().decode("utf-8"))
                    source_kind = "github"
            except Exception:
                remote_meta = None

        # 2. Fallback: Shared Server Updates Folder
        if remote_meta is None:
            upd_dir = str(cfg.get("shared_updates_dir", "")).strip()
            srv_ver_p = os.path.join(upd_dir, "version.json") if upd_dir else ""
            if srv_ver_p and os.path.exists(srv_ver_p):
                try:
                    with open(srv_ver_p, "r", encoding="utf-8-sig") as f:
                        remote_meta = json.load(f)
                        source_kind = "server"
                except Exception:
                    remote_meta = None

        if not remote_meta:
            if self.manual:
                self.no_update.emit(cur_ver)
            return

        new_ver = str(remote_meta.get("version", cur_ver)).strip()
        if _parse_ver(new_ver) > _parse_ver(cur_ver):
            remote_meta["_source_kind"] = source_kind
            remote_meta["_cfg"] = cfg
            self.update_available.emit(remote_meta)
        elif self.manual:
            self.no_update.emit(cur_ver)

def install_and_restart_update(parent_win, meta):
    import shutil
    app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else get_app_dir()
    new_ver = str(meta.get("version", "")).strip()
    zip_name = str(meta.get("zip_name") or f"BowmanMortonPricingSuite_v{new_ver}.zip")
    cfg = meta.get("_cfg", {})
    tmp_zip = os.path.join(tempfile.gettempdir(), f"bm_update_{new_ver}.zip")
    stage_dir = os.path.join(tempfile.gettempdir(), f"bm_stage_{new_ver}")

    try:
        if meta.get("_source_kind") == "github":
            url_tpl = str(cfg.get("github_zip_url_tpl", ""))
            dl_url = meta.get("download_url") or url_tpl.format(version=new_ver)
            req = urllib.request.Request(dl_url, headers={"User-Agent": "BowmanMortonUpdater/1.0"})
            with urllib.request.urlopen(req, timeout=45) as resp, open(tmp_zip, "wb") as out_f:
                out_f.write(resp.read())
        else:
            src_zip = os.path.join(str(cfg.get("shared_updates_dir", "")), zip_name)
            shutil.copy2(src_zip, tmp_zip)

        if os.path.exists(stage_dir):
            shutil.rmtree(stage_dir, ignore_errors=True)
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(stage_dir)

        entries = os.listdir(stage_dir)
        first_entry = next(iter(entries), "")
        copy_src = os.path.join(stage_dir, first_entry) if (len(entries) == 1 and os.path.isdir(os.path.join(stage_dir, first_entry))) else stage_dir

        exe_name = os.path.basename(sys.executable) if getattr(sys, "frozen", False) else "BowmanMortonPricingSuite.exe"
        bat_path = os.path.join(tempfile.gettempdir(), "bm_apply_update.bat")
        bat_lines = [
            "@echo off",
            "timeout /t 2 /nobreak > nul",
            f'xcopy /E /Y /I "{copy_src}\\*" "{app_dir}\\" > nul',
            f'start "" "{os.path.join(app_dir, exe_name)}"',
            'del "%~f0"',
        ]
        with open(bat_path, "w", encoding="utf-8") as bf:
            bf.write("\r\n".join(bat_lines))

        subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=0x08000000)
        os._exit(0)
    except Exception as ex:
        QMessageBox.critical(parent_win, "Update Failed", f"Could not install update v{new_ver}:\n{ex}")
