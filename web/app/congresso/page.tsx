import type { Metadata } from "next";
import Hemiciclo from "../components/Hemiciclo";
import { verCongresso } from "../lib/api";

export const revalidate = 900;

export const metadata: Metadata = {
  title: "Congresso",
  description: "Composição da Câmara dos Deputados por partido, com as 513 cadeiras.",
};

export default async function PaginaCongresso() {
  const dados = await verCongresso();
  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Visão institucional
      </p>
      <h1>O Congresso como lugar, não como lista</h1>
      <p className="muted" style={{ maxWidth: "58ch", margin: "12px 0 26px" }}>
        Entre pela casa, escolha a bancada e só então chegue na pessoa — em vez
        de encarar 513 nomes em ordem alfabética.
      </p>
      <Hemiciclo dados={dados} />
      <p className="muted" style={{ fontSize: 13, marginTop: 14, maxWidth: "62ch" }}>
        Esta é a legislatura em exercício. A eleição de 2026 já definiu outra
        composição, que assume em fevereiro de 2027 — são dois conjuntos
        diferentes de pessoas.
      </p>
    </div>
  );
}
