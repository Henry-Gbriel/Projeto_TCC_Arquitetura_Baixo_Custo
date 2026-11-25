import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Rodape, Topo } from "../componentes/comuns";
import { CONTEUDO } from "../conteudo";

const FLUXO: [string, string][] = [
  ["Prefeitura", "arquivos ITBI"], ["API · leitura", "Python"], ["Mosquitto", "MQTT"], ["3 × ESP32", "limpeza"], ["PostgreSQL", "Alembic"],
];

function Secao({ id, numero, legenda, titulo, children }: { id: string; numero: string; legenda: string; titulo: React.ReactNode; children: React.ReactNode }) {
  return (
    <section id={id} className="bloco" style={{ borderTop: "1px solid var(--linha)" }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "baseline", gap: 12, marginBottom: 32 }}>
        <h2 className="titulo t-2">{titulo}</h2>
        <span className="mono suave" style={{ fontSize: 13 }}>{numero} — {legenda}</span>
      </div>
      {children}
    </section>
  );
}

const EXTENSOES = ["jpg", "jpeg", "png", "webp"];

/** Foto de frontend/public/fotos/{arquivo}.{jpg|jpeg|png|webp}; sem o arquivo, mostra `reserva` ou o marcador [FOTO]. */
function Imagem({ arquivo, descricao, raio = 12, reserva, estilo }: {
  arquivo: string; descricao: string; raio?: number | string; reserva?: React.ReactNode; estilo?: React.CSSProperties;
}) {
  const [tentativa, setTentativa] = useState(0);
  // Com extensão no nome, usa o arquivo direto; sem extensão, tenta as extensões em ordem.
  const candidatos = /\.\w+$/.test(arquivo) ? [arquivo] : EXTENSOES.map((e) => `${arquivo}.${e}`);
  const base: React.CSSProperties = { width: "100%", height: "100%", borderRadius: raio };
  if (tentativa >= candidatos.length) {
    if (reserva) return <>{reserva}</>;
    return (
      <div style={{ ...base, background: "#2b231d", display: "grid", placeItems: "center", textAlign: "center", padding: 8 }}>
        <span className="mono suave" style={{ fontSize: 11 }}>[FOTO]<br />fotos/{candidatos[0]}</span>
      </div>
    );
  }
  return <img src={`fotos/${candidatos[tentativa]}`} alt={descricao} loading="lazy"
    onError={() => setTentativa((t) => t + 1)} style={{ ...base, objectFit: "cover", ...estilo }} />;
}

function Foto({ arquivo, legenda, altura = 220, classe, posicao }: {
  arquivo: string; legenda: string; altura?: number | string; classe?: string; posicao?: string;
}) {
  return (
    <figure className={classe} style={{ margin: 0, position: "relative", height: altura, borderRadius: "var(--raio-cartao)", border: "1px solid var(--linha)", overflow: "hidden" }}>
      <Imagem arquivo={arquivo} descricao={legenda} raio={0} estilo={posicao ? { objectPosition: posicao } : undefined} />
      <figcaption className="chip" style={{ position: "absolute", left: 14, bottom: 14, background: "var(--fundo)", fontFamily: "var(--sans)" }}>{legenda}</figcaption>
    </figure>
  );
}

/** Cartão de pessoa (autor e orientador têm o mesmo tamanho e a mesma estrutura). */
function Pessoa({ foto, iniciais, nome, papel, subtitulo, bio, links, destaque = false }: {
  foto: string; iniciais: string; nome: string; papel: string; subtitulo?: string; bio: string;
  links: [string, string][]; destaque?: boolean;
}) {
  const iniciaisGrandes = (
    <div style={{ width: "100%", height: "100%", borderRadius: "50%", display: "grid", placeItems: "center", fontWeight: 600, fontSize: 48,
      letterSpacing: "-0.04em", background: destaque ? "var(--tinta)" : "var(--fundo-campo)", color: "var(--destaque)" }}>{iniciais}</div>
  );
  return (
    <article className={`cartao ${destaque ? "destaque" : ""}`} style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ width: 168, height: 168, borderRadius: "50%", overflow: "hidden", flex: "none",
        boxShadow: `0 0 0 4px ${destaque ? "var(--tinta)" : "var(--destaque)"}` }}>
        {/* scale corta a moldura que já vem em algumas fotos redondas */}
        <Imagem arquivo={foto} descricao={nome} raio="50%" reserva={iniciaisGrandes} estilo={{ objectPosition: "center 20%", transform: "scale(1.08)" }} />
      </div>
      <p className="rotulo" style={{ fontSize: 11, margin: "24px 0 10px", color: destaque ? "var(--tinta)" : "var(--destaque)" }}>{papel}</p>
      <h3 className="titulo t-3" style={{ marginBottom: subtitulo ? 6 : 14 }}>{nome}</h3>
      {subtitulo && <p style={{ margin: "0 0 14px", fontSize: 14, fontWeight: 500 }}>{subtitulo}</p>}
      <p className={`bio ${destaque ? "" : "suave"}`} style={{ fontSize: 15, margin: "0 0 20px" }}>{bio}</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: "auto" }}>
        {links.map(([n, h], i) => (
          <Linkado key={n} href={h} classe={destaque
            ? `botao pequeno ${i === 0 ? "escuro" : "contorno-tinta"}`
            : i === 0 ? "botao primario pequeno" : "botao contorno pequeno"}>{n} ↗</Linkado>
        ))}
      </div>
    </article>
  );
}

