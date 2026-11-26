import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api, ErroApi, postar, type ArquivoBronze, type DetalheExecucao, type Execucao, type Usuario } from "../api";
import { Topo, usePeriodico } from "../componentes/comuns";
import { dataHora, haQuanto, hora, numero } from "../formato";

const MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"];
const CLASSE: Record<string, string> = {
  concluida: "ok", concluido: "ok", disponivel: "ok", em_andamento: "ok pulsa", preparando: "neutro pulsa",
  processando: "ok pulsa", falhou: "alerta", offline: "alerta", nunca_conectado: "neutro",
};

interface EstadoNos {
  broker_conectado: boolean;
  nos: { no_id: string; estado: string; disponivel: boolean; simulado?: boolean; lote_atual?: string | null; mem_livre?: number | null; segundos_sem_contato?: number | null }[];
}
interface AnosFonte {
  erro_fonte: string | null;
  anos: { ano: number; na_pagina: boolean; versoes_bronze: unknown[] }[];
}

export default function Painel() {
  const navegar = useNavigate();
  const [eu, setEu] = useState<Usuario | null>(null);

  // Qualquer 401 (sessão expirada) devolve para o login.
  const chamar = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    try {
      return await fn();
    } catch (e) {
      if (e instanceof ErroApi && e.status === 401) navegar("/login", { replace: true });
      else throw e;
    }
  }, [navegar]);

  useEffect(() => {
    chamar(() => api<Usuario>("/auth/eu")).then((u) => u && setEu(u));
  }, [chamar]);

  const sair = async () => {
    await postar("/auth/logout").catch(() => {});
    navegar("/login", { replace: true });
  };

  if (!eu) return <main className="conteudo vazio">Verificando sessão…</main>;
  return (
    <>
      <Topo
        entrar={false}
        links={[["Site", "/"], ["Cluster ao vivo", "/cluster"], ["Consulta", "/consulta"]]}
        acao={<>
          <span className="suave" style={{ fontSize: 14 }}>{eu.nome || eu.usuario}</span>
          <button className="botao contorno pequeno" onClick={sair}>Sair</button>
        </>}
      />
      <main className="conteudo" style={{ paddingTop: 56, paddingBottom: 80 }}>
        <p className="rotulo">Operação</p>
        <h1 className="titulo t-2" style={{ marginBottom: 40 }}>Painel de <em>controle</em></h1>
        <Conteudo chamar={chamar} />
      </main>
    </>
  );
}

type Chamar = <T>(fn: () => Promise<T>) => Promise<T | undefined>;

