# Materiais para download

Arquivos oferecidos na seção "Materiais" da página "Sobre o projeto". Depois de trocar, rode `npm run build` em `frontend/`.

| Arquivo | O que é |
| --- | --- |
| `Projeto-TCC.fzz` | Circuito no Fritzing (cópia de `simulacao_estrutura/projeto/Projeto-TCC.fzz`; copie de novo se mudar o circuito) |
| `TCC_HenryGabriel_AUTOR.pdf` | Artigo do TCC |
| `t.pptx` | Apresentação do TCC (baixada como `Apresentacao_TCC_HenryGabriel.pptx`) |
| `bannerFinalEngenharia.ppt` | Banner do Projeto Final de Engenharia |

Nomes, descrições e o link do repositório ficam em `frontend/src/conteudo.ts` (campo `materiais`).

Prévias dos cartões em `capas/` (artigo.png, apresentacao.png, banner.png): primeira página de cada arquivo, geradas com
`soffice --headless --convert-to pdf` + `pdftoppm -singlefile`. Gere de novo se o arquivo mudar.
