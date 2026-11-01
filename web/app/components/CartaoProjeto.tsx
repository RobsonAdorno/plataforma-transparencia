import Link from "next/link";
import Caminho from "./Caminho";
import { slug, type Marco } from "../lib/api";

const MORTOS: Marco[] = ["REJEITADO", "ARQUIVADO", "RETIRADO", "PREJUDICADO", "VETO_TOTAL"];

export const ROTULO: Record<string, string> = {
  APRESENTACAO: "Apresentado", COMISSOES: "Nas comissões",
  URGENCIA: "Urgência aprovada", PLENARIO_ORIGEM: "Aprovado na casa de origem",
  CASA_REVISORA: "Na casa revisora", PLENARIO_REVISORA: "Aprovado na casa revisora",
  SANCAO: "Na sanção presidencial", PROMULGACAO: "Na promulgação",
  LEI: "Virou lei", VETO_TOTAL: "Vetado integralmente", REJEITADO: "Rejeitado",
  ARQUIVADO: "Arquivado", DESARQUIVADO: "Desarquivado",
  RETIRADO: "Retirado pelo autor", PREJUDICADO: "Prejudicado",
};

export default function CartaoProjeto({
  id, tipo, numero, ano, ementa, marco, fase, etapas = 7, extra,
}: {
  id: number; tipo: string; numero: number; ano: number;
  ementa: string | null; marco: Marco | null; fase: number | null;
  etapas?: number; extra?: React.ReactNode;
}) {
  const morto = marco ? MORTOS.includes(marco) : false;
  return (
    <Link href={`/lei/${id}/${slug(`${tipo}-${numero}-${ano}`)}`} className="projeto">
      <div className="linha-topo">
        <span className="selo">{tipo} {numero}/{ano}</span>
        {marco && (
          <span className="mono" style={{ fontSize: 11.5,
            color: morto ? "var(--risk)" : "var(--muted)" }}>
            {ROTULO[marco] ?? marco}
          </span>
        )}
      </div>
      <Caminho fase={fase} total={etapas} morto={morto} />
      <h3>{ementa?.split(/(?<=\.)\s/)[0]?.slice(0, 110) ?? "Sem ementa publicada"}</h3>
      {ementa && ementa.length > 110 && <p>{ementa}</p>}
      {extra}
    </Link>
  );
}
