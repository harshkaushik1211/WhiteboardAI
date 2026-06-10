import asyncio
from typing import Callable, Dict, List, Optional

from models.schemas import JobStatus, PipelineStep


class JobQueue:
    def __init__(self):
        self._jobs: Dict[str, JobStatus] = {}
        self._listeners: Dict[str, List[asyncio.Queue]] = {}

    def create_job(self, job_id: str, project_id: str) -> JobStatus:
        job = JobStatus(
            job_id=job_id,
            project_id=project_id,
            step=PipelineStep.PENDING,
            progress=0.0,
            message="Job created",
        )
        self._jobs[job_id] = job
        self._listeners[job_id] = []
        return job

    def get_job(self, job_id: str) -> Optional[JobStatus]:
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        step: Optional[PipelineStep] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[JobStatus]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        if step is not None:
            job.step = step
        if progress is not None:
            job.progress = progress
        if message is not None:
            job.message = message
        if error is not None:
            job.error = error
            job.step = PipelineStep.ERROR
        self._notify(job_id, job)
        return job

    def subscribe(self, job_id: str) -> asyncio.Queue:
        if job_id not in self._listeners:
            self._listeners[job_id] = []
        q: asyncio.Queue = asyncio.Queue()
        self._listeners[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        if job_id in self._listeners:
            try:
                self._listeners[job_id].remove(queue)
            except ValueError:
                pass

    def _notify(self, job_id: str, job: JobStatus) -> None:
        for q in self._listeners.get(job_id, []):
            try:
                q.put_nowait(job.model_dump())
            except asyncio.QueueFull:
                pass

    async def run_job(
        self,
        job_id: str,
        fn: Callable,
        *args,
        **kwargs,
    ) -> None:
        try:
            await fn(job_id, *args, **kwargs)
        except Exception as e:
            self.update_job(job_id, error=str(e), message=f"Error: {e}")


job_queue = JobQueue()
