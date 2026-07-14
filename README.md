# Document Scan

> Scan billing documents

## Complete Application Launch Sequence

### 1. Set Local Environment Keys
Configure your real keys inside the configuration file container:
```bash
nano .env
```

### 2. Startup Arize Phoenix Local Telemetry Collector Instance (Terminal Window 1)
Run the telemetry collector platform engine container to inspect trace parameters on port 6006:
```bash
uv run phoenix serve
```

### 3. Startup Application Core Server Environment (Terminal Window 2)
This boots the FastAPI REST gateway framework on port 8000.
```bash
uv run uvicorn backend.src.documentscan.main:app --reload
```

### 4. Build & Install Frontend Client Dashboard Workspace UI (Terminal Window 3)
This boots the React + Vite development server on port 5173.
```bash
cd frontend
npm install
npm run dev
```

---

## Running the FastMCP Tool Server (Optional / Desktop Integration)

### Standalone Process Execution (Terminal Window 4)
To spin up your FastMCP protocol tools wrapper process target via direct script runner execution:
```bash
uv run mcp-server
```

#### Claude Desktop Native Integration Configuration
Add the configuration snippet below into your active system
