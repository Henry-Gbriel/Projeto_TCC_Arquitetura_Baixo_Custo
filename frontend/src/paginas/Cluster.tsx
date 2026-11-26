import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { api, type EstadoCluster, type EventoLog, type ItemEsteira, type NoCluster } from "../api";
import { Contador, PlacaEsp32, Rodape, Topo, usePeriodico } from "../componentes/comuns";
import { haQuanto, hora, nomeProprio, numero, reais } from "../formato";

const INTERVALO_MS = 2000;
const TRABALHANDO = new Set(["recebendo", "processando", "publicando"]);

function situacao(n: NoCluster): { rotulo: string; classe: string } {
  if (!n.disponivel) return { rotulo: n.estado === "nunca_conectado" ? "Nunca conectou" : "Sem sinal", classe: "alerta" };
  if (n.lote_atual || TRABALHANDO.has(n.estado)) return { rotulo: "Processando", classe: "ok pulsa" };
  return { rotulo: "Disponível", classe: "neutro" };
}

/** Uma linha do log no formato "hora  origem  mensagem", com cor para nós e alertas. */
function linhaLog(e: EventoLog): { origem: string; texto: string; cor?: string } {
  const lote = e.lote_id?.replace(/^.*lote-/, "lote ") ?? "";
  const d = e.detalhe as Record<string, string | number | null>;
  switch (e.tipo) {
    case "lote_atribuido": return { origem: "mqtt", texto: `${lote} → ${e.no_id}`, cor: "var(--destaque)" };
    case "lote_concluido": return { origem: e.no_id ?? "nó", texto: `${lote} concluído · ${d.registros ?? "?"} registros gravados` };
    case "reenvio": return { origem: "mqtt", texto: `reenvio para ${e.no_id} · ${lote}`, cor: "var(--alerta)" };
    case "tentativa_expirada": return { origem: "monitor", texto: `${lote} expirou em ${e.no_id} (${d.motivo}) → ${d.novo_estado}`, cor: "var(--alerta)" };
    case "no_silencioso": return { origem: "monitor", texto: `${e.no_id} sem sinal há ${Math.round(Number(d.segundos))} s`, cor: "var(--alerta)" };
    case "estado_no": return { origem: e.no_id ?? "nó", texto: `estado: ${d.anterior ?? "—"} → ${d.estado}`, cor: d.estado === "offline" ? "var(--alerta)" : undefined };
    case "execucao_criada": return { origem: "api", texto: `${e.execucao_id} criada` };
    case "preparacao_concluida": return { origem: "api", texto: `${e.execucao_id} pronta · ${d.lotes ?? "?"} lotes na fila` };
    case "execucao_concluida": return { origem: "api", texto: `${e.execucao_id} concluída · ${numero(Number(d.registros))} registros`, cor: "var(--destaque)" };
    case "execucao_falhou": return { origem: "api", texto: `${e.execucao_id} falhou`, cor: "var(--alerta)" };
    case "erro_leitura": return { origem: "leitor", texto: `erro de leitura · ${JSON.stringify(d)}`, cor: "var(--alerta)" };
    default: return { origem: "api", texto: `${e.tipo.replace(/_/g, " ")} ${e.execucao_id ?? ""} ${lote}` };
  }
}