/** Cartão de download com prévia (capa); confere se o arquivo existe antes de oferecer o botão. */
function Material({ sigla, titulo, texto, arquivo, nomeDownload, acao, baixar, capa, pagina = false }: {
  sigla: string; titulo: string; texto: string; arquivo: string; nomeDownload?: string; acao: string; baixar: boolean; capa?: string;
  pagina?: boolean; // capa de documento (página, slide, banner): mostra a folha inteira, sem cortar
}) {
  const url = `downloads/${arquivo}`;
  const [tamanho, setTamanho] = useState<number | null | undefined>(undefined); // undefined = verificando, null = não existe
  const [semCapa, setSemCapa] = useState(!capa);
  useEffect(() => {
    fetch(url, { method: "HEAD" })
      .then((r) => setTamanho(r.ok && !(r.headers.get("content-type") ?? "").includes("text/html") ? Number(r.headers.get("content-length")) : null))
      .catch(() => setTamanho(null));
  }, [url]);
  const existe = tamanho != null;
  const atributos = baixar ? { download: nomeDownload ?? arquivo } : { target: "_blank", rel: "noreferrer" };
  const previa = (
    <div style={{ height: 210, borderRadius: 14, overflow: "hidden", background: semCapa ? "var(--fundo-campo)" : pagina ? "#d9d2c7" : "#fff",
      display: "grid", placeItems: "center", border: "1px solid var(--linha)" }}>
      {semCapa
        ? <span className="mono alta" style={{ fontSize: 28, fontWeight: 500 }}>{sigla}</span>
        : <img src={capa} alt={`Prévia: ${titulo}`} loading="lazy" onError={() => setSemCapa(true)}
            style={pagina ? { height: 184, width: "auto", boxShadow: "0 6px 18px rgba(0,0,0,.25)" } : { width: "100%", height: "100%", objectFit: "cover", objectPosition: "center top" }} />}
    </div>
  );
  return (
    <div className="cartao" style={{ display: "flex", flexDirection: "column", gap: 14, padding: 20 }}>
      {existe ? <a href={url} {...atributos} aria-label={`${acao}: ${titulo}`} className="previa">{previa}</a> : previa}
      <div>
        <strong style={{ fontWeight: 500, fontSize: 20, letterSpacing: "-0.02em" }}>{titulo}</strong>
        <span className="chip" style={{ marginLeft: 10, fontSize: 11, padding: "2px 8px", verticalAlign: "middle" }}>{sigla}</span><br />
        <span className="suave mono" style={{ fontSize: 12, overflowWrap: "anywhere" }}>
          {nomeDownload ?? arquivo}{tamanho ? ` · ${tamanho > 1e6 ? `${(tamanho / 1e6).toFixed(1).replace(".", ",")} MB` : `${Math.round(tamanho / 1e3)} KB`}` : ""}
        </span>
      </div>
      <p className="suave" style={{ margin: 0, fontSize: 15 }}>{texto}</p>
      <div style={{ marginTop: "auto" }}>
        {existe ? (
          <a className="botao contorno pequeno" href={url} {...atributos}>{baixar ? "↓" : "↗"} {acao}</a>
        ) : (
          <span className="chip" style={{ color: "var(--suave)" }}>{tamanho === undefined ? "verificando…" : "em breve"}</span>
        )}
      </div>
    </div>
  );
}

const Linkado = ({ href, children, classe = "botao contorno pequeno" }: { href: string; children: React.ReactNode; classe?: string }) =>
  href ? <a className={classe} href={href} target="_blank" rel="noreferrer">{children}</a>
       : <span className={classe} style={{ opacity: 0.5 }} title="Link ainda não preenchido em src/conteudo.ts">{children}</span>;

