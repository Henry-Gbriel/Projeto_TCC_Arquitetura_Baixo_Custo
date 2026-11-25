import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import { consultarPreco, filtrosParaBusca, type ResultadoPreco, type Tipo } from "../api";
import { CampoSugestao, Contador, Rodape, Topo } from "../componentes/comuns";
import { CONTEUDO } from "../conteudo";
import { NOMES_TIPO, nomeProprio, reais, variacao } from "../formato";

const BAIRROS = ["Pinheiros", "Mooca", "Vila Mariana", "Tatuapé", "Santana", "Butantã", "Lapa", "Ipiranga", "Perdizes", "Saúde", "Bela Vista", "Moema"];
const EXEMPLO = { bairro: "Pinheiros", tipo: "apartamento" as Tipo };

const PROBLEMAS = [
  ["casa", "Anúncios mostram o preço pedido, não o preço pago"],
  ["grade", "Os dados públicos de ITBI chegam em planilhas enormes e cruas"],
  ["relogio", "Comparar bairros ao longo do tempo leva horas de trabalho manual"],
  ["cadeado", "As ferramentas de inteligência imobiliária costumam ser pagas"],
];

const ETAPAS: [string, React.ReactNode, string][] = [
  ["001", "Coleta", "A API descobre e baixa as planilhas anuais de ITBI publicadas pela Prefeitura de São Paulo e guarda o arquivo original, com SHA-256, sem alterar nada."],
  ["002", "Leitura", "O computador lê cada aba mensal em streaming, mapeia as 28 colunas e monta lotes de 10 registros. Ele não limpa nenhum valor."],
  ["003", <>Limpeza <em className="enfase">distribuída</em></>, "Três ESP32 recebem os registros por MQTT e aplicam as regras de limpeza campo a campo em paralelo, devolvendo o valor tratado e os erros encontrados."],
  ["004", "Armazenamento", "As respostas vão para o PostgreSQL (camada Silver), com schema versionado pelo Alembic e sem duplicar reenvios."],
  ["005", "Consulta", "A camada Gold calcula média, faixa e variação do preço do m² para o recorte que você escolheu."],
];

function Icone({ nome }: { nome: string }) {
  const p = { fill: "none", stroke: "var(--destaque)", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" {...p}>
      {nome === "casa" && <><path d="M4 11 12 4l8 7" /><path d="M6 10v10h12V10" /><path d="M10 20v-5h4v5" /></>}
      {nome === "grade" && <><rect x="4" y="4" width="16" height="16" rx="1" /><path d="M4 9.3h16M4 14.6h16M9.3 4v16M14.6 4v16" /></>}
      {nome === "relogio" && <><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></>}
      {nome === "cadeado" && <><rect x="6" y="11" width="12" height="9" rx="1.5" /><path d="M9 11V8a3 3 0 0 1 6 0v3" /></>}
    </svg>
  );
}

