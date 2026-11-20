import traceback
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)

class BackgroundTask(QRunnable):
    def __init__(self, fn, *args, pass_progress=False, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.pass_progress = pass_progress
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            if self.pass_progress:
                self.kwargs["progress_cb"] = self.signals.progress.emit
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception:
            self.signals.error.emit(traceback.format_exc())

def run_in_background(fn, *args, on_finished=None, on_error=None, on_progress=None, pass_progress=False, **kwargs):
    task = BackgroundTask(fn, *args, pass_progress=pass_progress, **kwargs)
    if on_finished is not None:
        task.signals.finished.connect(on_finished)
    if on_error is not None:
        task.signals.error.connect(on_error)
    if on_progress is not None:
        task.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(task)
    return task
