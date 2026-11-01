import type { Metadata } from "next";
import Link from "next/link";
import { brl, listarDeputados, listarMunicipios, listarUfs, slug }
  from "../../lib/api";

export const revalidate = 900;

export async function generateStaticParams() {
  const ufs = await listarUfs();
  return ufs.map((u) => ({ sigla: u.uf.toLowerCase() }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ sigla: string }> }
): Promise<Metadata> {
  const { sigla } = await params;
  const uf = (await listarUfs()).find((u) => u.uf.toLowerCase() === sigla);
  if (!uf) return { title: "Estado não encontrado" };
  return {
    title: `${uf.nome} · bancada federal`,
    description: `Os ${uf.deputados} deputados federais eleitos por ${uf.nome}, `
      + `com gastos de cota parlamentar e votos nominais.`,
  };
}

export default async function PaginaUf({ params }: { params: Promise<{ sigla: string }> }) {
  const { sigla } = await params;
  const uf = (await listarUfs()).find((u) => u.uf.toLowerCase() === sigla);
  if (!uf) return <div className="wrap" style={{ paddingBlock: 40 }}>Estado não encontrado.</div>;
  const deputados = await listarDeputados(uf.uf);
  const municipios = await listarMunicipios(uf.uf);

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <Link href="/" className="mono" style={{ fontSize: 12, textDecoration: "none" }}>
        ← mapa
      </Link>
      <h1 style={{ marginTop: 10 }}>{uf.nome}</h1>
      <p className="muted" style={{ margin: "8px 0 24px" }}>
        {uf.deputados} deputados federais · {brl(uf.gasto_cota)} em cota parlamentar em 2026
        {" · "}{uf.municipios} municípios · {uf.vereadores.toLocaleString("pt-BR")} vereadores
      </p>

      <h2 style={{ fontSize: 19, marginBottom: 10 }}>A sua cidade</h2>
      <p className="muted" style={{ fontSize: 13.5, margin: "0 0 12px", maxWidth: "62ch" }}>
        O nível municipal é o mais próximo e o mais confundido. As vinte maiores
        cidades do estado primeiro.
      </p>
      <div className="cartao rolar" style={{ marginBottom: 32 }}>
        <table>
          <thead>
            <tr><th>Município</th><th className="n">Habitantes</th>
                <th className="n">Vereadores</th><th /></tr>
          </thead>
          <tbody>
            {municipios.slice(0, 20).map((m) => (
              <tr key={m.codigo_ibge}>
                <td><Link href={`/municipio/${m.codigo_ibge}`}>{m.nome}</Link></td>
                <td className="n">{m.populacao?.toLocaleString("pt-BR") ?? "—"}</td>
                <td className="n">
                  {m.vereadores > 0 ? m.vereadores
                    : <span className="muted" title="Veja o motivo na página da cidade">
                        não publicado
                      </span>}
                </td>
                <td className="n"><Link href={`/municipio/${m.codigo_ibge}`}>ver →</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 style={{ fontSize: 19, marginBottom: 10 }}>A bancada federal</h2>

      <div className="cartao rolar">
        <table>
          <thead>
            <tr><th>Deputado</th><th>Partido</th><th /></tr>
          </thead>
          <tbody>
            {deputados.map((d) => (
              <tr key={d.id}>
                <td>
                  <Link href={`/deputado/${d.id}/${slug(d.nome_urna)}`}>{d.nome_urna}</Link>
                  <div className="muted" style={{ fontSize: 12.5 }}>{d.nome_completo}</div>
                </td>
                <td className="mono">{d.partido}</td>
                <td className="n"><Link href={`/deputado/${d.id}/${slug(d.nome_urna)}`}>ver →</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
