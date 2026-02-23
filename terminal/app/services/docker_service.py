import docker
import os

class DockerService:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            print(f"Error connecting to Docker: {e}")
            self.client = None

    def get_container_logs(self, container_name: str, tail: int = 100):
        if not self.client:
            return "Docker client not initialized"
        
        try:
            container = self.client.containers.get(container_name)
            logs = container.logs(tail=tail, stdout=True, stderr=True)
            return logs.decode('utf-8', errors='replace')
        except docker.errors.NotFound:
            return f"Container {container_name} not found"
        except Exception as e:
            return f"Error fetching logs: {str(e)}"

docker_service = DockerService()
