// Cliente da API FastAPI. O front é servido pela própria API (mesma origem), então o cookie de sessão
// do painel vai junto em toda chamada.

export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

export async function api<T>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  const cabecalhos: Record<string, string> = {};
  if (opcoes.body && !(opcoes.body instanceof FormData)) cabecalhos["content-type"] = "application/json";
  const r = await fetch(caminho, { credentials: "same-origin", ...opcoes, headers: { ...cabecalhos, ...opcoes.headers } });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detalhe = corpo?.detail;
    const msg = typeof detalhe === "string" ? detalhe : detalhe ? JSON.stringify(detalhe) : r.statusText;
    throw new ErroApi(r.status, msg);
  }
  return corpo as T;
}

export const postar = <T>(caminho: string, corpo?: unknown) =>
  api<T>(caminho, { method: "POST", body: corpo instanceof FormData ? corpo : JSON.stringify(corpo ?? {}) });

// ---------------------------------------------------------------- consulta
export type Tipo = "apartamento" | "casa" | "comercial" | "terreno";
export type Periodo = "12m" | "3a" | "5a" | "tudo";

export interface Filtros {
  bairro: string;
  rua: string;
  tipo: Tipo;
  areaMin: number | null;
  areaMax: number | null;
  periodo: Periodo;
  comparar: boolean;
}

export interface ResultadoPreco {
  criterio: string;
  amostra_minima: number;
  ultima_carga: string | null;
  referencia: string | null;
  resumo: null | {
    transacoes: number;
    preco_m2_medio: number | null;
    p25: number | null;
    p75: number | null;
    inicio: string | null;
    cidade_preco_m2_medio: number | null;
    variacao_12m: number | null;
    variacao_12m_cidade: number | null;
  };
  serie: { trimestre: string; local: number; transacoes: number; cidade: number }[];
  por_tipo: { tipo: Tipo; transacoes: number; preco_m2_medio: number }[];
  ruas: { logradouro: string; transacoes: number; preco_m2_medio: number; variacao_12m: number | null }[];
}

export function filtrosParaBusca(f: Filtros): URLSearchParams {
  const p = new URLSearchParams({ tipo: f.tipo, periodo: f.periodo });
  if (f.bairro.trim()) p.set("bairro", f.bairro.trim());
  if (f.rua.trim()) p.set("rua", f.rua.trim());
  if (f.areaMin != null) p.set("area_min", String(f.areaMin));
  if (f.areaMax != null) p.set("area_max", String(f.areaMax));
  if (!f.comparar) p.set("comparar", "0");
  return p;
}

export function buscaParaFiltros(p: URLSearchParams): Filtros {
  const num = (v: string | null) => (v != null && v !== "" && !isNaN(Number(v)) ? Number(v) : null);
  const tipo = p.get("tipo") as Tipo;
  const periodo = p.get("periodo") as Periodo;
  return {
    bairro: p.get("bairro") ?? "",
    rua: p.get("rua") ?? "",
    tipo: ["apartamento", "casa", "comercial", "terreno"].includes(tipo) ? tipo : "apartamento",
    areaMin: num(p.get("area_min")),
    areaMax: num(p.get("area_max")),
    periodo: ["12m", "3a", "5a", "tudo"].includes(periodo) ? periodo : "tudo",
    comparar: p.get("comparar") !== "0",
  };
}

export function consultarPreco(f: Filtros) {
  const p = filtrosParaBusca(f);
  p.delete("comparar"); // só muda a exibição
  return api<ResultadoPreco>(`/consulta/preco-m2?${p}`);
}

// ---------------------------------------------------------------- cluster
export interface NoCluster {
  no_id: string;
  estado: string;
  disponivel: boolean;
  simulado?: boolean;
  lote_atual?: string | null;
  mem_livre?: number | null;
  segundos_sem_contato?: number | null;
  lotes_processados: number;
  tempo_medio_lote_s?: number | null;
  registros: number;
}

export interface EventoLog {
  id: number;
  criado_em: string;
  tipo: string;
  execucao_id: string | null;
  lote_id: string | null;
  no_id: string | null;
  detalhe: Record<string, unknown>;
}

export interface EstadoCluster {
  broker_conectado: boolean;
  tamanho_lote: number;
  registros_validados: number;
  registros_com_erro: number;
  taxa_erro: number;
  vazao_reg_s: number;
  nos_ativos: number;
  nos: NoCluster[];
  execucao: null | {
    id: string;
    status: string;
    total_esperado: number | null;
    ano: number;
    mes: string | null;
    concluido_em: string | null;
    lotes: number;
    lotes_concluidos: number;
    lotes_na_fila: number;
    lotes_em_voo: number;
    processados: number;
  };
  log: EventoLog[];
  esteira: ItemEsteira[];
}

/** Registro recém-devolvido por um nó, com os campos que a limpeza alterou. */
export interface ItemEsteira {
  id: number;
  recebido_em: string;
  no_id: string;
  lote_id: string;
  posicao: number;
  aba: string;
  linha: number;
  duracao_us: number | null;
  logradouro: string | null;
  numero: string | null;
  bairro: string | null;
  valor_transacao: string | null;
  mudancas: { campo: string; antes: string | null; depois: string | null }[];
  erros: { campo: string; motivo: string; valor_original?: unknown }[];
}

// ---------------------------------------------------------------- painel
export interface Usuario {
  usuario: string;
  nome: string | null;
}

export interface ArquivoBronze {
  id: number;
  nome_original: string;
  ano_fonte: number | null;
  coletado_em: string;
  meses_disponiveis: string[];
  [k: string]: unknown;
}

export interface Execucao {
  id: string;
  status: string;
  ano: number;
  mes: string | null;
  abas_selecionadas: string[];
  nos: string[];
  total_esperado: number | null;
  processados: number;
  criado_em: string;
}

export interface DetalheExecucao extends Execucao {
  mensagem: string | null;
  com_erro: number;
  erros_leitura: number;
  progresso: number;
  lotes_por_estado: Record<string, number>;
  lotes: { id: string; numero: number; no_id: string | null; estado: string; total: number; feitos: number; tentativas: number }[];
  eventos_recentes: { tipo: string; lote_id: string | null; no_id: string | null; detalhe: Record<string, unknown>; criado_em: string }[];
}
