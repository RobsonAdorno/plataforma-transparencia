import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { brl, verDeputado } from "../../../lib/api";

export const revalidate = 900;

type Props = { params: Promise<{ id: string; slug: string }> };

async function carregar(id: string) {
  try {
    return await verDeputado(Number(id));
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const d = await carregar(id);
  if (!d) return { title: "Deputado não encontrado" };
  const nome = d.nome_urna || d.nome_completo;
  return {
    title: `${nome} (${d.partido}-${d.uf}) — gastos e votos`,
    description: `Quanto gasta e como vota ${nome}, deputado federal por ${d.estado}. `
      + "Dados oficiais da Câmara e do TSE.",
    alternates: { canonical: `/deputado/${id}/${(await params).slug}` },
  };
}

export default async function PaginaDeputado({ params }: Props) {
  const { id } = await params;
  const d = await carregar(id);
  if (!d) notFound();

  const nome = d.nome_urna || d.nome_completo;
  const total = d.gastos_por_categoria.reduce((s, g) => s + Number(g.total), 0);
  const jsonLd = {
    "@context": "https://schema.org", "@type": "Person",
    name: d.nome_completo, jobTitle: "Deputado Federal", affiliation: d.partido,
    address: { "@type": "PostalAddress", addressRegion: d.uf, addressCountry: "BR" },
  };

  return (
    <div className="wrap" style={{ paddingBlock: "28px 56px" }}>
      <script type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Link href={`/uf/${d.uf.toLowerCase()}`} className="mono"
            style={{ fontSize: 12, textDecoration: "none" }}>← bancada de {d.estado}</Link>

      <header style={{ display: "flex", gap: 18, alignItems: "center",
                       flexWrap: "wrap", margin: "14px 0 8px" }}>
        {d.foto_url && (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src={d.foto_url} alt={nome} width={84} height={112}
               style={{ objectFit: "cover", borderRadius: 5, border: "1px solid var(--line)" }} />
        )}
        <div>
          <h1>{nome}</h1>
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 14 }}>{d.nome_completo}</p>
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 14 }}>
            Deputado federal · {d.partido} · {d.estado}{" "}
            <span className="selo">{d.situacao.replace(/_/g, " ")}</span>
          </p>
        </div>
      </header>

      <h2 style={{ marginTop: 32 }}>Cota parlamentar · {brl(total)}</h2>
      <div className="cartao rolar" style={{ marginTop: 10 }}>
        <table>
          <thead><tr><th>Categoria</th><th className="n">Notas</th><th className="n">Total</th></tr></thead>
          <tbody>
            {d.gastos_por_categoria.map((g) => (
              <tr key={g.categoria}>
                <td>{g.categoria}</td>
                <td className="n">{g.notas}</td>
                <td className="n">{brl(Number(g.total))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 style={{ marginTop: 32 }}>Notas mais recentes</h2>
      <div className="cartao rolar" style={{ marginTop: 10 }}>
        <table>
          <thead><tr><th>Data</th><th>Fornecedor</th><th className="n">Valor</th><th>Documento</th></tr></thead>
          <tbody>
            {d.despesas_recentes.map((x, i) => (
              <tr key={i}>
                <td className="mono">{x.data ? new Date(x.data).toLocaleDateString("pt-BR") : "—"}</td>
                <td>{x.fornecedor}</td>
                <td className="n">{brl(Number(x.valor))}</td>
                <td>{x.documento_url
                  ? <a href={x.documento_url} rel="nofollow noopener" target="_blank">nota</a>
                  : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 style={{ marginTop: 32 }}>Votos nominais</h2>
      {d.votos_recentes.length ? (
        <>
          <div className="cartao rolar" style={{ marginTop: 10 }}>
            <table>
              <thead><tr><th>Data</th><th>Órgão</th><th>Matéria</th><th>Voto</th></tr></thead>
              <tbody>
                {d.votos_recentes.map((v, i) => (
                  <tr key={i}>
                    <td className="mono">{v.data_hora
                      ? new Date(v.data_hora).toLocaleDateString("pt-BR") : "—"}</td>
                    <td className="mono">{v.orgao}</td>
                    <td>{v.prop_tipo
                      ? `${v.prop_tipo} ${v.prop_numero}/${v.prop_ano}`
                      : (v.descricao ?? "").slice(0, 60)}</td>
                    <td><strong>{v.tipo_voto}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
            Das 7.436 votações de 2026, só 155 foram nominais. A maior parte é
            simbólica e não registra quem votou o quê.
          </p>
        </>
      ) : (
        <p className="muted" style={{ fontStyle: "italic", marginTop: 10 }}>
          Nenhum voto nominal no período coletado. A maior parte das votações é
          simbólica e não identifica quem votou o quê.
        </p>
      )}

      <div className="procedencia">
        Dados da API da Câmara dos Deputados e da base de candidatos do TSE.
        Identificação cruzada —{" "}
        {d.identidades.map((i) => `${i.fonte}: ${i.id_na_fonte} (${i.metodo})`).join(" · ")}.
        Cada nota aponta para o documento original no portal da Câmara.
      </div>
    </div>
  );
}
