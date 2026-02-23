<div align="center">

# 🌌 Arbitron Terminal
**Professional Financial AI Backend with OSINT Integration**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-00a393.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*An advanced, multi-service architecture designed for quantitative trading research, macroeconomic analysis, and real-time open-source intelligence (OSINT) gathering.*

</div>

---

## 📖 Overview

**Arbitron Terminal** is not just an application; it's a comprehensive ecosystem for algorithmic and discretionary traders. It bridges the gap between hard quantitative data (prices, macroeconomics, SEC filings) and soft alternative data (social sentiment, geopolitical alerts, offline humint via OSINT). 

The platform is divided into a sleek **Terminal Dashboard** (Frontend + API Gateway) and a heavy-duty **Quant Engine** (Machine Learning & Backtesting), orchestrated seamlessly via Docker Compose.

---

## 🏗️ Architecture & Microservices

The ecosystem consists of 4 core dockerized microservices working in tandem:

| Service | Technology | Port | Description |
| :--- | :--- | :--- | :--- |
| 🛡️ **Terminal (API/UI)** | `FastAPI` + `Vanilla JS/CSS` | `8000` | The main brain of the UI. Serves the dashboard, proxies requests, handles AI chats (Gemini), and runs background OSINT polling loops. |
| 🧠 **Quant Engine** | `FastAPI` + `Qlib` + `MLflow` | `8001` | The ML inference server. Provides an API for real-time market predictions, historical backtest data, and model diagnostics. |
| 🏭 **Quant Worker** | `Celery` | `-` | An asynchronous, heavy-duty worker designed for background model training, massive data ingestion, and complex backtests. |
| 📨 **Redis** | `Redis:7-alpine` | `6379` | The message broker connecting the FastAPI Quant Engine with the Celery Worker for distributed task queues. |

---

## 🌟 Core Features & Capabilities

### 1. 🤖 AI & Natural Language Interface
- **GenAI Integration**: Powered by Google Gemini. Allows users to chat directly with their data, ask for market summaries, or request code generation for algorithms.
- **Context-Aware**: The AI agent is hooked into the terminal's state, understanding current active windows and underlying data.

### 2. 📊 Quantitative Trading Engine (`Qlib`)
- **Real-Time Inference**: Ask the engine for live predictions (signals) on specific tickers based on the latest trained ML models.
- **Full-Scale Backtesting**: Run historical backtests, evaluate portfolio performance, and view interactive `Plotly` equity curves directly in the UI.
- **Automated ML Pipelines**: Trigger full model retraining pipelines in the background via Celery, tracking experiments natively.

### 3. 🌐 Open-Source Intelligence (OSINT)
- **🐦 Twitter Sentiment**: Monitors crypto and market sentiment on X (Twitter).
- **📰 RSS & Alert Aggregator**: Ingests automated Google Alerts and selected RSS feeds for geopolitical and macroeconomic breaking news.
- **🍕 The "Pentagon Pizza" Index**: A custom OSINT tracker that monitors the busyness (occupancy) of local pizza places near major US government institutions (e.g., The Pentagon) to predict late-night crisis meetings.

### 4. 📈 Fundamental & Macro Data
- **🏛️ SEC EDGAR**: Automatically pulls and caches official financial facts (10-K, 10-Q) directly from the U.S. Securities and Exchange Commission.
- **📉 FRED Macroeconomics**: Native integration with the Federal Reserve Economic Data (FRED) API for interest rates, inflation schemas, and housing data.

---

## 🚀 Getting Started

### Prerequisites

Ensure you have the following installed on your host machine:
- [Docker Engine](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)
- A [Google Gemini API Key](https://aistudio.google.com/app/apikey)
- A [FRED API Key](https://fred.account.stlouisfed.org/apikeys) (Optional)

### Installation Guide

1. **Clone the Repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Arbitron_Systems.git
   cd Arbitron_Systems
   ```

2. **Configure Environment Variables**
   We have provided a secure template. Copy it and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   *Open `.env` in your text editor and populate at least the `GEMINI_API_KEY`.*

3. **Build & Spin Up the Ecosystem**
   Let Docker handle the complexities of dependencies, networking, and volumes.
   ```bash
   docker-compose up -d --build
   ```

4. **Access the Application**
   - 💻 **Arbitron Terminal UI**: Open `http://localhost:8000` in your browser.
   - 🔌 **Terminal Swagger API Docs**: `http://localhost:8000/docs`
   - 🧠 **Quant Engine API Docs**: `http://localhost:8001/docs`

### Shutting Down

To gracefully stop the platform and remove the containers (your database and ML models will be safely preserved in Docker volumes):
```bash
docker-compose down
```

---

## 📂 Directory Structure

```text
Arbitron_Systems/
├── .env.example               # Template for API keys
├── docker-compose.yml         # Container orchestration
├── terminal/                  # Backend API & Frontend SPA
│   ├── app/                   # FastAPI application logic
│   │   ├── api/               # Router endpoints (Chat, Logs)
│   │   ├── services/          # Business logic (OSINT, EDGAR, AI)
│   │   └── core/              # Configs & Prompts
│   └── static/                # HTML/JS/CSS Dashboard
└── quant_engine/              # ML Engine & Data Processing
    ├── inference_api.py       # API for Predictions & Backtesting
    ├── tasks.py               # Celery asynchronous worker tasks
    ├── configs/               # ML Pipeline configurations
    └── scripts/               # Deep Qlib integrations
```

---

## 🔒 Security Notice

This repository contains an `.env.example` file. 
**NEVER commit your production `.env` file containing real API keys or secrets to version control.** 
The `.gitignore` is pre-configured to prevent accidental leaks of your `.venv`, `.env`, and generated SQLite databases.

<div align="center">
  <sub>Built for the future of decentralized and quantitative finance.</sub>
</div>
