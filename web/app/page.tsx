import MapaBrasil from "./components/MapaBrasil";
import { listarUfs } from "./lib/api";

export const revalidate = 900;

export default async function Home() {
  const ufs = await listarUfs();
  return (
    <div className="wrap" style={{ paddingBlock: "36px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Dados oficiais · Câmara e TSE
      </p>
      <h1>Quem representa você, e o que faz com o seu dinheiro</h1>
      <p className="muted" style={{ maxWidth: "58ch", margin: "12px 0 26px" }}>
        Comece pelo seu estado. Nenhuma lista longa: o país cabe em 27 alvos, e
        cada clique reduz o problema em vez de aumentá-lo.
      </p>
      <MapaBrasil ufs={ufs} />
    </div>
  );
}
