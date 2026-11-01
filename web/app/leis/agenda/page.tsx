import type { Metadata } from "next";
import Abas from "../../components/Abas";
import Fonte from "../../components/Fonte";
import CartaoProjeto from "../../components/CartaoProjeto";
import { verAgenda, dataHoraBr } from "../../lib/api";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "Leis que vão ser votadas",
  description:
    "O que está marcado para ser votado no Congresso nos próximos dias, com todas as etapas que faltam para cada projeto virar lei.",
};

export default async function PaginaAgenda() {
  const itens = await verAgenda(21);
  const porDia = new Map<string, typeof itens>();
  for (const i of itens) {
    const dia = i.inicio.slice(0, 10);
    porDia.set(dia, [...(porDia.get(dia) ?? []), i]);
  }

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Leis em movimento
      </p>
      <h1>O que vai ser votado<Fonte chave="camara_api" rotulo="pauta e agenda" /></h1>
      <p className="muted" style={{ maxWidth: "60ch", margin: "12px 0 0" }}>
        Cada projeto aqui está marcado para ser apreciado em uma sessão já
        convocada. Abrindo um deles você vê as sete etapas que um texto precisa
        atravessar para virar lei — e em qual delas ele está parado.
      </p>
      <Abas atual="/leis/agenda" />

      {itens.length === 0 ? (
        <p className="aviso" style={{ marginTop: 22 }}>
          Nada marcado para os próximos 21 dias. Em ano eleitoral e durante o
          recesso a agenda fica vazia por semanas — isso é o calendário do
          Congresso, não falta de dado.
        </p>
      ) : (
        [...porDia.entries()].map(([dia, lista]) => (
          <section key={dia} style={{ marginTop: 26 }}>
            <h2 style={{ fontSize: 17, marginBottom: 10 }}>
              {new Date(dia + "T12:00:00").toLocaleDateString("pt-BR",
                { weekday: "long", day: "2-digit", month: "long" })}
            </h2>
            <div className="cartao">
              {lista.map((i) => (
                <CartaoProjeto key={`${i.id}-${i.inicio}`} id={i.id} tipo={i.tipo}
                  numero={i.numero} ano={i.ano} ementa={i.ementa}
                  marco={i.marco_atual} fase={i.fase_atual}
                  extra={
                    <p className="mono" style={{ fontSize: 11.5, marginTop: 7,
                         WebkitLineClamp: "unset" as never, color: "var(--muted)" }}>
                      {dataHoraBr(i.inicio)} · {i.evento_tipo ?? "sessão"}
                      {i.regime ? ` · ${i.regime}` : ""}
                      {i.relator ? ` · relator: ${i.relator}` : ""}
                    </p>
                  } />
              ))}
            </div>
          </section>
        ))
      )}

      <p className="procedencia">
        Fonte: agenda e pauta da Câmara dos Deputados (API de dados abertos).
        Pauta publicada muda até a véspera, e matéria em pauta não quer dizer
        matéria votada — ela pode ser retirada na própria sessão.
      </p>
    </div>
  );
}
