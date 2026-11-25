import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, postar, type Usuario } from "../api";
import { Logo } from "../componentes/comuns";

export default function Login() {
  const navegar = useNavigate();
  const [usuario, setUsuario] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Já logado: vai direto ao painel.
  useEffect(() => {
    api<Usuario>("/auth/eu").then(() => navegar("/painel", { replace: true })).catch(() => {});
  }, [navegar]);

  const entrar = async (e: FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      await postar<Usuario>("/auth/login", { usuario: usuario.trim(), senha });
      navegar("/painel", { replace: true });
    } catch (err) {
      setErro((err as Error).message);
      setSenha("");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 16 }}>
      <div style={{ width: "100%", maxWidth: 440 }}>
        <div style={{ marginBottom: 40 }}><Logo /></div>
        <p className="rotulo">Acesso restrito</p>
        <h1 className="titulo t-2" style={{ fontSize: "clamp(40px, 6vw, 60px)", marginBottom: 32 }}>Painel de <em>controle</em></h1>
        <form onSubmit={entrar} className="cartao" style={{ display: "grid", gap: 20 }}>
          <label className="campo"><span>Usuário</span>
            <input className="entrada" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" autoFocus required />
          </label>
          <label className="campo"><span>Senha</span>
            <input className="entrada" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" required />
          </label>
          {erro && <div className="aviso" role="alert">{erro}</div>}
          <button className="botao primario" disabled={enviando || !usuario || !senha}>{enviando ? "Entrando…" : "Entrar"}</button>
        </form>
        <p className="suave" style={{ fontSize: 14, marginTop: 24 }}>
          Sem usuário? Crie um com <span className="mono">scripts/criar_usuario.py</span>. · <Link to="/">Voltar ao site</Link>
        </p>
      </div>
    </main>
  );
}
