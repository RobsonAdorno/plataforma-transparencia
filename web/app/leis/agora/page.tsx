import type { Metadata } from "next";
import Abas from "../../components/Abas";
import Fonte from "../../components/Fonte";
import CartaoProjeto from "../../components/CartaoProjeto";
import { verAgora, dataHoraBr } from "../../lib/api";

// Sessao em andamento muda em minutos: e a unica tela do site com cache curto.
export const revalidate = 60;

export const metadata: Metadata = {
  title: "Sendo votadas agora",
  description: "Sessões em andamento no Congresso e as matérias que estão na pauta delas.",
};

export default async function PaginaAgora() {
  const linhas = await verAgora();
  const sessoes = new Map<number, typeof linhas>();
  for (const l of linhas) sessoes.set(l.evento_id, [...(sessoes.get(l.evento_id) ?? []), l]);

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Leis em movimento
      </p>
      <h1>Está acontecendo agora<Fonte chave="camara_api" rotulo="sessões em andamento" /></h1>
      <p className="muted" style={{ maxWidth: "60ch", margin: "12px 0 0" }}>
        Sessões que a Câmara marcou como em andamento, com as matérias da pauta.
      </p>
      <Abas atual="/leis/agora" />

      <p className="aviso" style={{ marginTop: 20 }}>
        <strong>O que esta tela não consegue mostrar:</strong> apenas 2% das
        votações da Câmara são nominais — nas outras 98% o painel registra só se
        aprovou, sem o voto de cada deputado. Então estar em pauta numa sessão
        aberta não garante que depois existirá um voto individual para consultar.
      </p>

      {sessoes.size === 0 ? (
        <p className="muted" style={{ marginTop: 22 }}>
          Nenhuma sessão em andamento neste momento.
        </p>
      ) : (
        [...sessoes.values()].map((lista) => {
          const s = lista[0];
          return (
            <section key={s.evento_id} style={{ marginTop: 24 }}>
              <h2 style={{ fontSize: 17 }}>{s.evento ?? s.evento_tipo ?? "Sessão"}</h2>
              <p className="mono muted" style={{ fontSize: 11.5, margin: "4px 0 10px" }}>
                aberta em {dataHoraBr(s.inicio)} · {s.situacao}
              </p>
              <div className="cartao">
                {lista.filter((l) => l.id).map((l) => (
                  <CartaoProjeto key={l.id} id={l.id} tipo={l.tipo} numero={l.numero}
                    ano={l.ano} ementa={l.ementa} marco={l.marco_atual}
                    fase={l.fase_atual} />
                ))}
                {lista.every((l) => !l.id) && (
                  <p className="muted" style={{ padding: 15, margin: 0, fontSize: 13.5 }}>
                    A sessão está aberta, mas nenhuma pauta foi publicada para ela.
                  </p>
                )}
              </div>
            </section>
          );
        })
      )}
      <p className="procedencia">
        Fonte: eventos da Câmara dos Deputados, situação “Em Andamento”.
        Esta página é relida a cada minuto.
      </p>
    </div>
  );
}