export default function Sobre() {
  const [escolhido, setEscolhido] = useState(CONTEUDO.componentes[0].id);
  const comp = CONTEUDO.componentes.find((c) => c.id === escolhido)!;
  const { autor, orientador, professores, instituicao } = CONTEUDO;
  return (
    <>
      <Topo
        links={[["Componentes", "#componentes"], ["Tecnologias", "#tecnologias"], ["Fotos", "#fotos"], ["Equipe", "#equipe"], ["Materiais", "#materiais"], ["Instituição", "#instituicao"]]}
        acao={<Link to="/consulta" className="botao primario pequeno">Consultar preço</Link>}
      />
      <main className="conteudo">
        <section className="bloco">
          <p className="rotulo">Sobre o projeto</p>
          <h1 className="titulo t-1">Por dentro do <em>projeto</em>, peça por peça.</h1>
          <p className="lead" style={{ marginTop: 28 }}>
            O hardware que monta o cluster, as ferramentas gratuitas que sustentam a pilha, os bastidores da construção e quem está por trás dela.
          </p>
        </section>

        <Secao id="componentes" numero="001" legenda="hardware" titulo={<>Componentes <em>físicos</em></>}>
          <p className="suave" style={{ marginTop: -12 }}>Escolha um componente para ver a ficha <em className="enfase" style={{ color: "var(--suave)" }}>dele.</em></p>
          <div className="grade" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.25fr)", marginTop: 24 }} data-quebra>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 12, alignContent: "start" }}>
              {CONTEUDO.componentes.map((c) => (
                <button key={c.id} onClick={() => setEscolhido(c.id)} aria-pressed={c.id === escolhido} className="cartao"
                  style={{ padding: 10, cursor: "pointer", textAlign: "left", borderColor: c.id === escolhido ? "var(--destaque)" : undefined }}>
                  <div style={{ height: 96 }}><Imagem arquivo={c.foto} descricao={c.nome} /></div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginTop: 10 }}>
                    <span>{c.nome}</span><span className="mono alta">× {c.qtd}</span>
                  </div>
                </button>
              ))}
            </div>
            <div className="cartao" style={{ display: "grid", gap: 24, alignContent: "start" }}>
              <div style={{ height: 260 }}><Imagem key={comp.foto} arquivo={comp.foto} descricao={comp.nome} raio={16}
                estilo={{ objectFit: "contain", background: "var(--fundo-campo)" }} /></div>
              <div>
                <p className="rotulo alta" style={{ marginBottom: 10, color: "var(--destaque)" }}>{comp.papel} · × {comp.qtd}</p>
                <h3 className="titulo t-3" style={{ marginBottom: 14 }}>{comp.nome}</h3>
                <p className="suave" style={{ fontSize: 15 }}>{comp.texto}</p>
                <ul style={{ listStyle: "none", padding: 0, margin: "16px 0", display: "grid", gap: 6 }}>
                  {comp.specs.map((s) => (
                    <li key={s} className="mono" style={{ fontSize: 13 }}><span className="alta" aria-hidden="true">■ </span>{s}</li>
                  ))}
                </ul>
                {comp.link && <Linkado href={comp.link[1]} classe="botao primario pequeno">{comp.link[0]} ↗</Linkado>}
              </div>
            </div>
          </div>
          <div className="cartao" style={{ marginTop: 20 }}>
            <p style={{ margin: "0 0 18px" }}>Como as peças se <em className="enfase">conectam</em></p>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
              {FLUXO.map(([nome, sub], i) => (
                <span key={nome} style={{ display: "contents" }}>
                  <span style={{ flex: "1 1 120px", textAlign: "center", padding: "12px 10px", borderRadius: 12, border: "1px solid var(--linha)",
                    background: nome.includes("ESP32") ? "var(--destaque)" : "transparent", color: nome.includes("ESP32") ? "var(--tinta)" : undefined, fontSize: 14 }}>
                    {nome}<br /><small style={{ opacity: 0.7 }}>{sub}</small>
                  </span>
                  {i < FLUXO.length - 1 && <span className="suave" aria-hidden="true">→</span>}
                </span>
              ))}
            </div>
            <div style={{ marginTop: 10, textAlign: "center", padding: 12, borderRadius: 12, border: "1px solid var(--linha)", fontSize: 14 }}>
              API + Front<br /><small className="suave">você</small>
            </div>
          </div>
        </Secao>

        <Secao id="tecnologias" numero="002" legenda="custo de software: R$ 0,00" titulo={<>Tecnologias <em>utilizadas</em></>}>
          <div className="grade g-3">
            {CONTEUDO.tecnologias.map(([grupo, itens]) => (
              <div key={grupo} className="cartao" style={{ padding: 22 }}>
                <p className="rotulo" style={{ fontSize: 11, marginBottom: 16 }}>{grupo}</p>
                {itens.map(([sigla, nome]) => (
                  <div key={nome} style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 10, fontSize: 15 }}>
                    <span className="mono alta" style={{ fontSize: 11, width: 30, height: 26, display: "grid", placeItems: "center", background: "var(--fundo-campo)", borderRadius: 8 }}>{sigla}</span>
                    {nome}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Secao>

        <Secao id="fotos" numero="003" legenda="fotos" titulo={<>Os <em>bastidores</em></>}>
          <div className="grade bastidores">
            {CONTEUDO.fotos.map(([arquivo, legenda, posicao], i, todas) => (
              // A primeira é a grande; se a última linha ficaria com um buraco, a última foto ocupa 2 colunas.
              <Foto key={arquivo} arquivo={arquivo} legenda={legenda} altura="100%" posicao={posicao}
                classe={i === 0 ? "grande" : i === todas.length - 1 && (todas.length - 3) % 3 === 2 ? "larga" : undefined} />
            ))}
          </div>
        </Secao>

        <Secao id="equipe" numero="004" legenda="desenvolvedores" titulo={<>Quem <em>construiu</em></>}>
          <div className="grade g-2">
            <Pessoa destaque foto={autor.foto} iniciais={autor.iniciais} nome={autor.nome} papel="Autor" subtitulo={autor.curso}
              bio={autor.bio} links={[["Site pessoal", autor.site], ["LinkedIn", autor.linkedin], ["GitHub", autor.github]]} />
            <Pessoa foto={orientador.foto} iniciais={orientador.iniciais} nome={orientador.nome} papel={orientador.papel}
              bio={orientador.bio} links={orientador.links} />
          </div>
          <h3 style={{ fontSize: 22, fontWeight: 500, letterSpacing: "-0.02em", margin: "40px 0 16px" }}>Professores da <em className="enfase">disciplina</em></h3>
          <div className="grade g-2">
            {professores.map((p) => (
              <div key={p.nome} className="cartao" style={{ display: "grid", gap: 16, padding: 24, alignContent: "start" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <span style={{ flex: "none", width: 64, height: 64, borderRadius: "50%", overflow: "hidden" }}>
                    <Imagem arquivo={p.foto} descricao={p.nome} raio="50%" reserva={
                      <span style={{ width: "100%", height: "100%", borderRadius: "50%", background: "var(--fundo-campo)", color: "var(--destaque)", display: "grid", placeItems: "center", fontWeight: 600 }}>{p.iniciais}</span>} />
                  </span>
                  <strong style={{ flex: 1, minWidth: 0, fontWeight: 500, fontSize: 19, letterSpacing: "-0.02em" }}>{p.nome}</strong>
                  <Linkado href={p.linkedin}>LinkedIn ↗</Linkado>
                </div>
                <p className="suave bio" style={{ margin: 0, fontSize: 15 }}>{p.bio}</p>
              </div>
            ))}
          </div>
        </Secao>

        <Secao id="materiais" numero="005" legenda="downloads" titulo={<>Materiais do <em>projeto</em></>}>
          <div className="grade g-2">
            {CONTEUDO.materiais.arquivos.map((m) => <Material key={m.arquivo} {...m} />)}
          </div>
          <a href={CONTEUDO.materiais.repositorio} target="_blank" rel="noreferrer" className="cartao repositorio"
            style={{ marginTop: 20, display: "flex", alignItems: "center", gap: 20, textDecoration: "none", flexWrap: "wrap" }}>
            <svg width="40" height="40" viewBox="0 0 16 16" aria-hidden="true" fill="var(--texto)" style={{ flex: "none" }}>
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            <span style={{ flex: "1 1 260px", minWidth: 0 }}>
              <strong style={{ fontWeight: 500, fontSize: 20, letterSpacing: "-0.02em" }}>Repositório do projeto</strong><br />
              <span className="suave mono" style={{ fontSize: 13, overflowWrap: "anywhere" }}>{CONTEUDO.materiais.repositorio.replace("https://", "")}</span>
            </span>
            <span className="botao primario pequeno">Ver no GitHub ↗</span>
          </a>
          <p className="suave" style={{ fontSize: 14, marginTop: 16 }}>
            Código da API, firmware MicroPython dos ESP32, migrações do banco, testes e este site.
          </p>
        </Secao>

        <Secao id="instituicao" numero="006" legenda="onde nasceu" titulo={<>A <em>instituição</em></>}>
          <div className="grade g-2">
            <Foto arquivo={instituicao.foto} legenda="Campus Santo Amaro" altura={260} />
            <div className="cartao">
              <h3 className="titulo t-3" style={{ marginBottom: 10 }}>{instituicao.nome}</h3>
              <p className="mono suave" style={{ fontSize: 13 }}>{instituicao.curso}</p>
              <p>{instituicao.texto}</p>
              <Linkado href={instituicao.site} classe="botao claro pequeno">Conhecer o SENAC ↗</Linkado>
            </div>
          </div>
        </Secao>
      </main>
      <Rodape />
    </>
  );
}
