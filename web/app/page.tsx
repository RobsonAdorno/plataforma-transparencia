import Link from "next/link";
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

      {/* Duas portas que o mapa nao abre: a lei em movimento e o limite do
          cargo. Sem elas a plataforma responde "quem" e deixa "o que ele pode
          fazer" e "o que estao decidindo agora" de fora - que sao justamente
          as perguntas que levam alguem a cobrar da pessoa certa. */}
      <div className="grade" style={{ marginTop: 34,
           gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))" }}>
        <Link href="/leis" className="cartao"
              style={{ padding: 18, textDecoration: "none", color: "inherit" }}>
          <span className="selo">Leis em movimento</span>
          <h2 style={{ fontSize: 19, margin: "9px 0 0" }}>
            O que vão votar, o que estão votando e o que virou lei
          </h2>
          <p className="muted" style={{ fontSize: 14, margin: "8px 0 0" }}>
            Cada projeto com as sete etapas que faltam para virar lei, quem
            assinou e quem relatou — porque o texto aprovado raramente é o
            texto proposto.
          </p>
        </Link>
        <Link href="/cargos" className="cartao"
              style={{ padding: 18, textDecoration: "none", color: "inherit" }}>
          <span className="selo">O limite de cada cargo</span>
          <h2 style={{ fontSize: 19, margin: "9px 0 0" }}>
            Cobrar da pessoa certa
          </h2>
          <p className="muted" style={{ fontSize: 14, margin: "8px 0 0" }}>
            Vereador não asfalta rua, prefeito não comanda a polícia, deputado
            federal não tapa buraco de bairro. O que cada um pode e não pode,
            com o artigo citado.
          </p>
        </Link>
      </div>
    </div>
  );
}
