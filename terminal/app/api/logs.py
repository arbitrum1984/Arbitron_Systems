from fastapi import APIRouter, HTTPException
from app.services.docker_service import docker_service

router = APIRouter()

@router.get("/logs/{container_name}")
async def get_logs(container_name: str, tail: int = 100):
    """
    Fetch the last N lines of logs for a specific container.
    Valid containers: arbitron_terminal, quant_engine, quant_worker, redis
    """
    valid_containers = ["arbitron_terminal", "quant_engine", "quant_worker", "redis"]
    if container_name not in valid_containers:
        raise HTTPException(status_code=400, detail="Invalid container name")
    
    logs = docker_service.get_container_logs(container_name, tail=tail)
    return {"container": container_name, "logs": logs}
