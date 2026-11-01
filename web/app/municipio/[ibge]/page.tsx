import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Fonte from "../../components/Fonte";
import { verMunicipio, slug, type Cobertura, type Municipio } from "../../lib/api";

export const revalidate = 3600;

type Props = { params: Promise<{ ibge: string }> };

async function carrega(ibge: string): Promise<Municipio> {
  try {
    return await verMunicipio(ibge);
  } catch {
    notFound();
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ibge } = await params;
  const m = await carrega(ibge);
  return {
    title: `${m.nome}, ${m.uf} — quem governa e quem legisla`,
    description:
      `Prefeito e vereadores eleitos em ${m.nome} (${m.uf}), com o limite de cadeiras `
      + `que a Constituição fixa para a população da cidade.`,
  };
}

/** O bloco mais importante da pagina: o que a fonte NAO disse.
 *
 * Sem ele, "0 vereadores" seria lido como "esta cidade nao tem camara" - e em
 * Ananindeua, com 478 mil habitantes e 401 candidaturas registradas, isso
 * seria uma afirmacao falsa publicada com cara de dado oficial. */
function Aviso({ c, cargo }: { c: Cobertura | undefined; cargo: string }) {
  if (!c || c.situacao === "publicado") return null;
  const legal = c.situacao === "nao_se_aplica";
  return (
    <p className="aviso" style={{
      marginTop: 14,
      borderLeftColor: legal ? "var(--line)" : "var(--risk)",
    }}>
      <strong>
        {legal
          ? `Esta cidade não elege ${cargo}.`
          : `O resultado de ${cargo} não foi publicado.`}
      </strong>{" "}
      {c.motivo}
      {!legal && (
        <>
          {" "}Isso é uma lacuna da fonte oficial, não da plataforma — e é
          diferente de a cidade não ter câmara. Enquanto o TSE não divulgar,
          não há como dizer quem foi eleito aqui.
        </>
      )}
      <span className="lei-ref" style={{ marginTop: 7 }}>
        Fonte: {c.fonte} · conferido na eleição de {c.ano_eleicao}
      </span>
    </p>
  );
}

