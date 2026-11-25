// Textos fixos do site (página "Sobre o projeto", rodapé, custo). Edite aqui sem mexer nas telas.
// Trechos entre [COLCHETES] são marcadores dos mockups que ainda precisam do texto final.
// Fotos: ficam em frontend/public/fotos/; `foto` é o nome do arquivo (com extensão, ou sem ela para o site
// procurar .jpg/.jpeg/.png/.webp). Depois de trocar, rode `npm run build`. Sem o arquivo, aparece o marcador [FOTO].

export const CONTEUDO = {
  autor: {
    nome: "Henry Gabriel",
    iniciais: "HG",
    curso: "Engenharia da Computação · Centro Universitário SENAC",
    bio:
      "Técnico em Análise e Desenvolvimento de Sistemas pela Etec e graduando em Engenharia da Computação pelo Centro " +
      "Universitário Senac. Cursa o tecnólogo em Inteligência Artificial na FIAP, com conclusão prevista para novembro " +
      "de 2027. Atua como Engenheiro de Dados em uma das maiores joint ventures do mercado imobiliário da América Latina.",
    foto: "foto_henry.png",
    site: "https://site-profissional-1.onrender.com/",
    linkedin: "https://www.linkedin.com/in/henry-gabriel-santos-silva-6ba776209/",
    github: "https://github.com/Henry-Gbriel",
  },
  orientador: {
    nome: "Prof. Izaias Neri",
    iniciais: "IN",
    papel: "Orientador do TCC",
    bio:
      "Professor de matemática para engenharia e ciências exatas. Licenciado em Matemática pelo IME-USP, tecnólogo em " +
      "Análise e Desenvolvimento de Sistemas pelo SENAC-SP e mestre em Educação Matemática. Mantém cursos online de " +
      "Cálculo, Estatística, Álgebra Linear e outras disciplinas na Engrena Educacional.",
    foto: "foto_izaias.jpeg",
    links: [
      ["Engrena Educacional", "https://engrenaeducacional.com.br/"],
      ["LinkedIn", "https://www.linkedin.com/in/izaias-neri-076033b9/"],
      ["YouTube", "https://www.youtube.com/@izaiasneri/videos"],
    ] as [string, string][],
  },
  professores: [
    { iniciais: "RC", foto: "foto_ricardo.jpeg", nome: "Ricardo Luiz Ciuccio", bio: "Engenheiro de Produção, com pós-graduação em Engenharia Mecânica e experiência em gestão industrial e melhoria contínua. Coordenador dos cursos de Engenharia da Computação e de Produção do Centro Universitário Senac e professor da disciplina de Projeto Final de Engenharia.", linkedin: "https://www.linkedin.com/in/ciuccio-ricardo-luiz-msc-eng/" },
    { iniciais: "MF", foto: "foto_marcelo.jpeg", nome: "Marcello Figueiredo", bio: "Profissional da área de projetos e professor da disciplina de Projeto Final de Engenharia no Centro Universitário Senac. Acompanha o planejamento e o desenvolvimento dos trabalhos de conclusão de curso, contribuindo para a aplicação dos conhecimentos de engenharia em projetos práticos.", linkedin: "https://www.linkedin.com/in/marcellofigueiredo/" },
  ],
  instituicao: {
    nome: "Centro Universitário SENAC",
    curso: "Bacharelado em Engenharia da Computação · 2022–2026",
    texto: "Este sistema foi desenvolvido como Trabalho de Conclusão de Curso no campus Santo Amaro, em São Paulo, ao fim da graduação cursada de 2022 a 2026.",
    foto: "foto_senac.png",
    site: "https://www.sp.senac.br/",
  },
  custoPlacas: "[CUSTO DAS PLACAS]",
  // Arquivos em frontend/public/downloads/. Um arquivo que ainda não existe aparece como "em breve".
  // `capa`: imagem de prévia (em frontend/public/); sem ela, o cartão mostra a sigla do formato.
  materiais: {
    arquivos: [
      { sigla: "FZZ", titulo: "Circuito no Fritzing", texto: "Protoboard, esquemático e ligações dos três ESP32 com os displays e a fonte.",
        arquivo: "Projeto-TCC.fzz", acao: "Baixar .fzz", baixar: true, capa: "fotos/circuitoSimulado.jpeg" },
      { sigla: "PDF", titulo: "Artigo do TCC", texto: "O texto completo: arquitetura, regras de limpeza, experimentos e resultados.",
        arquivo: "TCC_HenryGabriel_AUTOR.pdf", acao: "Abrir PDF", baixar: false, capa: "downloads/capas/artigo.png", pagina: true },
      { sigla: "PPTX", titulo: "Apresentação do TCC", texto: "Os 15 slides da apresentação do framework de ETL para a banca.",
        arquivo: "t.pptx", nomeDownload: "Apresentacao_TCC_HenryGabriel.pptx", acao: "Baixar .pptx", baixar: true,
        capa: "downloads/capas/apresentacao.png", pagina: true },
      { sigla: "PPT", titulo: "Banner do projeto", texto: "O banner do Projeto Final de Engenharia.",
        arquivo: "bannerFinalEngenharia.ppt", acao: "Baixar .ppt", baixar: true, capa: "downloads/capas/banner.png", pagina: true },
    ],
    repositorio: "https://github.com/Henry-Gbriel/Projeto_TCC_Arquitetura_Baixo_Custo",
  },
  componentes: [
    {
      id: "esp32", foto: "foto_esp32.png", nome: "ESP32", qtd: 3, papel: "O trabalhador",
      texto: "Microcontrolador com Wi-Fi que forma os nós do cluster. Cada placa assina um tópico MQTT, recebe os " +
        "registros do ITBI um a um, aplica as regras de limpeza campo a campo e devolve o resultado para a API.",
      specs: ["Dual-core Xtensa LX6 · até 240 MHz", "520 KB de SRAM", "Wi-Fi 2,4 GHz + Bluetooth", "Lógica em 3,3 V", "MicroPython + OLED SSD1306"],
      link: ["Datasheet do ESP32 (Espressif)", "https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf"],
    },
    {
      id: "oled", foto: "informacoesLCD.jpeg", nome: "Display OLED", qtd: 3, papel: "O painel de cada nó",
      texto: "Tela 128×64 I²C em cada placa: mostra o nó, a conexão MQTT, o lote, o registro atual e os erros.",
      specs: ["0,96\" · 128 × 64 px, monocromático", "Controlador SSD1306", "I²C · endereço 0x3C", "SDA 21 · SCL 22"],
      link: ["Datasheet do SSD1306", "https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/791/SSD1306-Datasheet-for-096-OLED-_2800_1_2900_.pdf"],
    },
    {
      id: "fonte", foto: "fonte_chaveada.png", nome: "Fonte chaveada", qtd: 1, papel: "A energia",
      texto: "Alimenta as três placas a partir da tomada, pelo conector P4 com borne.",
      specs: ["Mean Well LRS-35 · 35 W", "Entrada 85–264 V CA", "Saída [TENSÃO / CORRENTE DO MODELO]"],
      link: ["Datasheet da LRS-35 (Mean Well)", "https://meanwell.lri.com.br/docs/datasheets/lrs/lrs-35-spec.pdf"],
    },
    {
      id: "protoboard", foto: "protoboard.png", nome: "Mini protoboard", qtd: 3, papel: "As ligações",
      texto: "Distribui a alimentação e liga o display a cada ESP32 sem solda.",
      specs: ["[MODELO]"],
      link: null,
    },
  ],
  tecnologias: [
    ["Dados · leitura", [["Py", "Python 3.12"], ["Op", "openpyxl (leitura em streaming)"], ["Bs", "Requests + BeautifulSoup (coleta)"]]],
    ["Banco de dados", [["Pg", "PostgreSQL"], ["Al", "Alembic"], ["Ps", "psycopg 3"]]],
    ["Mensageria · firmware", [["Mq", "Mosquitto (MQTT)"], ["Mp", "MicroPython + umqtt"]]],
    ["API", [["Fa", "FastAPI + Uvicorn"]]],
    ["Front-end", [["Re", "React + Vite"], ["Ts", "TypeScript"], ["Rc", "Recharts"]]],
    ["Infraestrutura", [["Dc", "Docker Compose"], ["Gh", "GitHub"], ["Ub", "Ubuntu Linux"]]],
  ] as [string, [string, string][]][],
  // [arquivo, legenda, enquadramento opcional (CSS object-position)]. A primeira é a foto grande.
  fotos: [
    ["foto_projeto.jpg", "O cluster montado na placa gravada a laser", "center 30%"],
    ["foto_principal.jpeg", "O cluster na máquina de gravação a laser", "center 62%"],
    ["circuitoSimulado.jpeg", "O circuito simulado no Fritzing"],
    ["informacoesLCD.jpeg", "Nó 01 conectado ao MQTT"],
    ["impressao3D.jpeg", "Impressão 3D das caixas"],
    ["primeirofront_projeto.jpeg", "A primeira versão do painel"],
  ] as [string, string, string?][],
  faq: [
    ["De onde vêm os dados?",
      "Da base pública de ITBI da Prefeitura de São Paulo, que registra as transações de compra e venda de imóveis na cidade. As planilhas são baixadas da página oficial e guardadas sem alteração antes de qualquer processamento."],
    ["O valor mostrado é o preço de anúncio?",
      "Não. É o valor declarado pelo comprador na transação registrada para o ITBI: o preço que de fato foi pago, não o pedido no anúncio."],
    ["Por que usar ESP32?",
      "Para mostrar que dá para distribuir processamento em hardware barato. Cada placa custa pouco, consome pouca energia e, juntas, limpam os registros em paralelo, com reenvio e reatribuição automáticos quando uma delas cai."],
    ["Com que frequência os dados são atualizados?",
      "A Prefeitura publica as planilhas periodicamente. Cada nova carga passa pelo cluster e o resultado entra na consulta assim que a execução termina."],
  ] as [string, string][],
};
