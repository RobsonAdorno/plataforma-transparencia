import type { Metadata } from "next";
import Link from "next/link";
import Formulario from "./Formulario";
import { listarTemas, verMunicipio } from "../lib/api";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Abrir uma reclamação",
  description:
    "Descreva um problema da sua cidade. A plataforma identifica de quem é a responsabilidade, conta o prazo legal de resposta e mostra o que fazer se não responderem.",
};

type Props = { searchParams: Promise<{ ente?: string }> };

export default async function PaginaReclamar({ searchParams }: Props) {
  const { ente } = await searchParams;
  const temas = await listarTemas();
  let cidade = null;
  if (ente && /^\d{1,7}$/.test(ente)) {
    try {
      const m = await verMunicipio(ente);
      cidade = { codigo_ibge: m.codigo_ibge, nome: m.nome, uf: m.uf };
    } catch { cidade = null; }
  }

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Reclamações
      </p>
      <h1>Cobrar da pessoa certa</h1>
      <p className="muted" style={{ maxWidth: "62ch", margin: "12px 0 0" }}>
        Você descreve o problema; a plataforma descobre de quem é. A reclamação
        fica pública, com o prazo legal de resposta contado — 30 dias, pela Lei
        13.460/2017 — e se o prazo vencer sem resposta, isso também fica
        registrado aqui, junto com o que fazer em seguida.
      </p>
      <p className="muted" style={{ fontSize: 13.5, margin: "10px 0 0", maxWidth: "62ch" }}>
        <Link href="/reclamacoes">Ver as reclamações já abertas →</Link>
      </p>
      <Formulario temas={temas} cidade={cidade} />
    </div>
  );
}
