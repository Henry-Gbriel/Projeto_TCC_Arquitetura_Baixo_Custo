import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { buscaParaFiltros, filtrosParaBusca, type Filtros, type Periodo, type Tipo } from "../api";
import { CampoSugestao, Rodape, Segmentado, Topo } from "../componentes/comuns";
import { NOMES_PERIODO, NOMES_TIPO, nomeProprio } from "../formato";

const AREA_MAX = 300; // no controle, 300 = "300 m² ou mais" (sem limite)

export default function Busca() {
  const [params] = useSearchParams();
  const navegar = useNavigate();
  const [f, setF] = useState<Filtros>(() => {
    const inicial = buscaParaFiltros(params);
    return params.size ? inicial : { ...inicial, areaMin: 50, areaMax: 90 };
  });
  const muda = <K extends keyof Filtros>(k: K, v: Filtros[K]) => setF((x) => ({ ...x, [k]: v }));

  const min = f.areaMin ?? 0, max = f.areaMax ?? AREA_MAX;
  const area = !f.areaMin && !f.areaMax ? "qualquer área" : f.areaMax == null ? `${min}+ m²` : `${min}–${max} m²`;
  const enviar = (e: FormEvent) => {
    e.preventDefault();
    navegar(`/resultado?${filtrosParaBusca(f)}`);
  };

  const local = f.rua.trim() || f.bairro.trim();
  return (
    <>
      <Topo acao={<Link to="/cluster" className="suave" style={{ textDecoration: "none", fontSize: 15 }}>Cluster ao vivo</Link>} />
      <main className="conteudo" style={{ paddingTop: 72, paddingBottom: 32 }}>
        <p className="rotulo">Nova consulta</p>
        <h1 className="titulo t-2">Ajuste o recorte. <em>A gente faz a conta.</em></h1>

        <form onSubmit={enviar} className="grade g-2" style={{ marginTop: 56, alignItems: "start" }}>
          <div className="cartao" style={{ padding: 0 }}>
            <div style={{ padding: "28px 28px 24px", display: "grid", gap: 22 }}>
              <label className="campo"><span>Bairro</span>
                <CampoSugestao id="bairro" valor={f.bairro} aoMudar={(v) => muda("bairro", v)} rotulo="Bairro"
                  placeholder="ex.: Pinheiros" endpoint="/consulta/bairros" formatar={nomeProprio} />
              </label>
              <label className="campo"><span>Rua <em>(opcional)</em></span>
                <CampoSugestao id="rua" valor={f.rua} aoMudar={(v) => muda("rua", v)} rotulo="Rua" placeholder="ex.: Rua dos Pinheiros"
                  endpoint={`/consulta/ruas${f.bairro.trim() ? `?bairro=${encodeURIComponent(f.bairro.trim())}` : ""}`} formatar={nomeProprio} />
              </label>
            </div>
            <Divisor />
            <div className="campo" style={{ padding: 28 }}>
              <span>Tipo de imóvel</span>
              <Segmentado rotulo="Tipo de imóvel" valor={f.tipo} aoMudar={(v: Tipo) => muda("tipo", v)}
                opcoes={Object.entries(NOMES_TIPO).map(([k, [n]]) => [k as Tipo, n])} />
            </div>
            <Divisor />
            <div style={{ padding: 28, display: "grid", gap: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span className="suave">{f.tipo === "terreno" ? "Área do terreno" : "Área útil"}</span>
                <span className="mono" style={{ fontSize: 20 }}>{area}</span>
              </div>
              <Faixa rotulo="mínima" valor={min} aoMudar={(v) => setF((x) => ({ ...x, areaMin: v || null, areaMax: x.areaMax != null && x.areaMax < v ? v : x.areaMax }))} />
              <Faixa rotulo="máxima" valor={max} aoMudar={(v) => setF((x) => ({ ...x, areaMax: v >= AREA_MAX ? null : v, areaMin: x.areaMin != null && x.areaMin > v ? v : x.areaMin }))} />
            </div>
            <Divisor />
            <div className="campo" style={{ padding: 28 }}>
              <span>Período</span>
              <Segmentado rotulo="Período" variante="claro mono" valor={f.periodo} aoMudar={(v: Periodo) => muda("periodo", v)}
                opcoes={Object.entries(NOMES_PERIODO).map(([k, [n]]) => [k as Periodo, n])} />
            </div>
            <Divisor />
            <div style={{ padding: "20px 28px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
              <span>Comparar com a média da cidade</span>
              <div style={{ width: 170 }}>
                <Segmentado rotulo="Comparar com a média da cidade" valor={f.comparar ? "on" : "off"} aoMudar={(v) => muda("comparar", v === "on")}
                  opcoes={[["off", "Off"], ["on", "On"]]} />
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gap: 20 }}>
            <div className="cartao" style={{ padding: 40 }}>
              <p className="rotulo">Você vai ver</p>
              <p style={{ fontSize: "clamp(26px, 2.8vw, 40px)", lineHeight: 1.18, letterSpacing: "-0.035em", margin: "0 0 32px", fontWeight: 500 }}>
                O preço do m² de <em className="enfase">{NOMES_TIPO[f.tipo][1]}</em>
                {local ? <> em <em className="enfase">{nomeProprio(local) || local}</em></> : " em toda a cidade"}
                {f.areaMin || f.areaMax ? ` com ${area.replace("–", " a ")}` : ""}, {NOMES_PERIODO[f.periodo][1]}
                {f.comparar && local ? ", comparado com a média da cidade" : ""}.
              </p>
              <button className="botao primario" style={{ padding: "16px 30px", fontSize: 18 }}>Consultar <span aria-hidden="true">→</span></button>
            </div>
            <div className="cartao tracejado" aria-hidden="true">
              <div className="grade g-3" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
                {[0, 1, 2].map((i) => <div key={i} style={{ height: 70, background: "var(--superficie)", borderRadius: 14 }} />)}
              </div>
              <svg viewBox="0 0 400 90" style={{ width: "100%", height: 110, margin: "20px 0" }}>
                <polyline points="40,80 80,77 110,76 150,70 200,66 250,56 290,49 330,42 370,34" fill="none" stroke="var(--linha)" strokeWidth="2.5" />
              </svg>
              <p className="suave" style={{ fontSize: 14, margin: 0 }}>Média, variação e evolução do preço ao longo do tempo.</p>
            </div>
            <p className="suave" style={{ fontSize: 14, margin: 0 }}>
              Fonte: ITBI · Prefeitura de São Paulo. Consultas com poucas transações mostram um aviso de baixa amostra.
            </p>
          </div>
        </form>
      </main>
      <Rodape />
    </>
  );
}

const Divisor = () => <hr style={{ border: 0, borderTop: "1px solid var(--linha)", margin: 0 }} />;

function Faixa({ rotulo, valor, aoMudar }: { rotulo: string; valor: number; aoMudar: (v: number) => void }) {
  return (
    <label style={{ display: "grid", gridTemplateColumns: "70px 1fr", alignItems: "center", gap: 16, fontSize: 15 }} className="suave">
      {rotulo}
      <input type="range" min={0} max={AREA_MAX} step={5} value={valor} aria-label={`Área ${rotulo}`}
        aria-valuetext={valor >= AREA_MAX ? "sem limite" : `${valor} m²`} onChange={(e) => aoMudar(Number(e.target.value))} />
    </label>
  );
}
