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
