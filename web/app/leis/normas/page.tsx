import type { Metadata } from "next";
import Abas from "../../components/Abas";
import CartaoProjeto from "../../components/CartaoProjeto";
import { verVotadas, dataBr } from "../../lib/api";

export const revalidate = 900;

export const metadata: Metadata = {
  title: "Projetos que viraram lei",
  description:
    "Projetos que atravessaram as duas casas do Congresso, foram sancionados e publicados no Diário Oficial.",
};

export default async function PaginaNormas() {
  const itens = await verVotadas(true);
  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Leis em movimento
      </p>
      <h1>Chegaram ao fim: viraram lei</h1>
      <p className="muted" style={{ maxWidth: "60ch", margin: "12px 0 0" }}>
        Estes atravessaram as sete etapas. De cada um guardamos a trilha inteira,
        com data e despacho, para que daqui a dez anos ainda se possa ver quem
        propôs, quem relatou e quanto tempo levou.
      </p>
      <Abas atual="/leis/normas" />
      <div className="cartao" style={{ marginTop: 22 }}>
        {itens.map((i) => (
          <CartaoProjeto key={i.id} id={i.id} tipo={i.tipo} numero={i.numero}
            ano={i.ano} ementa={i.ementa} marco={i.marco_atual} fase={i.fase_atual}
            extra={
              <p className="mono" style={{ fontSize: 12, marginTop: 7,
                   WebkitLineClamp: "unset" as never, color: "var(--accent-ink)" }}>
                {i.norma_tipo?.replace(/_/g, " ")} {i.norma_numero}/{i.norma_ano}
                {i.norma_data ? ` · sancionada em ${dataBr(i.norma_data)}` : ""}
              </p>
            } />
        ))}
        {itens.length === 0 && (
          <p className="muted" style={{ padding: 15, margin: 0 }}>
            Nenhuma norma carregada ainda nesta janela.
          </p>
        )}
      </div>
      <p className="procedencia">
        O número da lei vem de duas fontes independentes: do despacho de
        transformação na Câmara e do campo estruturado do Senado. Quando as duas
        divergem, vale a do Senado — campo publicado é mais confiável que
        expressão regular sobre texto livre.
      </p>
    </div>
  );
}