export default function Cluster() {
  const [c, setC] = useState<EstadoCluster | null>(null);
  const [erro, setErro] = useState(false);
  usePeriodico(() => {
    api<EstadoCluster>("/cluster").then((d) => { setC(d); setErro(false); }).catch(() => setErro(true));
  }, INTERVALO_MS);

  const log = useRef<HTMLPreElement>(null);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight }); }, [c?.log[0]?.id]);

  const ex = c?.execucao;
  const emAndamento = ex && (ex.status === "em_andamento" || ex.status === "preparando");
  return (
    <>
      <Topo links={[["Início", "/"], ["Sobre o projeto", "/sobre"]]} acao={<Link to="/consulta" className="botao primario pequeno">Consultar preço</Link>} />
      <main className="conteudo" style={{ paddingTop: 72 }}>
        <p className="rotulo">Cluster · ao vivo</p>
        <h1 className="titulo t-1">A sala das <em>máquinas</em></h1>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 20, justifyContent: "space-between", alignItems: "flex-end", margin: "28px 0 44px" }}>
          <p className="lead" style={{ margin: 0 }}>
            Três ESP32 recebem os registros pelo broker MQTT, aplicam as regras de limpeza em paralelo e devolvem o resultado para a API.
          </p>
          {erro ? <span className="status alerta">API indisponível</span> : ex && (
            <span className="chip" style={{ fontFamily: "var(--sans)", fontSize: 15, padding: "10px 18px" }}>
              <span className={`status ${emAndamento ? "ok pulsa" : "neutro"}`} style={{ padding: 0, background: "none", color: emAndamento ? "var(--destaque)" : "var(--suave)", border: 0 }} />
              {emAndamento
                ? `Carga em andamento · lote ${ex.lotes_concluidos + ex.lotes_em_voo} de ${ex.lotes} · ${ex.id}`
                : `Última carga: ${ex.id} (${ex.mes ?? "ano"} ${ex.ano}) ${ex.status === "concluida" ? "concluída" : ex.status}`}
            </span>
          )}
        </div>

        <div className="grade g-4">
          <Kpi nome="Registros processados" valor={<Contador valor={c?.registros_validados} formatar={(v) => numero(Math.round(v))} />} />
          <Kpi nome="Registros com erro de campo" valor={c ? `${numero(c.taxa_erro * 100, 1)}%` : "—"} />
          <Kpi nome="Vazão do cluster" valor={<>{c ? numero(c.vazao_reg_s, 1) : "—"}<small>reg/s</small></>} nota="média do último minuto" />
          <Kpi nome="Nós ativos" valor={<>{c?.nos_ativos ?? "—"}<small>de {c?.nos.length ?? 3}</small></>} />
        </div>

        <div className="grade g-3" style={{ marginTop: 20 }}>
          {(c?.nos ?? []).map((n) => {
            const s = situacao(n);
            const linhas: [string, string, boolean?][] = n.disponivel
              ? [["Lotes processados", numero(n.lotes_processados)], ["Registros processados", numero(n.registros)],
                 ["Tempo médio por lote", n.tempo_medio_lote_s != null ? `${numero(n.tempo_medio_lote_s, 2)} s` : "—"],
                 ["Memória livre (heap)", n.mem_livre != null ? `${numero(n.mem_livre / 1024)} KB` : "—"],
                 ["Último sinal", haQuanto(n.segundos_sem_contato)]]
              : [["Lotes processados", numero(n.lotes_processados)], ["Registros processados", numero(n.registros)],
                 ["Último sinal", haQuanto(n.segundos_sem_contato), true]];
            return (
              <div key={n.no_id} className={`cartao ${n.disponivel ? "" : "tracejado"}`}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                  <span className="mono" style={{ fontSize: 24, color: n.disponivel ? "var(--texto)" : "var(--suave)" }}>
                    {n.no_id}{n.simulado ? <small className="suave" style={{ fontSize: 12 }}> sim</small> : null}
                  </span>
                  <span className={`status ${s.classe}`}>{s.rotulo}</span>
                </div>
                <PlacaEsp32 ligada={n.disponivel} />
                <dl style={{ margin: 0, display: "grid", gap: 10 }}>
                  {linhas.map(([k, v, alerta]) => (
                    <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                      <dt className="suave">{k}</dt><dd className={`mono ${alerta ? "alerta" : ""}`} style={{ margin: 0 }}>{v}</dd>
                    </div>
                  ))}
                </dl>
                {!n.disponivel && (
                  <p style={{ fontSize: 15, marginBottom: 0 }}>
                    {emAndamento ? "Os lotes deste nó voltam para a fila e são redistribuídos entre os outros." : "Fora do ar. Quando voltar, ele recebe lotes de novo."}
                  </p>
                )}
                {n.disponivel && n.lote_atual && <p className="mono suave" style={{ fontSize: 13, marginBottom: 0 }}>{n.lote_atual}</p>}
              </div>
            );
          })}
        </div>

        <div className="grade" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(0, 3fr)", marginTop: 20 }} data-quebra>
          <div className="cartao">
            <h2 className="titulo t-3" style={{ fontWeight: 500, fontSize: 26, marginBottom: 28 }}>Fluxo dos <em style={{ color: "var(--texto)" }}>lotes</em></h2>
            {[
              ["API · gera lotes", `${c?.tamanho_lote ?? "—"} reg/lote`, false],
              ["Mosquitto · fila MQTT", c ? (c.broker_conectado ? `${ex?.lotes_na_fila ?? 0} na fila` : "desconectado") : "—", false],
              ["Nós ESP32 · limpeza", `${c?.nos_ativos ?? 0} ativos`, (c?.nos_ativos ?? 0) > 0],
              ["PostgreSQL · gravação", c ? "OK" : "—", false],
            ].map(([nome, valor, destaque], i, todos) => (
              <div key={String(nome)}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "18px 22px", borderRadius: 14,
                  background: destaque ? "var(--destaque)" : "var(--fundo-campo)", color: destaque ? "var(--tinta)" : undefined }}>
                  <span>{nome}</span><span className="mono" style={{ opacity: destaque ? 1 : 0.8 }}>{valor}</span>
                </div>
                {i < todos.length - 1 && <div className="suave" style={{ padding: "6px 24px" }} aria-hidden="true">↓</div>}
              </div>
            ))}
          </div>
          <div className="terminal">
            <header><span>log · tcc/nos/#</span><span aria-hidden="true"><i /><i /><i /></span></header>
            <pre aria-live="off" ref={log}>
              {(c?.log ?? []).slice().reverse().map((e) => {
                const l = linhaLog(e);
                return (
                  <div key={e.id}>
                    <span className="hora">{hora(e.criado_em)}</span>{"  "}
                    <span style={{ display: "inline-block", minWidth: 80 }}>{l.origem}</span>{"  "}
                    <span style={{ color: l.cor }}>{l.texto}</span>
                  </div>
                );
              })}
              {c && c.log.length === 0 && <span className="suave">Nenhum evento ainda.</span>}
            </pre>
          </div>
        </div>
        <Esteira itens={c?.esteira ?? []} carregado={!!c} />

        <p className="suave" style={{ fontSize: 14, marginTop: 28 }}>
          Dados lidos da API (<span className="mono">/cluster</span>) a cada {INTERVALO_MS / 1000} s. Para iniciar cargas, use o <Link to="/painel" className="alta">painel de controle</Link>.
        </p>
      </main>
      <Rodape />
    </>
  );
}

