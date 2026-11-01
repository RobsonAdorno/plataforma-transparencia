import type { Metadata } from "next";
import Link from "next/link";
import { listarReclamacoes, dataBr, ESTADO_RECLAMACAO } from "../lib/api";

export const revalidate = 120;

export const metadata: Metadata = {
  title: "Reclamações",
  description:
    "Reclamações abertas por cidadãos, com o prazo legal de resposta contado e o registro público de quem respondeu e quem ficou em silêncio.",
};

export default async function PaginaReclamacoes() {
  const itens = await listarReclamacoes();
  const semResposta = itens.filter((i) => i.estado === "sem_resposta").length;
  const respondidas = itens.filter((i) => i.estado === "respondida").length;

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Reclamações
      </p>
      <h1>O que os cidadãos cobraram, e quem respondeu</h1>
      <p className="muted" style={{ maxWidth: "62ch", margin: "12px 0 0" }}>
        Toda reclamação aqui é pública desde o primeiro dia, com prazo contado.
        As que venceram sem resposta ficam marcadas — silêncio não é dado
        faltando, é o achado.
      </p>

      <div className="acoes-painel" style={{ marginTop: 18 }}>
        <Link href="/" className="botao">Abrir uma reclamação pelo mapa</Link>
      </div>

      {itens.length > 0 && (
        <dl className="cartao" style={{ margin: "22px 0 0", padding: "4px 0",
             display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))" }}>
          {[
            ["Abertas", String(itens.length)],
            ["Respondidas", String(respondidas)],
            ["Sem resposta no prazo", String(semResposta)],
          ].map(([k, v]) => (
            <div key={k} style={{ padding: "11px 15px" }}>
              <dt className="mono muted" style={{ fontSize: 10.5, letterSpacing: ".07em",
                   textTransform: "uppercase" }}>{k}</dt>
              <dd style={{ margin: "3px 0 0", fontSize: 21,
                           fontFamily: "var(--fonte-mono)" }}>{v}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="cartao" style={{ marginTop: 20 }}>
        {itens.map((i) => {
          const [rotulo, cor] = ESTADO_RECLAMACAO[i.estado];
          return (
            <Link key={i.protocolo} href={`/reclamacao/${i.protocolo}`}
                  className="projeto">
              <div className="linha-topo">
                <span className="selo">{i.protocolo}</span>
                <span className="mono" style={{ fontSize: 11.5, color: cor }}>
                  {rotulo}
                </span>
                <span className="mono muted" style={{ fontSize: 11 }}>
                  {i.municipio}/{i.uf}
                </span>
              </div>
              <h3>{i.titulo}</h3>
              <p className="mono" style={{ fontSize: 11.5, marginTop: 6,
                   WebkitLineClamp: "unset" as never }}>
                {i.tema} · aberta em {dataBr(i.criado_em)}
                {i.destino_nome && ` · para ${i.destino_nome}`}
                {i.prazo_resposta && i.estado === "encaminhada"
                  && ` · prazo até ${dataBr(i.prorrogado_ate ?? i.prazo_resposta)}`}
              </p>
            </Link>
          );
        })}
        {itens.length === 0 && (
          <p className="muted" style={{ padding: 18, margin: 0 }}>
            Nenhuma reclamação aberta ainda. Comece pelo mapa: escolha sua
            cidade e clique em “Abrir reclamação”.
          </p>
        )}
      </div>

      <p className="procedencia">
        O prazo de 30 dias vem do art. 16 da Lei 13.460/2017, que trata a
        reclamação como “manifestação” e obriga a ouvidoria a enviar a decisão
        administrativa final. A lei permite uma prorrogação por igual período,
        com justificativa — quando isso acontece, fica registrado na página da
        reclamação, para não acusar de omisso quem usou um direito legal.
      </p>
    </div>
  );
}
