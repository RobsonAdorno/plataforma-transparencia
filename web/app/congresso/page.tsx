import type { Metadata } from "next";
import Congresso from "../components/Congresso";
import Fonte from "../components/Fonte";
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
      <h1>O Congresso como lugar, não como lista<Fonte chave="camara_api" rotulo="composição" /></h1>
      <p className="muted" style={{ maxWidth: "60ch", margin: "12px 0 26px" }}>
        As duas casas, com quem preside cada uma e como estão divididas as
        cadeiras. Entre pela casa, escolha a bancada e só então chegue na
        pessoa — em vez de encarar 594 nomes em ordem alfabética.
      </p>
      <Congresso dados={dados} />
      <p className="procedencia">
        Esta é a legislatura em exercício. A eleição de 2026 já definiu outra
        composição, que assume em fevereiro de 2027 — são dois conjuntos
        diferentes de pessoas. Os 81 senadores vêm do próprio Senado, não do
        TSE: a casa mistura três eleições e inclui suplentes que assumiram, e
        só ela sabe quem está sentado hoje.
      </p>
    </div>
  );
}