function Conteudo({ chamar }: { chamar: Chamar }) {
  const [nos, setNos] = useState<EstadoNos | null>(null);
  const [arquivos, setArquivos] = useState<ArquivoBronze[]>([]);
  const [execucoes, setExecucoes] = useState<Execucao[]>([]);
  const [selecionada, setSelecionada] = useState<string | null>(null);

  usePeriodico(() => { chamar(() => api<EstadoNos>("/nos")).then((d) => d && setNos(d)).catch(() => setNos(null)); }, 3000);
  usePeriodico(() => { chamar(() => api<Execucao[]>("/execucoes?limite=30")).then((d) => d && setExecucoes(d)).catch(() => {}); }, 2500);
  const carregarArquivos = useCallback(() => {
    chamar(() => api<ArquivoBronze[]>("/arquivos")).then((d) => d && setArquivos(d)).catch(() => {});
  }, [chamar]);
  useEffect(carregarArquivos, [carregarArquivos]);

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="cartao">
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 12, marginBottom: 20 }}>
          <h2 className="titulo t-3" style={{ fontWeight: 500 }}>Nós</h2>
          <span className={`status ${nos?.broker_conectado ? "ok" : "alerta"}`}>broker {nos ? (nos.broker_conectado ? "conectado" : "desconectado") : "…"}</span>
        </div>
        <div className="grade" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          {(nos?.nos ?? []).map((n) => (
            <div key={n.no_id} style={{ background: "var(--fundo-campo)", borderRadius: 14, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <span className="mono">{n.no_id}{n.simulado ? " (sim)" : ""}</span>
                <span className={`status ${n.disponivel ? CLASSE[n.estado] ?? "ok" : "alerta"}`} style={{ fontSize: 12, padding: "3px 10px" }}>{n.estado}</span>
              </div>
              <div className="suave mono" style={{ fontSize: 12, marginTop: 10 }}>
                {n.lote_atual ?? "sem lote"} · {n.mem_livre != null ? `${numero(n.mem_livre / 1024)} KB` : "—"} · {haQuanto(n.segundos_sem_contato)}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grade g-2" style={{ alignItems: "stretch" }}>
        <Fontes chamar={chamar} arquivos={arquivos} aoMudar={carregarArquivos} />
        <NovaExecucao chamar={chamar} arquivos={arquivos} nos={nos?.nos ?? []} aoCriar={setSelecionada} />
      </div>

      <div className="cartao">
        <h2 className="titulo t-3" style={{ fontWeight: 500, marginBottom: 20 }}>Execuções</h2>
        <div className="rolagem-x">
          <table className="tabela">
            <thead><tr><th>ID</th><th>Status</th><th>Abas</th><th>Nós</th><th className="num">Progresso</th><th>Criada</th></tr></thead>
            <tbody>
              {execucoes.map((e) => (
                <tr key={e.id} onClick={() => setSelecionada(e.id)} style={{ cursor: "pointer", background: e.id === selecionada ? "var(--fundo-campo)" : undefined }}>
                  <td><button className="mono alta" style={{ background: "none", border: 0, padding: 0, cursor: "pointer" }}>{e.id}</button></td>
                  <td><span className={`status ${CLASSE[e.status] ?? "neutro"}`} style={{ fontSize: 12, padding: "3px 10px" }}>{e.status}</span></td>
                  <td style={{ maxWidth: 260, fontSize: 13 }}>{e.abas_selecionadas.join(", ")}</td>
                  <td className="mono" style={{ fontSize: 13 }}>{e.nos.join(", ")}</td>
                  <td className="num">{numero(e.processados)} / {e.total_esperado != null ? numero(e.total_esperado) : "…"}</td>
                  <td style={{ fontSize: 13, whiteSpace: "nowrap" }}>{dataHora(e.criado_em)}</td>
                </tr>
              ))}
              {execucoes.length === 0 && <tr><td colSpan={6} className="suave">Nenhuma execução ainda.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {selecionada && <Detalhe chamar={chamar} id={selecionada} aoFechar={() => setSelecionada(null)} />}
    </div>
  );
}

// ---------------------------------------------------------------- Bronze e coleta
function Fontes({ chamar, arquivos, aoMudar }: { chamar: Chamar; arquivos: ArquivoBronze[]; aoMudar: () => void }) {
  const [anos, setAnos] = useState<AnosFonte | null>(null);
  const [ano, setAno] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [msg, setMsg] = useState<{ texto: string; erro?: boolean } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    chamar(() => api<AnosFonte>("/fontes/itbi-sp/anos")).then((d) => {
      if (!d) return;
      setAnos(d);
      setAno((a) => a || String(d.anos.find((x) => x.na_pagina)?.ano ?? ""));
    }).catch((e) => setMsg({ texto: e.message, erro: true }));
  }, [chamar, arquivos.length]);

  const acompanhar = async (id: number) => {
    const c = await chamar(() => api<{ status: string; progresso: Record<string, { status: string }> }>(`/coletas/${id}`));
    if (!c) return;
    setMsg({ texto: `Coleta ${id}: ${c.status} — ${Object.entries(c.progresso).map(([a, p]) => `${a}: ${p.status}`).join(", ")}`, erro: c.status === "falhou" });
    if (c.status === "em_andamento") setTimeout(() => acompanhar(id), 2000);
    else { setOcupado(false); aoMudar(); }
  };
  const coletar = async (corpo: object) => {
    setOcupado(true);
    try {
      const r = await chamar(() => postar<{ coleta_id: number }>("/coletas/itbi-sp", corpo));
      if (r) acompanhar(r.coleta_id);
    } catch (e) { setMsg({ texto: (e as Error).message, erro: true }); setOcupado(false); }
  };
  const enviar = async () => {
    if (!arquivo) return;
    const fd = new FormData();
    fd.append("arquivo", arquivo);
    setOcupado(true);
    setMsg({ texto: "Enviando…" });
    try {
      const r = await chamar(() => postar<{ novo: boolean; arquivo: { id: number } }>("/arquivos", fd));
      if (r) setMsg({ texto: r.novo ? `Arquivo preservado: #${r.arquivo.id}` : `Já existia (mesmo SHA-256): #${r.arquivo.id}` });
      aoMudar();
    } catch (e) { setMsg({ texto: (e as Error).message, erro: true }); }
    setOcupado(false);
  };

  return (
    <div className="cartao" style={{ display: "grid", gap: 20, alignContent: "start" }}>
      <div>
        <h2 className="titulo t-3" style={{ fontWeight: 500 }}>Fontes <em style={{ color: "var(--suave)" }}>Bronze</em></h2>
        <p className="suave" style={{ fontSize: 14, margin: "6px 0 0" }}>Baixa a planilha da Prefeitura e guarda o original. Não processa nada.</p>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "end" }}>
        <label className="campo" style={{ flex: "1 1 140px" }}><span>Ano na página oficial</span>
          <select className="entrada" value={ano} onChange={(e) => setAno(e.target.value)}>
            {anos?.anos.filter((a) => a.na_pagina).map((a) => <option key={a.ano} value={a.ano}>{a.ano}{a.versoes_bronze.length ? "  ✓ já coletado" : ""}</option>)}
          </select>
        </label>
        <button className="botao primario" disabled={ocupado || !ano} onClick={() => coletar({ ano: Number(ano) })}>Coletar ano</button>
        <button className="botao contorno" disabled={ocupado} onClick={() => confirm("Baixar os arquivos de todos os anos?") && coletar({ todos: true })}>Todos</button>
      </div>
      {anos?.erro_fonte && <div className="aviso">Página oficial indisponível: {anos.erro_fonte}</div>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "end" }}>
        <label className="campo" style={{ flex: "1 1 200px" }}><span>Ou enviar um XLSX</span>
          <input className="entrada" type="file" accept=".xlsx" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} style={{ padding: 11, fontSize: 14 }} />
        </label>
        <button className="botao contorno" disabled={ocupado || !arquivo} onClick={enviar}>Enviar</button>
      </div>
      {msg && <p className={msg.erro ? "alerta" : "suave"} style={{ fontSize: 14, margin: 0 }} role="status">{msg.texto}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- nova execução
function NovaExecucao({ chamar, arquivos, nos, aoCriar }: {
  chamar: Chamar; arquivos: ArquivoBronze[]; nos: EstadoNos["nos"]; aoCriar: (id: string) => void;
}) {
  const [arquivoId, setArquivoId] = useState("");
  const [ano, setAno] = useState("");
  const [mes, setMes] = useState("");
  const [limite, setLimite] = useState("");
  const [escolhidos, setEscolhidos] = useState<Set<string> | null>(null);
  const [msg, setMsg] = useState<{ texto: string; erro?: boolean } | null>(null);

  const arq = arquivos.find((a) => String(a.id) === arquivoId) ?? arquivos[0];
  const abas = arq?.meses_disponiveis ?? [];
  const anos = [...new Set(abas.map((x) => x.split("-")[1]))].sort().reverse();
  const anoEfetivo = anos.includes(ano) ? ano : anos[0] ?? "";
  const meses = MESES.filter((m) => abas.includes(`${m}-${anoEfetivo}`));
  // Padrão: todos os nós físicos (não simulados).
  const marcados = escolhidos ?? new Set(nos.filter((n) => !n.simulado).map((n) => n.no_id));

  const iniciar = async () => {
    if (!arq) return;
    const corpo = { arquivo_id: arq.id, ano: Number(anoEfetivo), mes: mes || null, limite_registros: limite ? Number(limite) : null, nos: [...marcados] };
    try {
      const r = await chamar(() => postar<{ execucao_id: string; abas: string[] }>("/execucoes", corpo));
      if (r) { setMsg({ texto: `Criada ${r.execucao_id} (${r.abas.join(", ")})` }); aoCriar(r.execucao_id); }
    } catch (e) { setMsg({ texto: (e as Error).message, erro: true }); }
  };

  return (
    <div className="cartao" style={{ display: "grid", gap: 18 }}>
      <div>
        <h2 className="titulo t-3" style={{ fontWeight: 500 }}>Nova <em style={{ color: "var(--suave)" }}>execução</em></h2>
        <p className="suave" style={{ fontSize: 14, margin: "6px 0 0" }}>Lê as abas escolhidas e distribui os registros para os nós.</p>
      </div>
      <label className="campo"><span>Arquivo / versão</span>
        <select className="entrada" value={arq ? String(arq.id) : ""} onChange={(e) => setArquivoId(e.target.value)}>
          {arquivos.map((a) => <option key={a.id} value={a.id}>#{a.id} · {a.ano_fonte ?? "?"} · {a.nome_original} · {a.coletado_em.slice(0, 10)}</option>)}
        </select>
      </label>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10 }}>
        <label className="campo"><span>Ano</span>
          <select className="entrada" value={anoEfetivo} onChange={(e) => { setAno(e.target.value); setMes(""); }}>
            {anos.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
        <label className="campo"><span>Mês</span>
          <select className="entrada" value={mes} onChange={(e) => setMes(e.target.value)}>
            <option value="">todos</option>
            {meses.map((m) => <option key={m}>{m}</option>)}
          </select>
        </label>
        <label className="campo"><span>Limite</span>
          <input className="entrada" type="number" min={1} placeholder="sem" value={limite} onChange={(e) => setLimite(e.target.value)} />
        </label>
      </div>
      <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="suave" style={{ fontSize: 15, marginBottom: 10 }}>Nós</legend>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {nos.map((n) => {
            const ativo = marcados.has(n.no_id);
            return (
              <button key={n.no_id} type="button" aria-pressed={ativo} className="chip"
                style={{ cursor: "pointer", background: ativo ? "var(--destaque)" : "transparent", color: ativo ? "var(--tinta)" : undefined, borderColor: ativo ? "var(--destaque)" : undefined }}
                onClick={() => { const s = new Set(marcados); if (ativo) s.delete(n.no_id); else s.add(n.no_id); setEscolhidos(s); }}>
                {n.no_id}
              </button>
            );
          })}
        </div>
      </fieldset>
      <button className="botao primario" disabled={!arq || marcados.size === 0} onClick={iniciar}>Iniciar execução</button>
      {msg && <p className={msg.erro ? "alerta" : "suave"} style={{ fontSize: 14, margin: 0 }} role="status">{msg.texto}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- detalhe de uma execução
type Aba = "eventos" | "indicadores" | "metricas" | "registros";

function Detalhe({ chamar, id, aoFechar }: { chamar: Chamar; id: string; aoFechar: () => void }) {
  const [d, setD] = useState<DetalheExecucao | null>(null);
  const [aba, setAba] = useState<Aba>("eventos");
  const [extra, setExtra] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>(null);

  usePeriodico(() => { chamar(() => api<DetalheExecucao>(`/execucoes/${id}`)).then((x) => x && setD(x)).catch(() => {}); }, 2000);
  useEffect(() => { setD(null); setAba("eventos"); }, [id]);
  useEffect(() => {
    setExtra(null);
    const caminho = { eventos: null, indicadores: "indicadores", metricas: "metricas", registros: "registros?por_pagina=20&somente_erros=false" }[aba];
    if (caminho) chamar(() => api(`/execucoes/${id}/${caminho}`)).then(setExtra).catch((e) => setExtra({ erro: e.message }));
  }, [aba, id, chamar]);

  const retomar = async () => {
    const r = await chamar(() => postar<{ lotes_reabertos: number }>(`/execucoes/${id}/retomar`));
    if (r) setMsg(`${r.lotes_reabertos} lote(s) reaberto(s)`);
  };
  const atualizarGold = async () => {
    await chamar(() => postar("/gold/atualizar"));
    setMsg("Recalculando a consulta pública (Gold) em segundo plano.");
  };

  if (!d) return <div className="cartao esqueleto" style={{ height: 300 }} />;
  return (
    <div className="cartao" style={{ display: "grid", gap: 20 }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
        <h2 className="titulo t-3" style={{ fontWeight: 500 }}>Execução <span className="mono">{d.id}</span></h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="botao contorno pequeno" onClick={retomar} disabled={!d.lotes_por_estado.falhou}>Retomar lotes falhos</button>
          <button className="botao contorno pequeno" onClick={atualizarGold}>Recalcular Gold</button>
          <button className="botao contorno pequeno" onClick={aoFechar} aria-label="Fechar detalhe">✕</button>
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
        <span className={`status ${CLASSE[d.status] ?? "neutro"}`}>{d.status}</span>
        <span className="mono" style={{ fontSize: 14 }}>{numero(d.processados)} / {d.total_esperado != null ? numero(d.total_esperado) : "…"} registros</span>
        <span className="suave" style={{ fontSize: 14 }}>· {numero(d.com_erro)} com erro de campo · {numero(d.erros_leitura)} erros de leitura</span>
      </div>
      {d.mensagem && <div className="aviso">{d.mensagem}</div>}
      {msg && <p className="suave" style={{ margin: 0, fontSize: 14 }} role="status">{msg}</p>}
      <div style={{ height: 10, background: "var(--fundo-campo)", borderRadius: 99, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${d.progresso * 100}%`, background: "var(--destaque)", transition: "width .3s" }} />
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }} aria-label="Lotes">
        {d.lotes.map((l) => (
          <span key={l.id} title={`${l.id} · ${l.estado} · ${l.no_id ?? "—"} · ${l.feitos}/${l.total} · tentativa ${l.tentativas}`}
            style={{ width: 12, height: 12, borderRadius: 3, background: { concluido: "var(--destaque)", falhou: "var(--alerta)", atribuido: "var(--suave)", processando: "var(--suave)" }[l.estado] ?? "var(--linha)" }} />
        ))}
        {d.lotes.length >= 500 && <span className="suave" style={{ fontSize: 12 }}>(primeiros 500 lotes)</span>}
      </div>
      <div className="segmentado mono" style={{ maxWidth: 560 }} role="tablist">
        {(["eventos", "indicadores", "metricas", "registros"] as Aba[]).map((a) => (
          <button key={a} role="tab" aria-selected={a === aba} aria-pressed={a === aba} onClick={() => setAba(a)}>{a}</button>
        ))}
      </div>
      {aba === "eventos" ? (
        <div className="terminal"><pre>
          {d.eventos_recentes.map((e, i) => (
            <div key={i}><span className="hora">{hora(e.criado_em)}</span>  {e.tipo}  {e.lote_id?.replace(/^.*lote-/, "lote ") ?? ""} {e.no_id ?? ""} <span className="suave">{JSON.stringify(e.detalhe)}</span></div>
          ))}
        </pre></div>
      ) : extra == null ? <div className="esqueleto" style={{ height: 160 }} /> : <Dados valor={extra} />}
    </div>
  );
}

/** Mostra a resposta da API: objetos como pares chave/valor, listas de objetos como tabela. */
function Dados({ valor, nivel = 0 }: { valor: unknown; nivel?: number }) {
  if (Array.isArray(valor)) {
    if (valor.length === 0) return <span className="suave">—</span>;
    if (typeof valor[0] !== "object" || valor[0] === null) return <span className="mono">{valor.join(", ")}</span>;
    const colunas = Object.keys(valor[0] as object).filter((k) => !["dados_origem", "tipos", "dados_tratados"].includes(k));
    return (
      <div className="rolagem-x">
        <table className="tabela" style={{ fontSize: 13 }}>
          <thead><tr>{colunas.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {(valor as Record<string, unknown>[]).map((l, i) => (
              <tr key={i}>{colunas.map((c) => <td key={c} className={typeof l[c] === "number" ? "num" : "mono"} style={{ fontSize: 12 }}>{celula(l[c])}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (valor && typeof valor === "object") {
    return (
      <div style={{ display: "grid", gap: nivel ? 8 : 24 }}>
        {Object.entries(valor).map(([k, v]) => (
          v && typeof v === "object" ? (
            <div key={k}>
              <p className="rotulo" style={{ marginBottom: 10, fontSize: 11 }}>{k.replace(/_/g, " ")}</p>
              <Dados valor={v} nivel={nivel + 1} />
            </div>
          ) : (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 14, borderBottom: "1px solid var(--linha)", paddingBottom: 6 }}>
              <span className="suave">{k.replace(/_/g, " ")}</span><span className="mono">{celula(v)}</span>
            </div>
          )
        ))}
      </div>
    );
  }
  return <span className="mono">{celula(valor)}</span>;
}

function celula(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return numero(v, Number.isInteger(v) ? 0 : 2);
  if (typeof v === "object") return JSON.stringify(v);
  const s = String(v);
  return /^\d{4}-\d{2}-\d{2}T/.test(s) ? dataHora(s) : s;
}

