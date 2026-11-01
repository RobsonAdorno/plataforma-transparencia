import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { verCargo, verCamaras, type Atribuicao, type CargoDetalhe } from "../../lib/api";

export const revalidate = 3600;

const CODIGOS = ["vereador", "prefeito", "deputado_estadual", "governador",
                 "deputado_federal", "senador", "presidente"];

export function generateStaticParams() {
  return CODIGOS.map((codigo) => ({ codigo }));
}

type Props = { params: Promise<{ codigo: string }> };

async function carrega(codigo: string): Promise<CargoDetalhe> {
  try {
    return await verCargo(codigo);
  } catch {
    notFound();
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { codigo } = await params;
  const c = await carrega(codigo);
  return {
    title: `O que um ${c.nome.toLowerCase()} pode e não pode fazer`,
    description: c.resumo ?? undefined,
  };
}

function Regras({ itens, tipo, titulo }:
  { itens: Atribuicao[]; tipo: "pode" | "nao"; titulo: string }) {
  return (
    <div className="cartao">
      <div className="cabeca-pode" data-tipo={tipo}>{titulo}</div>
      <ul className="lista-reg">
        {itens.map((a) => (
          <li key={a.ordem}>
            <p>
              {a.texto}
              {a.abrangencia === "LEI_LOCAL" && (
                <span className="local" title="Depende da lei local">lei local</span>
              )}
            </p>
            <span className="lei-ref">{a.base_legal}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default async function PaginaCargo({ params }: Props) {
  const { codigo } = await params;
  const c = await carrega(codigo);
  // A conferencia do art. 29 so existe para vereador: e o unico cargo cujo
  // numero de cadeiras a Constituicao fixa em tabela.
  const camaras = c.codigo === "VEREADOR" ? await verCamaras().catch(() => null) : null;
  const porEstado = new Map((camaras?.por_estado ?? []).map((e) => [e.estado, e.total]));

  return (
    <div className="wrap" style={{ paddingBlock: "28px 56px" }}>
      <Link href="/cargos" className="mono"
            style={{ fontSize: 11.5, letterSpacing: ".06em", textTransform: "uppercase",
                     textDecoration: "none" }}>
        ← Todos os cargos
      </Link>

      <div className="linha-topo" style={{ marginTop: 16 }}>
        <span className="selo">{c.esfera.toLowerCase()}</span>
        <span className="mono muted" style={{ fontSize: 11.5 }}>
          {c.poder === "EXECUTIVO" ? "Poder Executivo" : "Poder Legislativo"}
          {" · "}mandato de {c.mandato_anos} anos
          {c.em_exercicio > 0 && ` · ${c.em_exercicio.toLocaleString("pt-BR")} no Brasil`}
        </span>
      </div>

      <h1 style={{ marginTop: 10 }}>{c.nome}</h1>
      <p style={{ maxWidth: "62ch", margin: "12px 0 0", fontSize: 17 }}>{c.resumo}</p>

      {!c.revisado && (
        <p className="aviso" style={{ marginTop: 20 }}>
          <strong>Conteúdo em revisão.</strong> Os textos abaixo foram redigidos
          a partir dos artigos citados, mas ainda não passaram por revisão
          humana. Confira sempre a base legal indicada em cada linha.
        </p>
      )}

      <div className="duas" style={{ marginTop: 24 }}>
        <Regras itens={c.pode} tipo="pode" titulo="Pode fazer" />
        <Regras itens={c.nao_pode} tipo="nao" titulo="Não pode fazer" />
      </div>

      {c.limite.length > 0 && (
        <>
          <h2 style={{ marginTop: 36 }}>Os limites numéricos</h2>
          <p className="muted" style={{ fontSize: 13.5, margin: "7px 0 13px", maxWidth: "62ch" }}>
            Estes não são interpretação: são números que a Constituição fixa, e
            por isso dá para conferir contra o dado real.
          </p>
          <div className="cartao">
            <ul className="lista-reg">
              {c.limite.map((a) => (
                <li key={a.ordem}>
                  <p>{a.texto}</p>
                  <span className="lei-ref">{a.base_legal}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}

      {camaras && (
        <>
          <h2 style={{ marginTop: 36 }}>Conferindo as 5.571 câmaras</h2>
          <p className="muted" style={{ fontSize: 13.5, margin: "7px 0 14px", maxWidth: "64ch" }}>
            Cruzamos o número de vereadores eleitos em 2024 com a população do
            IBGE e o teto do art. 29, IV. É o tipo de conferência que o número
            constitucional permite fazer — e que o resultado abaixo mostra ser
            menos simples do que parece.
          </p>
          <div className="cartao" style={{ overflow: "hidden" }}>
            <ul className="lista-reg">
              {[
                ["conforme", "Dentro do teto", "var(--accent-ink)"],
                ["conforme_pela_estimativa", "Dentro do teto pela população que valia na eleição", "var(--muted)"],
                ["a_conferir", "Acima do teto por qualquer referência", "var(--risk)"],
                ["sem_vereador_publicado", "O TSE não publicou o resultado de vereador", "var(--muted)"],
                ["sem_populacao", "Sem população do IBGE", "var(--muted)"],
              ].map(([k, rotulo, cor]) => (
                porEstado.get(k) ? (
                  <li key={k} style={{ display: "flex", gap: 14, alignItems: "baseline" }}>
                    <span className="mono" style={{ fontSize: 17, color: cor,
                          minWidth: 62, textAlign: "right" }}>
                      {porEstado.get(k)!.toLocaleString("pt-BR")}
                    </span>
                    <p style={{ fontSize: 14 }}>{rotulo}</p>
                  </li>
                ) : null
              ))}
            </ul>
          </div>

          <p className="muted" style={{ fontSize: 13.5, margin: "14px 0 0", maxWidth: "64ch" }}>
            A segunda linha é a mais interessante. O número de vagas é fixado{" "}
            <strong>antes</strong> da eleição, com a população daquele momento.
            Entre a estimativa de 2021 e o Censo de 2022 muitos municípios
            encolheram — Rio Preto da Eva, no Amazonas, caiu de 34.856 para
            24.936 habitantes, o que muda o teto de 13 para 11 cadeiras sem que
            ninguém tenha feito nada de errado. Comparar só com o Censo acusaria
            essas câmaras injustamente.
          </p>

          {camaras.a_conferir.length > 0 && (
            <>
              <h3 style={{ fontFamily: "var(--fonte-titulo)", fontSize: 16, marginTop: 26 }}>
                As que não fecham por nenhuma referência
              </h3>
              <div className="cartao rolar" style={{ marginTop: 10 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Município</th><th className="n">Censo 2022</th>
                      <th className="n">Estimativa 2021</th><th className="n">Cadeiras</th>
                      <th className="n">Teto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {camaras.a_conferir.map((m) => (
                      <tr key={m.codigo_ibge}>
                        <td>{m.nome}/{m.uf}</td>
                        <td className="n">{m.populacao?.toLocaleString("pt-BR") ?? "—"}</td>
                        <td className="n">{m.populacao_referencia?.toLocaleString("pt-BR") ?? "—"}</td>
                        <td className="n">{m.cadeiras}</td>
                        <td className="n">{m.teto_aplicavel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="aviso" style={{ marginTop: 14 }}>
                <strong>Isto não é um laudo de irregularidade.</strong> A
                divergência pode estar na fonte. Em Braga, no Rio Grande do Sul,
                o próprio arquivo do TSE lista 10 vereadores eleitos — e nenhuma
                das 24 faixas do art. 29 é um número par. Casos assim vão para
                conferência manual, não para a tela como acusação.
              </p>
            </>
          )}
        </>
      )}

      <p className="procedencia">
        Base legal citada linha por linha acima.{" "}
        {camaras && "População: IBGE, Censo 2022 e estimativa de 2021. Eleitos: TSE, eleição municipal de 2024. "}
        Onde está escrito “lei local”, a regra depende da Lei Orgânica do
        município ou da Constituição do estado, que variam.
      </p>
    </div>
  );
}