export default async function PaginaMunicipio({ params }: Props) {
  const { ibge } = await params;
  const m = await carrega(ibge);
  const cv = m.cobertura["VEREADOR"];
  const cp = m.cobertura["PREFEITO"];

  // O teto aplicavel e o maior entre as referencias: o numero de cadeiras foi
  // fixado antes da eleicao, com a populacao daquele momento.
  const teto = Math.max(m.faixa_censo?.max_vereadores ?? 0,
                        m.faixa_referencia?.max_vereadores ?? 0);
  const cadeiras = m.vereadores.length;
  const porPartido = new Map<string, number>();
  for (const v of m.vereadores) {
    porPartido.set(v.partido ?? "sem partido",
                   (porPartido.get(v.partido ?? "sem partido") ?? 0) + 1);
  }

  return (
    <div className="wrap" style={{ paddingBlock: "28px 56px" }}>
      <Link href={`/uf/${m.uf.toLowerCase()}`} className="mono"
            style={{ fontSize: 11.5, letterSpacing: ".06em", textTransform: "uppercase",
                     textDecoration: "none" }}>
        ← {m.estado ?? m.uf}
      </Link>

      <div className="linha-topo" style={{ marginTop: 16 }}>
        <span className="selo">{m.uf}</span>
        <span className="mono muted" style={{ fontSize: 11.5 }}>
          IBGE {m.codigo_ibge}
          {m.populacao && ` · ${m.populacao.toLocaleString("pt-BR")} habitantes `
            + `(Censo ${m.populacao_ano})`}
        </span>
        {m.populacao && <Fonte chave="ibge_censo" rotulo="população" />}
      </div>
      <h1 style={{ marginTop: 10 }}>{m.nome}</h1>

      {/* ------------------------------------------------------ o prefeito */}
      <h2 style={{ marginTop: 30 }}>
        Quem administra<Fonte chave="eleitos_municipais" rotulo="prefeito eleito" />
      </h2>
      {m.prefeito ? (
        <div className="cartao" style={{ padding: 16, marginTop: 10 }}>
          <p className="mono muted" style={{ fontSize: 10.5, letterSpacing: ".07em",
               textTransform: "uppercase", margin: 0 }}>Prefeito</p>
          <p style={{ fontSize: 19, margin: "5px 0 0",
                      fontFamily: "var(--fonte-titulo)", fontWeight: 700 }}>
            {m.prefeito.nome_urna}
            {m.prefeito.partido && <span className="local">{m.prefeito.partido}</span>}
          </p>
          <p className="muted" style={{ fontSize: 13.5, margin: "4px 0 0" }}>
            {m.prefeito.nome_completo}
          </p>
          <p className="muted" style={{ fontSize: 13.5, margin: "12px 0 0", maxWidth: "58ch" }}>
            É quem executa: contrata, paga e entrega. Asfalto, iluminação, coleta,
            creche e atenção básica de saúde passam por aqui.{" "}
            <Link href="/cargo/prefeito">O que um prefeito pode e não pode fazer →</Link>
          </p>
        </div>
      ) : <Aviso c={cp} cargo="prefeito" />}

      {/* ----------------------------------------------------- a câmara */}
      <h2 style={{ marginTop: 34 }}>
        Quem legisla e fiscaliza
        <Fonte chave="eleitos_municipais" rotulo="vereadores eleitos" />
      </h2>

      {cadeiras > 0 ? (
        <>
          <dl className="cartao" style={{ margin: "10px 0 0", padding: "4px 0",
               display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))" }}>
            {[
              ["Vereadores", String(cadeiras)],
              ["Teto da Constituição", teto ? String(teto) : "—"],
              ["Partidos", String(porPartido.size)],
            ].map(([k, v]) => (
              <div key={k} style={{ padding: "11px 15px" }}>
                <dt className="mono muted" style={{ fontSize: 10.5, letterSpacing: ".07em",
                     textTransform: "uppercase" }}>{k}</dt>
                <dd style={{ margin: "3px 0 0", fontSize: 19,
                             fontFamily: "var(--fonte-mono)" }}>{v}</dd>
              </div>
            ))}
          </dl>

          {teto > 0 && (
            <p className="muted" style={{ fontSize: 13.5, marginTop: 11, maxWidth: "64ch" }}>
              A Constituição fixa o número máximo de cadeiras pela população da
              cidade, em 24 faixas — esta cai na faixa{" "}
              <strong>{m.faixa_censo?.letra ?? m.faixa_referencia?.letra}</strong>,
              com teto de <strong>{teto}</strong>.{" "}
              {cadeiras < teto
                ? "Ter menos que o teto está em ordem: é máximo, não mínimo."
                : cadeiras === teto
                  ? "A câmara está exatamente no teto."
                  : "A câmara aparece acima do teto — e isso vai para conferência, "
                    + "porque a divergência pode estar na fonte."}
              {" "}
              <Link href="/cargo/vereador">Art. 29, IV →</Link>
              <Fonte chave="art29" rotulo="teto de vereadores" />
            </p>
          )}

          <div className="cartao" style={{ marginTop: 18 }}>
            <div className="cabeca-pode" data-tipo="pode">
              Câmara Municipal de {m.nome} — {cadeiras} vereadores
            </div>
            <div className="legenda" style={{ borderTop: 0, borderBottom: "1px solid var(--line)" }}>
              {[...porPartido.entries()]
                .sort((a, b) => b[1] - a[1])
                .map(([p, n]) => <span key={p}>{p} {n}</span>)}
            </div>
            <ul className="lista-reg">
              {m.vereadores.map((v) => (
                <li key={v.id} style={{ display: "flex", gap: 12,
                                        justifyContent: "space-between" }}>
                  <p>
                    {v.nome_urna}
                    <span className="lei-ref">{v.nome_completo}</span>
                  </p>
                  <span className="mono muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                    {v.partido ?? "—"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <p className="muted" style={{ fontSize: 13.5, marginTop: 12, maxWidth: "64ch" }}>
            Vereador não executa obra. Ele vota as leis da cidade, aprova o
            orçamento e fiscaliza o prefeito.{" "}
            <Link href="/cargo/vereador">O que um vereador pode e não pode fazer →</Link>
          </p>
        </>
      ) : <Aviso c={cv} cargo="vereador" />}

      <p className="procedencia">
        Eleitos: TSE, eleição municipal de 2024. População: IBGE, Censo{" "}
        {m.populacao_ano ?? 2022}
        {m.populacao_referencia && `, com a estimativa de ${m.populacao_referencia_ano} `
          + `(${m.populacao_referencia.toLocaleString("pt-BR")} habitantes) usada como `
          + `referência do que valia quando as cadeiras foram fixadas`}.
        Gastos da câmara e projetos de lei municipais ainda não entram aqui: não
        existe fonte padronizada para os 5.571 municípios, e cada câmara publica
        como quer.
      </p>
    </div>
  );
}
