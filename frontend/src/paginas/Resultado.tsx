import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { buscaParaFiltros, consultarPreco, filtrosParaBusca, type ResultadoPreco } from "../api";
import { Contador, Rodape, Topo } from "../componentes/comuns";
import { NOMES_PERIODO, NOMES_TIPO, baixarCsv, dataHora, mesAno, mil, nomeProprio, numero, reais, trimestre, trimestreCurto, variacao } from "../formato";

export default function Resultado() {
  const [params] = useSearchParams();
  const f = buscaParaFiltros(params);
  const chave = params.toString();
  const [dados, setDados] = useState<ResultadoPreco | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    setDados(null);
    setErro(null);
    consultarPreco(f).then(setDados).catch((e) => setErro(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  const local = nomeProprio(f.rua.trim() ? f.rua.toUpperCase() : f.bairro.toUpperCase()) || "São Paulo";
  const area = f.areaMin || f.areaMax ? (f.areaMax == null ? `${f.areaMin}+ m²` : `${f.areaMin ?? 0}–${f.areaMax} m²`) : null;
  const r = dados?.resumo;
  const comCidade = f.comparar && (f.bairro.trim() || f.rua.trim());
  const pequena = r && r.transacoes < (dados?.amostra_minima ?? 0);

  const csv = () => {
    if (!dados) return;
    baixarCsv(`quadra-${local.toLowerCase().replace(/\s+/g, "-")}-${f.tipo}.csv`, [
      ["trimestre", `preco_m2_${local}`, "transacoes", "preco_m2_cidade"],
      ...dados.serie.map((s) => [s.trimestre, s.local, s.transacoes, s.cidade]),
      [],
      ["rua", "transacoes", "preco_m2_medio", "variacao_12m_%"],
      ...dados.ruas.map((x) => [nomeProprio(x.logradouro), x.transacoes, x.preco_m2_medio, x.variacao_12m]),
    ]);
  };

  return (
    <>
      <Topo acao={<Link to={`/consulta?${filtrosParaBusca(f)}`} className="botao contorno pequeno">Nova consulta</Link>} />
      <main className="conteudo" style={{ paddingTop: 48 }}>
        <Link to={`/consulta?${filtrosParaBusca(f)}`} className="voltar">← Editar filtros</Link>
        <h1 className="titulo t-2" style={{ margin: "18px 0 22px" }}>{local} · <em>{NOMES_TIPO[f.tipo][1]}</em></h1>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {area && <span className="chip">{area}</span>}
            <span className="chip">{NOMES_PERIODO[f.periodo][1].replace(/^n?[oe]s? /, "").replace("em todo o ", "todo o ")}</span>
            {f.rua.trim() && f.bairro.trim() && <span className="chip">{nomeProprio(f.bairro.toUpperCase())}</span>}
            {comCidade && <span className="chip">vs. média da cidade</span>}
            {pequena && <span className="chip cheio">amostra pequena</span>}
          </div>
          <button className="botao contorno pequeno" onClick={csv} disabled={!dados?.resumo}>
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M8 2v8M4.5 6.5 8 10l3.5-3.5M3 13h10" /></svg>
            Baixar CSV
          </button>
        </div>

        {erro && <div className="aviso">Não foi possível consultar: {erro}</div>}
        {!erro && !dados && <Carregando />}
        {dados && !r && (
          <div className="cartao vazio">
            <p className="t-3 titulo" style={{ color: "var(--texto)" }}>Nenhuma transação nesse recorte.</p>
            <p>Confira a grafia do bairro ou da rua, ou amplie a faixa de área e o período.</p>
            <Link to={`/consulta?${filtrosParaBusca(f)}`} className="botao primario" style={{ marginTop: 12 }}>Ajustar filtros</Link>
          </div>
        )}
        {dados && r && (
          <>
            {pequena && (
              <div className="aviso" style={{ marginBottom: 20 }}>
                Só {r.transacoes} transações nesse recorte (o mínimo recomendado é {dados.amostra_minima}). Trate a média como indicativa.
              </div>
            )}
            <div className="grade g-4">
              <div className="cartao destaque kpi">
                <div className="nome">Preço médio do m²</div>
                <div className="valor"><Contador valor={r.preco_m2_medio} formatar={reais} /></div>
                <div className="nota">{mesAno(r.inicio)} a {mesAno(dados.referencia)}</div>
              </div>
              <div className="cartao kpi">
                <div className="nome">Variação em 12 meses</div>
                <div className={`valor ${variacao(r.variacao_12m).classe}`}>{variacao(r.variacao_12m).texto}</div>
                <div className="nota">
                  {r.variacao_12m == null ? "poucas transações para comparar os dois anos" : `cidade: ${variacao(r.variacao_12m_cidade).texto.replace(/[▲▼] /, "")}`}
                </div>
              </div>
              <div className="cartao kpi">
                <div className="nome">Transações no período</div>
                <div className="valor"><Contador valor={r.transacoes} formatar={(v) => numero(Math.round(v))} /></div>
                <div className="nota">compras e vendas válidas do ITBI</div>
              </div>
              <div className="cartao kpi">
                <div className="nome">Faixa típica (P25–P75)</div>
                <div className="valor" style={{ fontSize: "clamp(22px, 2.2vw, 30px)" }}>R$ {mil(r.p25).replace(" mil", "")}–{mil(r.p75)}</div>
                <div className="nota">metade das transações</div>
              </div>
            </div>

            <div className="cartao" style={{ marginTop: 20 }}>
              <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 12, marginBottom: 24 }}>
                <h2 className="titulo t-3" style={{ fontWeight: 500 }}>Evolução do preço do m² <em style={{ color: "var(--suave)" }}>por trimestre</em></h2>
                <div style={{ display: "flex", gap: 20, fontSize: 14 }} className="suave">
                  <span><Legenda tracejado={false} /> {local}</span>
                  {comCidade && <span><Legenda tracejado /> Média da cidade</span>}
                </div>
              </div>
              {dados.serie.length < 2 ? (
                <p className="suave">Poucos trimestres com transações para desenhar a evolução.</p>
              ) : (
                <div style={{ height: 340 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={dados.serie} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                      <defs>
                        <linearGradient id="preenchimento" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#c6f36b" stopOpacity={0.16} />
                          <stop offset="100%" stopColor="#c6f36b" stopOpacity={0.03} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid vertical={false} stroke="#3a3029" strokeOpacity={0.6} />
                      <XAxis dataKey="trimestre" tickFormatter={trimestreCurto} tick={{ fill: "#b5a899", fontSize: 12, fontFamily: "JetBrains Mono" }}
                        axisLine={false} tickLine={false} minTickGap={40} />
                      <YAxis tickFormatter={(v: number) => `R$ ${mil(v)}`} width={92} domain={["auto", "auto"]}
                        tick={{ fill: "#b5a899", fontSize: 12, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{ background: "#201a15", border: "1px solid #3a3029", borderRadius: 14, fontFamily: "JetBrains Mono", fontSize: 13 }}
                        labelFormatter={(t) => trimestre(String(t))}
                        formatter={(v, nome, item) => [`${reais(Number(v))}${nome === "local" ? ` · ${item.payload.transacoes} transações` : ""}`, nome === "local" ? local : "Cidade"]}
                      />
                      <Area type="monotone" dataKey="local" stroke="#c6f36b" strokeWidth={2.5} fill="url(#preenchimento)" dot={dados.serie.length < 12} />
                      {comCidade && <Line type="monotone" dataKey="cidade" stroke="#b5a899" strokeWidth={1.6} strokeDasharray="5 5" dot={false} />}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="grade" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(0, 3fr)", marginTop: 20 }} data-quebra>
              <div className="cartao">
                <h2 className="titulo t-3" style={{ fontWeight: 500, fontSize: 24, marginBottom: 28 }}>Por tipo de imóvel</h2>
                {dados.por_tipo.map((t) => {
                  const maior = Math.max(...dados.por_tipo.map((x) => x.preco_m2_medio));
                  const poucas = t.transacoes < dados.amostra_minima;
                  return (
                    <div key={t.tipo} style={{ marginBottom: 22 }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span>{NOMES_TIPO[t.tipo][0]}</span><span className="mono">{reais(t.preco_m2_medio)}</span>
                      </div>
                      <div style={{ height: 10, background: "var(--fundo-campo)", borderRadius: 99, margin: "8px 0 6px" }}>
                        <div style={{ height: "100%", width: `${(t.preco_m2_medio / maior) * 100}%`, borderRadius: 99,
                          background: t.tipo === f.tipo ? "var(--destaque)" : "var(--destaque-escuro)" }} />
                      </div>
                      <span className="suave" style={{ fontSize: 13 }}>{numero(t.transacoes)} transações{poucas ? " · amostra pequena" : ""}</span>
                    </div>
                  );
                })}
              </div>
              <div className="cartao">
                <h2 className="titulo t-3" style={{ fontWeight: 500, fontSize: 24, marginBottom: 28 }}>Ruas com mais transações</h2>
                {dados.ruas.length === 0 ? <p className="suave">Sem ruas identificadas nesse recorte.</p> : (
                  <div className="rolagem-x">
                    <table className="tabela">
                      <thead><tr><th>Rua</th><th className="num">Transações</th><th className="num">m² médio</th><th className="num">12 meses</th></tr></thead>
                      <tbody>
                        {dados.ruas.map((x) => {
                          const v = variacao(x.variacao_12m);
                          return (
                            <tr key={x.logradouro}>
                              <td>{nomeProprio(x.logradouro)}</td>
                              <td className="num">{numero(x.transacoes)}</td>
                              <td className="num">{reais(x.preco_m2_medio)}</td>
                              <td className={`num ${v.classe}`}>{v.texto}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            <div style={{ borderTop: "1px solid var(--linha)", marginTop: 32, paddingTop: 32, display: "grid", gridTemplateColumns: "minmax(160px, 1fr) minmax(0, 3fr)", gap: 24 }} data-quebra>
              <h2 className="titulo" style={{ fontSize: 24, fontWeight: 500, letterSpacing: "-0.03em" }}>Como <em style={{ color: "var(--texto)" }}>calculamos</em></h2>
              <p className="suave" style={{ margin: 0 }}>
                {dados.criterio} As regras de limpeza rodam nos nós ESP32. Fonte: ITBI · Prefeitura de São Paulo · última carga em {dataHora(dados.ultima_carga)}.
              </p>
            </div>
          </>
        )}
      </main>
      <Rodape />
    </>
  );
}

function Legenda({ tracejado }: { tracejado: boolean }) {
  return (
    <svg width="22" height="8" aria-hidden="true" style={{ verticalAlign: "middle", marginRight: 6 }}>
      <line x1="0" y1="4" x2="22" y2="4" stroke={tracejado ? "#b5a899" : "#c6f36b"} strokeWidth="2.5" strokeDasharray={tracejado ? "4 3" : undefined} />
    </svg>
  );
}

function Carregando() {
  return (
    <div style={{ display: "grid", gap: 20 }} aria-busy="true" aria-label="Carregando">
      <div className="grade g-4">{[0, 1, 2, 3].map((i) => <div key={i} className="esqueleto" style={{ height: 170 }} />)}</div>
      <div className="esqueleto" style={{ height: 420 }} />
    </div>
  );
}
