import type { Metadata } from "next";
import Link from "next/link";
import { brl, listarDeputados, listarUfs, slug } from "../../lib/api";

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

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <Link href="/" className="mono" style={{ fontSize: 12, textDecoration: "none" }}>
        ← mapa
      </Link>
      <h1 style={{ marginTop: 10 }}>{uf.nome}</h1>
      <p className="muted" style={{ margin: "8px 0 24px" }}>
        {uf.deputados} deputados federais · {brl(uf.gasto_cota)} em cota parlamentar em 2026
      </p>

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