function Kpi({ nome, valor, nota }: { nome: string; valor: React.ReactNode; nota?: string }) {
  return (
    <div className="cartao kpi" style={{ padding: "24px 28px" }}>
      <div className="nome">{nome}</div>
      <div className="valor">{valor}</div>
      {nota && <div className="nota" style={{ fontSize: 13 }}>{nota}</div>}
    </div>
  );
}

/** Esteira: os últimos registros devolvidos pelos nós, com o que a limpeza mudou em cada um. */
function Esteira({ itens, carregado }: { itens: ItemEsteira[]; carregado: boolean }) {
  return (
    <section className="cartao" style={{ marginTop: 20 }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "baseline", gap: 12, marginBottom: 20 }}>
        <h2 className="titulo t-3" style={{ fontWeight: 500, fontSize: 26, margin: 0 }}>Esteira de <em style={{ color: "var(--texto)" }}>registros</em></h2>
        <span className="suave" style={{ fontSize: 14 }}>Últimos {itens.length || ""} registros limpos pelos nós · campo: <s>antes</s> → depois</span>
      </div>
      {carregado && itens.length === 0 && <p className="suave" style={{ margin: 0 }}>Nenhum registro processado ainda.</p>}
      <ol className="esteira">
        {itens.map((r) => {
          const endereco = [nomeProprio(r.logradouro), r.numero].filter(Boolean).join(", ");
          const valor = r.valor_transacao != null && !isNaN(Number(r.valor_transacao)) ? reais(Number(r.valor_transacao)) : r.valor_transacao;
          return (
            <li key={r.id}>
              <div className="esteira-cabeca">
                <span className="chip">{r.no_id}</span>
                <span className="esteira-endereco">{endereco || "—"}{r.bairro && <span className="suave"> · {nomeProprio(r.bairro)}</span>}</span>
                {valor && <span className="mono">{valor}</span>}
                <span className="mono suave esteira-meta">
                  {r.aba} · linha {r.linha}{r.duracao_us != null && ` · ${numero(r.duracao_us / 1000, 1)} ms`} · {hora(r.recebido_em)}
                </span>
              </div>
              {(r.mudancas.length > 0 || r.erros.length > 0) && (
                <ul className="esteira-mudancas">
                  {r.mudancas.map((m) => (
                    <li key={m.campo}>
                      <span className="suave">{m.campo}:</span> <s>{visivel(m.antes)}</s> → <span className="alta">{visivel(m.depois)}</span>
                    </li>
                  ))}
                  {r.erros.map((e, i) => (
                    <li key={`erro-${i}`} className="alerta">⚠ {e.campo}: {e.motivo}</li>
                  ))}
                </ul>
              )}
              {r.mudancas.length === 0 && r.erros.length === 0 && <p className="suave mono" style={{ fontSize: 13, margin: "8px 0 0" }}>sem alterações</p>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Mostra espaços nas pontas e valores vazios, que são justamente o que a limpeza costuma corrigir. */
function visivel(v: string | null): string {
  if (v == null) return "∅";
  if (v === "") return "\"\"";
  return v.replace(/^ +| +$/g, (m) => "·".repeat(m.length));
}
