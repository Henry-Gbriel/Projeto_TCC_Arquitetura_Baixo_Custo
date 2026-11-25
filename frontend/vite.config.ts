import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento (npm run dev, porta 5173) as chamadas vão para a API em :8010.
// Em produção o build (dist/) é servido pela própria API, na mesma origem.
const API = process.env.API_URL ?? "http://localhost:8010";
const rotas = ["/auth", "/consulta", "/cluster", "/nos", "/arquivos", "/fontes", "/coletas", "/execucoes", "/gold"];

export default defineConfig({
  plugins: [react()],
  server: { proxy: Object.fromEntries(rotas.map((r) => [r, API])) },
});
