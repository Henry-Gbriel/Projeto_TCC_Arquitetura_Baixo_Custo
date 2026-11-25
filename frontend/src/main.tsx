import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter, Route, Routes, useLocation } from "react-router";
import { useEffect } from "react";
import "@fontsource/inter-tight/400.css";
import "@fontsource/inter-tight/500.css";
import "@fontsource/inter-tight/600.css";
import "@fontsource/instrument-serif/400-italic.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "./estilo.css";
import Inicio from "./paginas/Inicio";
import Busca from "./paginas/Busca";
import Resultado from "./paginas/Resultado";
import Cluster from "./paginas/Cluster";
import Sobre from "./paginas/Sobre";
import Login from "./paginas/Login";
import Painel from "./paginas/Painel";

// HashRouter: as rotas ficam depois do "#", então a API só precisa servir o index.html em "/".
function VoltarAoTopo() {
  const { pathname } = useLocation();
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  return null;
}

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <HashRouter>
      <VoltarAoTopo />
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/consulta" element={<Busca />} />
        <Route path="/resultado" element={<Resultado />} />
        <Route path="/cluster" element={<Cluster />} />
        <Route path="/sobre" element={<Sobre />} />
        <Route path="/login" element={<Login />} />
        <Route path="/painel" element={<Painel />} />
        <Route path="*" element={<Inicio />} />
      </Routes>
    </HashRouter>
  </StrictMode>,
);
