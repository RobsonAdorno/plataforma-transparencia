// Toda leitura passa por aqui. Os componentes de servidor chamam a API
// diretamente: nada de CORS e o HTML ja sai pronto, que e o que a busca
// organica exige.
const BASE = process.env.API_BASE ?? "http://127.0.0.1:8000";

export const REVALIDAR = 900; // dado publico muda em horas, nao em segundos

async function buscar<T>(caminho: string, revalidate = REVALIDAR): Promise<T> {
  const r = await fetch(`${BASE}${caminho}`, { next: { revalidate } });
  if (!r.ok) throw new Error(`${caminho} respondeu ${r.status}`);
  return r.json() as Promise<T>;
}

export type Uf = {
  uf: string; nome: string; codigo_ibge: string;
  deputados: number; gasto_cota: number;
  vereadores: number; prefeitos: number; municipios: number;
};
export type Deputado = {
  id: number; nome_urna: string; nome_completo: string; foto_url: string | null;
  partido: string; uf: string; mandato_id: number;
};
export type Categoria = { categoria: string; notas: number; total: number };
export type Despesa = {
  data: string | null; fornecedor: string; cnpj_cpf: string; valor: number;
  documento_url: string | null; fonte: string; coletado_em: string;
};
export type VotoRecente = {
  data_hora: string | null; orgao: string; descricao: string; tipo_voto: string;
  prop_tipo: string | null; prop_numero: number | null; prop_ano: number | null;
};
export type Identidade = { fonte: string; id_na_fonte: string; metodo: string; confianca: number };
export type DeputadoDetalhe = Deputado & {
  data_nascimento: string | null; sexo: string | null; cor_raca: string | null;
  situacao: string; estado: string;
  identidades: Identidade[];
  gastos_por_categoria: Categoria[];
  despesas_recentes: Despesa[];
  votos_por_tipo: { tipo_voto: string; total: number }[];
  votos_recentes: VotoRecente[];
};
export type Congresso = {
  casa: string; total: number; partidos: { partido: string; cadeiras: number }[];
};

export const listarUfs = () => buscar<Uf[]>("/ufs");
export const listarDeputados = (uf?: string) =>
  buscar<Deputado[]>(`/deputados${uf ? `?uf=${uf}` : ""}`);
export const verDeputado = (id: number) => buscar<DeputadoDetalhe>(`/deputados/${id}`);
export const verCongresso = () => buscar<Congresso>("/congresso");

export const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export function slug(s: string) {
  return (s ?? "").normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// ------------------------------------------------------------------- leis

export type Marco =
  | "APRESENTACAO" | "COMISSOES" | "URGENCIA" | "PLENARIO_ORIGEM"
  | "CASA_REVISORA" | "PLENARIO_REVISORA" | "SANCAO" | "PROMULGACAO"
  | "LEI" | "VETO_TOTAL" | "REJEITADO" | "ARQUIVADO" | "DESARQUIVADO"
  | "RETIRADO" | "PREJUDICADO";

export type ProjetoBase = {
  id: number; tipo: string; numero: number; ano: number;
  ementa: string | null; marco_atual: Marco | null; fase_atual: number | null;
};
export type NaAgenda = ProjetoBase & {
  inicio: string; evento: string | null; evento_tipo: string | null;
  regime: string | null; relator: string | null; titulo: string | null;
  etapas: number;
};
export type Agora = ProjetoBase & {
  evento_id: number; evento: string | null; evento_tipo: string | null;
  inicio: string; situacao: string;
};
export type Votada = ProjetoBase & {
  situacao: string | null; ultimo_passo: string | null;
  norma_tipo: string | null; norma_numero: string | null;
  norma_ano: number | null; norma_data: string | null;
};
export type Assinante = {
  nome: string; tipo: string | null; partido: string | null; uf: string | null;
  ordem: number | null; proponente: boolean; papel: "autor" | "relator";
  pessoa_id: number | null;
};
export type Movimentacao = {
  data_hora: string | null; orgao: string | null; descricao: string | null;
  despacho: string | null; url: string | null; fonte: "camara" | "senado";
  metodo: "codigo" | "texto" | null;
};
export type Bloco = {
  marco: Marco; fase: number | null; rotulo: string; explicacao: string | null;
  inicio: string | null; fim: string | null; total: number; itens: Movimentacao[];
};
export type Projeto = ProjetoBase & {
  situacao: string | null; cod_situacao: number | null; regime: string | null;
  apreciacao: string | null; casa_origem: string | null; url_integra: string | null;
  tramitando: boolean | null; data_apresentacao: string | null;
  norma_tipo: string | null; norma_numero: string | null;
  norma_ano: number | null; norma_data: string | null;
  autores: Assinante[]; relatores: Assinante[]; trilha: Bloco[];
  movimentacoes_totais: number;
  caminho: { marco: Marco; fase: number; rotulo: string; explicacao: string | null }[];
};

export const verAgenda = (dias = 21) => buscar<NaAgenda[]>(`/leis/agenda?dias=${dias}`, 300);
export const verAgora = () => buscar<Agora[]>("/leis/agora", 60);
export const verVotadas = (virouLei = false) =>
  buscar<Votada[]>(`/leis/votadas?virou_lei=${virouLei}`);
export const verProjeto = (id: number) => buscar<Projeto>(`/leis/${id}`);

// ----------------------------------------------------------------- cargos

export type CargoResumo = {
  codigo: string; nome: string; plural: string; esfera: string;
  poder: string; mandato_anos: number; resumo: string | null;
};
export type Atribuicao = {
  natureza: "pode" | "nao_pode" | "limite"; texto: string;
  base_legal: string; abrangencia: "NACIONAL" | "LEI_LOCAL";
  ordem: number; revisado: boolean;
};
export type CargoDetalhe = CargoResumo & {
  pode: Atribuicao[]; nao_pode: Atribuicao[]; limite: Atribuicao[];
  em_exercicio: number; revisado: boolean;
};
export type Camaras = {
  por_estado: { estado: string; total: number }[];
  a_conferir: {
    nome: string; uf: string; codigo_ibge: string;
    populacao: number | null; populacao_referencia: number | null;
    cadeiras: number; teto_censo: number | null;
    teto_estimativa: number | null; teto_aplicavel: number;
  }[];
  base_legal: string;
};

export const listarCargos = () => buscar<CargoResumo[]>("/cargos");
export const verCargo = (codigo: string) => buscar<CargoDetalhe>(`/cargos/${codigo}`);
export const verCamaras = () => buscar<Camaras>("/cargos/vereador/camaras");

export const dataBr = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString("pt-BR", { timeZone: "UTC" }) : "—";
export const dataHoraBr = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("pt-BR",
    { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—";
