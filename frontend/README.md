# PayShield: Frontend Dashboard Console

This folder houses the Vite + React frontend dashboard for **PayShield**.

---

## 🎨 Design Theme & Core Stack

- **Framework**: Vite + React 19
- **Aesthetic**: Custom dark neon cyber-panel with radial glowing highlights
- **Styling**: Tailwind CSS
- **Iconography**: Lucide React
- **Graphics**: Recharts Area & Polar Radar

---

## 🚀 Development Execution

To start the frontend dev server standalone:

```bash
npm install
npm run dev
```

The frontend binds to **[http://localhost:5173](http://localhost:5173)** and connects to the FastAPI scoring pipeline backend.

---

## 🔧 Environment Variables

We support fully configurable backend URL bindings. To configure a different backend URL, set the environment variable:

- **`VITE_API_BASE`**: Set this to your FastAPI target gateway (defaults to `http://localhost:8000/api`).

For example, create a `.env` file:
```env
VITE_API_BASE=http://localhost:8000/api
```
