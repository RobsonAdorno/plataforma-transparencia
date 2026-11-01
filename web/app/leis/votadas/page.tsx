import type { Metadata } from "next";
import Abas from "../../components/Abas";
import Fonte from "../../components/Fonte";
import CartaoProjeto from "../../components/CartaoProjeto";
import { verVotadas, dataBr } from "../../lib/api";

export const revalidate = 900;

export const metadata: Metadata = {
  title: "Leis já votadas",
  description:
    "Projetos que já passaram por votação em plenário, com a trilha completa de cada um e o desfecho.",
};

export default async function PaginaVotadas() {
  const itens = await verVotadas(false);
  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Leis em movimento
      </p>
      <h1>O que já foi votado<Fonte chave="camara_api" rotulo="tramitação" /></h1>
      <p className="muted" style={{ maxWidth: "60ch", margin: "12px 0 0" }}>
        Projetos que já passaram por uma votação em plenário. Passar não é
        virar lei: daqui o texto ainda vai à outra casa do Congresso e à sanção
        do Presidente.
      </p>
      <Abas atual="/leis/votadas" />
      <div className="cartao" style={{ marginTop: 22 }}>
        {itens.map((i) => (
          <CartaoProjeto key={i.id} id={i.id} tipo={i.tipo} numero={i.numero}
            ano={i.ano} ementa={i.ementa} marco={i.marco_atual} fase={i.fase_atual}
            extra={
              <p className="mono" style={{ fontSize: 11.5, marginTop: 7,
                   WebkitLineClamp: "unset" as never, color: "var(--muted)" }}>
                {i.norma_numero
                  ? `virou ${i.norma_tipo?.replace(/_/g, " ").toLowerCase()} ${i.norma_numero}/${i.norma_ano}`
                  : `situação na fonte: ${i.situacao ?? "—"}`}
                {i.ultimo_passo ? ` · último passo em ${dataBr(i.ultimo_passo)}` : ""}
              </p>
            } />
        ))}
        {itens.length === 0 && (
          <p className="muted" style={{ padding: 15, margin: 0 }}>
            Nenhum projeto carregado ainda nesta janela.
          </p>
        )}
      </div>
      <p className="procedencia">
        Fonte: tramitação das proposições na Câmara dos Deputados, cruzada com o
        serviço de processo do Senado Federal.
      </p>
    </div>
  );
}
