import type { Periodo, Tipo } from "./api";

const inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

export const numero = (v: number | null | undefined, casas = 0) =>
  v == null ? "—" : new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }).format(v);

export const reais = (v: number | null | undefined) => (v == null ? "—" : `R$ ${inteiro.format(v)}`);

/** 11900 -> "11,9 mil" */
export const mil = (v: number | null | undefined) => (v == null ? "—" : `${numero(v / 1000, 1)} mil`);

/** Variação sempre com seta e sinal, nunca só cor (guia de estilo). */
export function variacao(v: number | null | undefined): { texto: string; classe: string } {
  if (v == null) return { texto: "—", classe: "suave" };
  if (v === 0) return { texto: "0,0%", classe: "suave" };
  return v > 0
    ? { texto: `▲ +${numero(v, 1)}%`, classe: "alta" }
    : { texto: `▼ ${numero(v, 1)}%`, classe: "alerta" };
}

export const NOMES_TIPO: Record<Tipo, [string, string]> = {
  apartamento: ["Apartamento", "apartamentos"],
  casa: ["Casa", "casas"],
  comercial: ["Comercial", "imóveis comerciais"],
  terreno: ["Terreno", "terrenos"],
};

export const NOMES_PERIODO: Record<Periodo, [string, string]> = {
  "12m": ["12 meses", "nos últimos 12 meses"],
  "3a": ["3 anos", "nos últimos 3 anos"],
  "5a": ["5 anos", "nos últimos 5 anos"],
  tudo: ["Tudo", "em todo o histórico"],
};

const MINUSCULAS = new Set(["DA", "DAS", "DE", "DO", "DOS", "E"]);
const PREFIXOS: Record<string, string> = {
  R: "Rua", AV: "Av.", AL: "Alameda", TV: "Travessa", PC: "Praça", EST: "Estrada", ROD: "Rodovia",
  LGO: "Largo", VL: "Viela", DR: "Dr.", PROF: "Prof.", CEL: "Cel.", GAL: "Gal.", PRES: "Pres.", ENG: "Eng.",
};

/** "R DOS PINHEIROS" -> "Rua dos Pinheiros"; "ALTO DE PINHEIROS" -> "Alto de Pinheiros". */
export function nomeProprio(texto: string | null | undefined): string {
  if (!texto) return "";
  return texto
    .trim()
    .toUpperCase()
    .split(/\s+/)
    .map((p, i) => {
      if (PREFIXOS[p]) return PREFIXOS[p];
      if (i > 0 && MINUSCULAS.has(p)) return p.toLowerCase();
      return p.charAt(0) + p.slice(1).toLowerCase();
    })
    .join(" ");
}

const TRIMESTRES = ["1º", "2º", "3º", "4º"];
export function trimestre(iso: string): string {
  const [a, m] = iso.split("-").map(Number);
  return `${TRIMESTRES[Math.floor((m - 1) / 3)]} tri ${a}`;
}

/** "2019-04-01" -> "T2·19", para o eixo do gráfico. */
export function trimestreCurto(iso: string): string {
  const [a, m] = iso.split("-").map(Number);
  return `T${Math.floor((m - 1) / 3) + 1}·${String(a).slice(2)}`;
}

export function mesAno(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("pt-BR", { month: "short", year: "numeric" }).replace(/\.?( de)? /, "/");
}

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function hora(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour12: false });
}

export function haQuanto(segundos: number | null | undefined): string {
  if (segundos == null) return "—";
  if (segundos < 60) return `há ${Math.round(segundos)} s`;
  if (segundos < 3600) return `há ${Math.round(segundos / 60)} min`;
  if (segundos < 86400) return `há ${Math.round(segundos / 3600)} h`;
  return `há ${Math.round(segundos / 86400)} d`;
}

export function baixarCsv(nome: string, linhas: (string | number | null)[][]) {
  const csv = linhas
    .map((l) => l.map((c) => (c == null ? "" : /[;"\n]/.test(String(c)) ? `"${String(c).replace(/"/g, '""')}"` : String(c))).join(";"))
    .join("\n");
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nome });
  a.click();
  URL.revokeObjectURL(url);
}
