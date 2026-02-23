# Arbitron Terminal

**Arbitron Terminal** is a Professional Financial AI Backend with OSINT Integration. This project is a comprehensive multi-service architecture designed for quantitative trading research, macroeconomic analysis, and real-time open-source intelligence (OSINT) gathering.

## Project Structure

The project consists of several microservices orchestrated via Docker Compose:

1. **Terminal (Backend & UI)**
   - Built with FastAPI (`app.main`).
   - Serves the frontend single-page application (SPA).
   - Provides API endpoints for chat, docker logs, SEC EDGAR financials, FRED macroeconomic data, backtesting, and model training.
   - Runs asynchronous background loops to poll intelligence services:
     - Twitter Service
     - RSS/Alerts Service
     - Pizza Index Service (Occupancy index check)

2. **Quant Engine (Prediction API)**
   - The machine learning engine behind the terminal.
   - Built with FastAPI and `uvicorn`.
   - Connects to shared data volumes (`qlib_data`, `model_data`).

3. **Quant Worker (Celery)**
   - An asynchronous worker service built on Celery for heavy tasks (e.g., model training, data ingestion).

4. **Redis**
   - Message broker and queue backend for Celery tasks.

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed.
- [Docker Compose](https://docs.docker.com/compose/install/) installed.

### Setup

1. **Environment Variables**
   - Copy the example `.env` file to set up your variables:
     ```bash
     cp .env.example .env
     ```
   - Open `.env` and fill in your actual API keys (e.g., Gemini, Apify, SerpApi, FRED, EDGAR).

2. **Running the Application**
   - Use Docker Compose to build and start all services in the background:
     ```bash
     docker-compose up -d --build
     ```

3. **Accessing the Services**
   - **Terminal UI & API:** Available at `http://localhost:8000`
   - **Quant Engine API:** Available at `http://localhost:8001`

### Stopping the Application

To gracefully stop and remove all containers, run:
```bash
docker-compose down
```

## Security

Please make sure you **do not commit** the `.env` file or any files containing real API keys or credentials to the repository. Use `.env.example` as a template for other developers.
