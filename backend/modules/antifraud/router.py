"""Small registration surface; analysis stays inside this module."""
from fastapi import APIRouter
from modules.llm import LLMError
from .review import analyze_reviewed


def create_router(job_provider, model_provider):
    router = APIRouter()

    @router.get('/api/link-jobs/{job_id}/antifraud')
    async def report(job_id: str):
        job = job_provider(job_id)
        try:
            client = model_provider()
        except LLMError:
            client = None
        return (await analyze_reviewed(job, client=client, job_id=job_id)).as_dict()

    return router
