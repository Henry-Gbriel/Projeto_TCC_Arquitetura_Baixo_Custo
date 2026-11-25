import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router";
import { api } from "../api";
import { CONTEUDO } from "../conteudo";

export function Logo() {
  return (
    <Link to="/" className="logo" aria-label="quadra, página inicial">
      <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
        <rect x="1" y="1" width="13" height="13" fill="var(--destaque)" />
        <rect x="16" y="1" width="13" height="13" fill="none" stroke="var(--texto)" strokeWidth="2" />
        <rect x="1" y="16" width="13" height="13" fill="none" stroke="var(--texto)" strokeWidth="2" />
        <rect x="16" y="16" width="13" height="13" fill="none" stroke="var(--texto)" strokeWidth="2" />
      </svg>
      quadra
    </Link>
  );
}

export function Topo({ links = [], acao }: { links?: [string, string][]; acao?: ReactNode }) {
  return (
    <header className="topo">
      <div className="conteudo">
        <Logo />
        <nav aria-label="Seções">
          {links.map(([rotulo, destino]) =>
            destino.startsWith("#") ? (
              <a key={destino} href={destino} onClick={(e) => rolarPara(e, destino)}>{rotulo}</a>
            ) : (
              <NavLink key={destino} to={destino} className={({ isActive }) => (isActive ? "ativo" : "")}>{rotulo}</NavLink>
            ),
          )}
        </nav>
        <div className="acoes">{acao}</div>
      </div>
    </header>
  );
}

// Com HashRouter o "#" da URL é a rota; âncoras da página rolam sem trocar a rota.
function rolarPara(e: React.MouseEvent, destino: string) {
  e.preventDefault();
  document.getElementById(destino.slice(1))?.scrollIntoView();
}

export function Rodape() {
  return (
    <footer className="rodape">
      <div className="conteudo">
        <p className="marca" aria-hidden="true">quadra</p>
        <div className="linha-rodape">
          <span>Projeto de TCC · {CONTEUDO.autor.nome}</span>
          <span>Fonte dos dados: ITBI · Prefeitura de São Paulo</span>
          <span style={{ display: "flex", gap: 20 }}>
            <Link to="/painel">Painel de controle</Link>
            <a href={CONTEUDO.autor.github} target="_blank" rel="noreferrer">{CONTEUDO.autor.github.replace("https://", "")}</a>
          </span>
        </div>
      </div>
    </footer>
  );
}