export default function Inicio() {
  const navegar = useNavigate();
  const [bairro, setBairro] = useState("");
  const [tipo, setTipo] = useState<Tipo>("apartamento");
  const [exemplo, setExemplo] = useState<ResultadoPreco | null>(null);
  const [faqAberta, setFaqAberta] = useState(0);

  useEffect(() => {
    consultarPreco({ ...EXEMPLO, rua: "", areaMin: null, areaMax: null, periodo: "tudo", comparar: true })
      .then(setExemplo)
      .catch(() => setExemplo(null));
  }, []);

  const consultar = (e?: FormEvent, nome = bairro) => {
    e?.preventDefault();
    const busca = filtrosParaBusca({ bairro: nome, rua: "", tipo, areaMin: null, areaMax: null, periodo: "tudo", comparar: true });
    navegar(nome.trim() ? `/resultado?${busca}` : "/consulta");
  };

  const r = exemplo?.resumo;
  const v = variacao(r?.variacao_12m);
  return (
    <>
      <Topo
        links={[["Intro", "#intro"], ["O problema", "#problema"], ["Como funciona", "#como"], ["Custo", "#custo"],
          ["Perguntas", "#perguntas"], ["Cluster ao vivo", "/cluster"], ["Sobre o projeto", "/sobre"]]}
        acao={<Link to="/consulta" className="botao primario pequeno">Consultar preço</Link>}
      />
      <main>
        <section className="bloco conteudo" id="intro" style={{ paddingBottom: 64 }}>
          <p className="rotulo">TCC · Engenharia da Computação · Dados públicos de ITBI</p>
          <h1 className="titulo t-1">Quanto vale o <em>metro quadrado</em> da sua rua?</h1>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 32, alignItems: "flex-end", justifyContent: "space-between", marginTop: 48 }}>
            <div style={{ flex: "1 1 460px", maxWidth: 620 }}>
              <p className="lead" style={{ marginTop: 0 }}>
                Consulte a média e a variação de preço dos imóveis em qualquer bairro de São Paulo, calculadas a partir das transações reais registradas no ITBI.
              </p>
              <form onSubmit={consultar} style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 28 }}>
                <div style={{ flex: "2 1 220px" }}>
                  <CampoSugestao valor={bairro} aoMudar={setBairro} rotulo="Bairro" placeholder="Bairro — ex.: Pinheiros"
                    endpoint="/consulta/bairros" formatar={nomeProprio} />
                </div>
                <select className="entrada" style={{ flex: "1 1 150px" }} value={tipo} onChange={(e) => setTipo(e.target.value as Tipo)} aria-label="Tipo de imóvel">
                  {Object.entries(NOMES_TIPO).map(([k, [n]]) => <option key={k} value={k}>{n}</option>)}
                </select>
                <button className="botao primario">Consultar</button>
              </form>
            </div>
            <Link to={`/resultado?${filtrosParaBusca({ ...EXEMPLO, rua: "", areaMin: null, areaMax: null, periodo: "tudo", comparar: true })}`}
              className="cartao" style={{ flex: "0 1 340px", textDecoration: "none", padding: 22 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, color: "var(--suave)" }}>
                {EXEMPLO.bairro} · {NOMES_TIPO[EXEMPLO.tipo][0]}
                <span className="chip" style={{ fontSize: 11, padding: "2px 8px" }}>{r ? "DADOS REAIS" : "EXEMPLO"}</span>
              </div>
              <div className="mono" style={{ fontSize: 34, margin: "14px 0 4px" }}>
                <Contador valor={r?.preco_m2_medio ?? null} formatar={reais} /><small className="suave" style={{ fontSize: 14 }}>/m²</small>
              </div>
              <div className={v.classe} style={{ fontSize: 13 }}>
                {r?.variacao_12m != null ? `${v.texto} em 12 meses` : r ? `${r.transacoes} transações` : "carregando…"}
              </div>
              <div style={{ height: 60, marginTop: 8 }}>
                {exemplo && exemplo.serie.length > 1 && (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={exemplo.serie}>
                      <YAxis hide domain={["dataMin", "dataMax"]} />
                      <Line dataKey="local" stroke="var(--destaque)" strokeWidth={2} dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Link>
          </div>
        </section>

        <div className="letreiro" aria-label="Bairros para consultar">
          <div className="letreiro-faixa">
            {[0, 1].map((copia) => (
              <div key={copia} style={{ display: "flex" }} aria-hidden={copia === 1}>
                {BAIRROS.map((b) => (
                  <span key={b}><button tabIndex={copia ? -1 : 0} onClick={() => consultar(undefined, b)}>{b}</button><span className="sep">·</span></span>
                ))}
              </div>
            ))}
          </div>
        </div>

        <section className="bloco conteudo" id="problema">
          <p className="rotulo">O problema</p>
          <h2 className="titulo t-2">O preço de um imóvel não está escondido. <em>Está espalhado.</em></h2>
          <p className="suave" style={{ margin: "36px 0 20px" }}>Isso soa <em className="enfase" style={{ color: "var(--suave)" }}>familiar?</em></p>
          <div className="grade g-4">
            {PROBLEMAS.map(([icone, texto]) => (
              <div key={texto} className="cartao" style={{ minHeight: 200, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                <Icone nome={icone} />
                <p style={{ margin: 0 }}>{texto}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="bloco conteudo" id="como">
          <p className="rotulo">Como funciona</p>
          <h2 className="titulo t-2">Da planilha da Prefeitura ao gráfico, <em>passando por três placas</em> ESP32.</h2>
          <ol style={{ listStyle: "none", padding: 0, margin: "48px 0 24px", borderTop: "1px solid var(--linha)" }}>
            {ETAPAS.map(([n, nome, texto]) => (
              <li key={n} style={{ display: "grid", gridTemplateColumns: "60px minmax(140px, 1fr) minmax(0, 1.4fr)", gap: 24, padding: "26px 0", borderBottom: "1px solid var(--linha)", alignItems: "baseline" }}>
                <span className="mono alta" style={{ fontSize: 13 }}>{n}</span>
                <span style={{ fontSize: 22, letterSpacing: "-0.02em" }}>{nome}</span>
                <span className="suave" style={{ fontSize: 15 }}>{texto}</span>
              </li>
            ))}
          </ol>
          <Link to="/cluster" className="alta" style={{ fontSize: 15 }}>Ver o cluster trabalhando ao vivo →</Link>
        </section>

        <section className="bloco conteudo" id="custo">
          <p className="rotulo">Custo</p>
          <h2 className="titulo t-2">Gratuito para <em>começar.</em> E para terminar.</h2>
          <div className="grade g-2" style={{ marginTop: 48 }}>
            <div className="cartao destaque">
              <p style={{ fontWeight: 600, margin: 0 }}>Software</p>
              <p className="mono" style={{ fontSize: "clamp(40px, 5vw, 64px)", margin: "16px 0 8px" }}>R$ 0,00</p>
              <p style={{ margin: "0 0 20px" }}>Toda a pilha é aberta ou usa planos gratuitos.</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {["Python", "PostgreSQL", "Mosquitto", "MicroPython", "Docker", "React"].map((t) => (
                  <span key={t} className="chip" style={{ borderColor: "var(--tinta)", color: "var(--tinta)", fontFamily: "var(--sans)" }}>{t}</span>
                ))}
              </div>
            </div>
            <div className="cartao">
              <p style={{ fontWeight: 600, margin: 0 }}>Hardware</p>
              <p className="mono" style={{ fontSize: "clamp(40px, 5vw, 64px)", margin: "16px 0 8px" }}>3 × ESP32</p>
              <p style={{ margin: "0 0 16px" }}>O único custo físico do projeto: {CONTEUDO.custoPlacas}.</p>
              <p className="suave" style={{ fontSize: 15, margin: 0 }}>Cada placa recebe registros, aplica as regras de limpeza e devolve o resultado. Juntas, mostram que dá para distribuir processamento em hardware barato.</p>
            </div>
          </div>
        </section>

        <section className="bloco conteudo" id="perguntas">
          <h2 className="titulo t-2">Antes de você <em>perguntar</em></h2>
          <div style={{ maxWidth: 760, marginTop: 40 }}>
            {CONTEUDO.faq.map(([p, resp], i) => (
              <div key={p} style={{ borderBottom: "1px solid var(--linha)" }}>
                <button onClick={() => setFaqAberta(faqAberta === i ? -1 : i)} aria-expanded={faqAberta === i}
                  style={{ width: "100%", display: "flex", justifyContent: "space-between", background: "none", border: 0, padding: "22px 0", fontSize: 18, cursor: "pointer", textAlign: "left" }}>
                  {p} <span className="alta" aria-hidden="true">{faqAberta === i ? "−" : "+"}</span>
                </button>
                {faqAberta === i && <p className="suave" style={{ margin: "0 0 22px", maxWidth: 640 }}>{resp}</p>}
              </div>
            ))}
          </div>
        </section>
      </main>
      <Rodape />
    </>
  );
}

