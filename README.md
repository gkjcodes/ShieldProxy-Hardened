# 🛡️ ShieldProxy: The Ultimate LLM Prompt Injection Firewall

ShieldProxy is a high-performance, production-ready LLM Prompt Injection Firewall. It is designed to intercept, manage, and prevent severe attacks on Large Language Models—including Prompt Injection, Jailbreaking, System Prompt Leaks, and Social Engineering—in real-time.

It features a cutting-edge **Python/FastAPI Backend** powered natively by **Ollama (Llama 3 8B)** for zero-day threat detection and natural language conversational routing, alongside a beautiful, futuristic **React/Vite Frontend Dashboard** built with custom glassmorphism styling and real-time visualization.

---

## ✨ Key Capabilities

1. **Native Native Ollama 3 (Llama 3 8B) Integration**:
   - **Threat Classifier**: 100% of simulator prompts and API traffic go securely through the local Llama 3 instance to catch zero-day attacks that static regex filters miss.
   - **LLM Gateway**: Unsafe requests are instantly dropped (403 Forbidden). Safe requests are piped directly to the Ollama engine to generate dynamic, accurate conversational responses.
2. **Sub-1ms Semantic Caching**: Drastically reduces repeated generation latency. The first time a prompt is intercepted, Ollama evaluates it natively. All subsequent identical prompts return out of a fast LRU memory cache in `<5ms`.
3. **Multi-Stage Security Pipeline**:
   - **Rate Limiting Engine**: A Redis-backed sliding-window token bucket blocks DDOS attacks instantly.
   - **Threat Classifier**: Real-time generative heuristic threat detection.
   - **PII Scrubber**: Identifies and masks Personally Identifiable Information using Regex/NLP before it reaches the generative AI model to ensure data privacy.
   - **Audit Logger**: Asynchronous Redis-backed audit trails mapping the attack vector timelines.
   - **LLM Gateway**: Connecting to Local Llama 3 8B seamlessly.
   - **Output Filter**: Evaluates generated token streams to ensure no hidden payloads were generated.
4. **Interactive Dashboard**:
   - Track active threats, analyze metrics via `recharts`, and visually monitor latency spikes. Includes a fully playable **Attack Simulator Lab**.

---

## 🚀 Tech Stack

### Backend
- **Core Engine**: Python 3, FastAPI, Uvicorn
- **AI/LLM Engine**: Ollama (Llama 3 8B), OpenAI Python SDK Wrapper
- **Caching & Rate Limiting**: Redis, LRU In-Memory Dicts
- **Security NLP**: spaCy, Regex

### Frontend
- **Framework**: React 19, Vite
- **Styling**: Modular Vanilla CSS with CSS Variables, Glassmorphism
- **Visualizations**: Recharts, D3-Geo, React-Simple-Maps
- **Icons**: Lucide-React

---

## 🛠️ Local Development Setup

### 1. Requirements
- Node.js (v18+)
- Python (3.10+)
- [Ollama](https://ollama.com/) installed and running locally with the exact model: `llama3:8b`.
  *(Run `ollama run llama3:8b` in your terminal to download and start it).*
- [Redis](https://redis.io/) running on `localhost:6379`.

### 2. Backend Startup
Open a terminal, navigate to the `backend/` directory, and set up your environment:
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate      # (Windows)
# source venv/bin/activate   #(Mac/Linux)
pip install -r requirements.txt
```
Run the FastAPI development server:
```bash
python -m uvicorn main:app --reload --port 8000
```
*The backend API will spark to life at `http://localhost:8000/v1`*

### 3. Frontend Startup
Open a new terminal at the root directory of the project:
```bash
npm install
npm run dev
```
*The React Dashboard will be available at `http://localhost:5173/`*

---

*Developed as a robust, production-grade security architecture designed to shield modern GenAI infrastructure from advanced prompt exploitation.*