/** Número que conta até o valor (guia de estilo: "números contam até o valor"). */
export function Contador({ valor, formatar }: { valor: number | null | undefined; formatar: (v: number) => string }) {
  const [mostrado, setMostrado] = useState(valor ?? 0);
  const anterior = useRef(0);
  useEffect(() => {
    if (valor == null) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setMostrado(valor);
      anterior.current = valor;
      return;
    }
    const de = anterior.current, inicio = performance.now(), duracao = 900;
    let quadro = 0;
    const passo = (agora: number) => {
      const t = Math.min(1, (agora - inicio) / duracao);
      setMostrado(de + (valor - de) * (1 - Math.pow(1 - t, 3)));
      if (t < 1) quadro = requestAnimationFrame(passo);
      else anterior.current = valor;
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [valor]);
  return <>{valor == null ? "—" : formatar(mostrado)}</>;
}

export function Segmentado<T extends string>({ opcoes, valor, aoMudar, variante = "", rotulo }: {
  opcoes: [T, string][]; valor: T; aoMudar: (v: T) => void; variante?: string; rotulo: string;
}) {
  return (
    <div className={`segmentado ${variante}`} role="group" aria-label={rotulo}>
      {opcoes.map(([v, texto]) => (
        <button key={v} type="button" aria-pressed={v === valor} onClick={() => aoMudar(v)}>{texto}</button>
      ))}
    </div>
  );
}

/** Campo de texto com sugestões vindas da API (bairros, ruas). */
export function CampoSugestao({ valor, aoMudar, endpoint, placeholder, formatar, rotulo, id }: {
  valor: string;
  aoMudar: (v: string) => void;
  endpoint: string; // ex.: "/consulta/bairros" ou "/consulta/ruas?bairro=PINHEIROS"; recebe &q=
  placeholder?: string;
  formatar: (v: string) => string;
  rotulo: string;
  id?: string;
}) {
  const [itens, setItens] = useState<{ nome: string; transacoes: number }[]>([]);
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(-1);
  const lista = useId();
  useEffect(() => {
    if (!aberto || valor.trim().length < 2) return setItens([]);
    const url = `${endpoint}${endpoint.includes("?") ? "&" : "?"}q=${encodeURIComponent(valor)}`;
    const t = setTimeout(() => {
      api<Record<string, string | number>[]>(url)
        .then((r) => setItens(r.map((x) => ({ nome: String(x.bairro ?? x.logradouro), transacoes: Number(x.transacoes) }))))
        .catch(() => setItens([]));
    }, 180);
    return () => clearTimeout(t);
  }, [valor, aberto, endpoint]);

  const escolher = (nome: string) => {
    aoMudar(formatar(nome));
    setAberto(false);
  };
  return (
    <div style={{ position: "relative" }}>
      <input
        id={id} className="entrada" value={valor} placeholder={placeholder} aria-label={rotulo} autoComplete="off"
        role="combobox" aria-expanded={aberto && itens.length > 0} aria-controls={lista}
        onChange={(e) => { aoMudar(e.target.value); setAberto(true); setAtivo(-1); }}
        onFocus={() => setAberto(true)}
        onBlur={() => setTimeout(() => setAberto(false), 150)}
        onKeyDown={(e) => {
          if (!itens.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setAtivo((a) => Math.min(itens.length - 1, a + 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setAtivo((a) => Math.max(0, a - 1)); }
          if (e.key === "Enter" && ativo >= 0) { e.preventDefault(); escolher(itens[ativo].nome); }
          if (e.key === "Escape") setAberto(false);
        }}
      />
      {aberto && itens.length > 0 && (
        <ul className="sugestoes" id={lista} role="listbox">
          {itens.map((i, n) => (
            <li key={i.nome} role="option" aria-selected={n === ativo}>
              <button type="button" data-ativo={n === ativo} onMouseDown={(e) => e.preventDefault()} onClick={() => escolher(i.nome)}>
                {formatar(i.nome)} <small>{i.transacoes}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Desenho da placa ESP32 usado na tela do cluster. */
export function PlacaEsp32({ ligada }: { ligada: boolean }) {
  const pinos = [0, 1, 2, 3];
  return (
    <svg viewBox="0 0 180 64" width="180" height="64" role="img" aria-label={ligada ? "placa com sinal" : "placa sem sinal"}
      style={{ display: "block", margin: "8px auto 28px", opacity: ligada ? 1 : 0.55 }}>
      <rect x="1" y="1" width="178" height="62" rx="5" fill="var(--fundo-campo)" stroke="var(--linha)" strokeWidth="2" />
      {ligada && pinos.map((i) => (
        <g key={i} fill="var(--suave)" opacity=".75">
          <rect x={10 + i * 9} y="6" width="5" height="3" /><rect x={135 + i * 9} y="6" width="5" height="3" />
          <rect x={10 + i * 9} y="55" width="5" height="3" /><rect x={135 + i * 9} y="55" width="5" height="3" />
        </g>
      ))}
      <rect x="62" y="15" width="56" height="34" rx="3" fill="var(--superficie)" stroke="var(--suave)" strokeOpacity=".6" />
      <circle cx="157" cy="32" r="4" fill={ligada ? "var(--destaque)" : "none"} stroke={ligada ? "none" : "var(--suave)"} />
    </svg>
  );
}

/** Repete `carregar` a cada `ms` enquanto a aba estiver visível. */
export function usePeriodico(carregar: () => void, ms: number) {
  const ref = useRef(carregar);
  ref.current = carregar;
  useEffect(() => {
    ref.current();
    const t = setInterval(() => { if (!document.hidden) ref.current(); }, ms);
    return () => clearInterval(t);
  }, [ms]);
}
