// Registro das fontes. Um lugar so, para a mesma origem nunca ser descrita de
// dois jeitos diferentes em duas telas.
//
// Cada entrada responde tres coisas que o ícone ⓘ mostra: o que é aquele
// número, de onde ele veio, e um link para a pessoa conferir sozinha. A
// terceira é a que importa — transparência sem link verificável é só
// afirmação com cara de dado.
//
// Os endereços foram testados em 01/11/2026. Os do Planalto não respondem a
// verificação automática a partir deste ambiente, mas foram lidos de lá: são
// a fonte oficial consolidada da legislação federal.

export type Fonte = {
  /** O que é, em uma frase. */
  o_que: string;
  /** Quem publica. */
  orgao: string;
  /** Onde conferir. */
  url: string;
  /** Quando foi coletado ou conferido por nós. */
  quando?: string;
  /** O que esse dado NÃO diz. Omitir isto é o jeito mais comum de enganar. */
  ressalva?: string;
};

export const FONTES = {
  eleitos_municipais: {
    o_que: "Prefeitos e vereadores eleitos na eleição municipal de 2024, "
      + "conforme o resultado oficial por candidato.",
    orgao: "Tribunal Superior Eleitoral — Dados Abertos",
    url: "https://dadosabertos.tse.jus.br/dataset/candidatos-2024",
    quando: "coletado em 28/10/2026",
    ressalva: "São os eleitos, não necessariamente quem está no cargo hoje: "
      + "cassação, renúncia e posse de suplente não aparecem neste arquivo.",
  },
  eleitos_2022: {
    o_que: "Deputados federais, senadores, governadores e presidente eleitos "
      + "em 2022.",
    orgao: "Tribunal Superior Eleitoral — Dados Abertos",
    url: "https://dadosabertos.tse.jus.br/dataset/candidatos-2022",
    quando: "coletado em 28/10/2026",
    ressalva: "Em 2022 renovou-se um terço do Senado: são 27 senadores "
      + "eleitos, não os 81 em exercício.",
  },
  camara_api: {
    o_que: "Deputados em exercício, proposições, tramitação, votações e agenda "
      + "da Câmara dos Deputados.",
    orgao: "Câmara dos Deputados — Dados Abertos",
    url: "https://dadosabertos.camara.leg.br/",
    ressalva: "Só 2% das votações são nominais: nas outras o painel registra "
      + "apenas se aprovou, sem o voto de cada deputado.",
  },
  camara_ceap: {
    o_que: "Cota para o Exercício da Atividade Parlamentar: o que cada "
      + "deputado gastou e com quem, nota por nota.",
    orgao: "Câmara dos Deputados — Transparência",
    url: "https://www.camara.leg.br/transparencia/gastos-parlamentares",
    ressalva: "É só a cota. Não inclui salário, verba de gabinete nem "
      + "emenda parlamentar.",
  },
  senado_processo: {
    o_que: "O trâmite de uma matéria no Senado e a norma que ela gerou.",
    orgao: "Senado Federal — Dados Abertos",
    url: "https://legis.senado.leg.br/dadosabertos/",
    ressalva: "Usamos o serviço /processo. O antigo /materia foi desativado "
      + "em 01/02/2026.",
  },
  ibge_censo: {
    o_que: "População residente por município, apurada no Censo Demográfico "
      + "de 2022.",
    orgao: "IBGE — SIDRA, tabela 4714",
    url: "https://sidra.ibge.gov.br/tabela/4714",
    ressalva: "O número de vagas na câmara foi fixado antes da eleição, com a "
      + "população daquele momento — por isso guardamos também a estimativa "
      + "de 2021.",
  },
  ibge_malhas: {
    o_que: "O desenho dos limites de estados e municípios usado neste mapa.",
    orgao: "IBGE — API de Malhas Territoriais",
    url: "https://servicodados.ibge.gov.br/api/docs",
    ressalva: "Simplificamos o contorno para o mapa carregar rápido: serve "
      + "para localizar, não para medir distância ou área.",
  },
  querido_diario: {
    o_que: "Diários oficiais municipais indexados e com busca em texto "
      + "completo.",
    orgao: "Querido Diário — Open Knowledge Brasil",
    url: "https://queridodiario.ok.org.br/",
    ressalva: "Cobre 510 dos 5.570 municípios, e é texto de gazeta — não um "
      + "registro estruturado de leis.",
  },
  cf88: {
    o_que: "Constituição da República Federativa do Brasil de 1988, texto "
      + "consolidado.",
    orgao: "Presidência da República — Casa Civil",
    url: "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
  },
  art29: {
    o_que: "O art. 29, IV fixa o número máximo de vereadores por faixa de "
      + "população, em 24 degraus — de 9 a 55 cadeiras.",
    orgao: "Constituição Federal, redação da Emenda Constitucional 58/2009",
    url: "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc58.htm",
    ressalva: "É teto, não piso: câmara com menos cadeiras que o máximo está "
      + "em ordem.",
  },
  lei_13460: {
    o_que: "Código de Defesa do Usuário de Serviços Públicos. O art. 16 dá à "
      + "ouvidoria 30 dias para a decisão final, prorrogáveis uma vez.",
    orgao: "Presidência da República — Casa Civil",
    url: "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/lei/l13460.htm",
  },
  lai: {
    o_que: "Lei de Acesso à Informação. Pedido de informação tem 20 dias de "
      + "prazo, prorrogáveis por 10, com recurso definido em lei.",
    orgao: "Presidência da República — Casa Civil",
    url: "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm",
  },
  lrf: {
    o_que: "Lei de Responsabilidade Fiscal: limites de gasto com pessoal, "
      + "endividamento e despesa em fim de mandato.",
    orgao: "Presidência da República — Casa Civil",
    url: "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp101.htm",
  },
} as const satisfies Record<string, Fonte>;

export type ChaveFonte = keyof typeof FONTES;
