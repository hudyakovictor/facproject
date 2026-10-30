import concurrent.futures, threading, time, uuid, traceback, json
from server.config import atomic_json, ROOT


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, queue, id):
        self.queue = queue
        self.id = id

    def check(self):
        if self.queue.items[self.id].get("cancel_requested"):
            raise Cancelled()

    def update(self, progress, message, **extra):
        self.check()
        self.queue.update(
            self.id, progress=round(float(progress), 3), message=message, **extra
        )


class Queue:
    def __init__(self):
        path = ROOT / "data/jobs.json"
        self.items = json.loads(path.read_text()) if path.exists() else {}
        for job in self.items.values():
            if job["status"] in ("queued", "running"):
                job.update(status="cancelled", message="Прервано перезапуском сервера")
        self.revision = 0
        self.lock = threading.RLock()
        self.pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="atlas-cpu"
        )

    def update(self, id, **fields):
        with self.lock:
            self.items[id].update(fields)
            self.revision += 1
            atomic_json(ROOT / "data/jobs.json", self.items)

    def submit(self, kind, fn, params):
        id = uuid.uuid4().hex[:12]
        with self.lock:
            self.items[id] = {
                "id": id,
                "kind": kind,
                "params": params,
                "status": "queued",
                "progress": 0,
                "message": "В очереди",
                "created": time.time(),
                "cancel_requested": False,
            }
            self.revision += 1

        def run():
            j = Job(self, id)
            try:
                j.check()
                self.update(id, status="running", message="Запуск")
                result = fn(j)
                j.check()
                self.update(
                    id,
                    status="completed",
                    progress=1,
                    message="Готово",
                    result=result,
                    finished=time.time(),
                )
            except Cancelled:
                self.update(
                    id, status="cancelled", message="Отменено", finished=time.time()
                )
            except Exception as e:
                traceback.print_exc()
                self.update(id, status="failed", message=str(e), finished=time.time())

        self.pool.submit(run)
        return dict(self.items[id])

    def list(self):
        with self.lock:
            return [
                dict(j)
                for j in sorted(
                    self.items.values(), key=lambda j: j["created"], reverse=True
                )
            ][:30]


queue = Queue()
