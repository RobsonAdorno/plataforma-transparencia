import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ROTULO } from "../../../components/CartaoProjeto";
import { verProjeto, dataBr, dataHoraBr, slug, type Bloco, type Projeto }
  from "../../../lib/api";

export const revalidate = 900;

type Props = { params: Promise<{ id: string; slug: string }> };

async function carrega(id: string): Promise<Projeto> {
  try {
    return await verProjeto(Number(id));
  } catch {
    notFound();
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const p = await carrega(id);
  const nome = `${p.tipo} ${p.numero}/${p.ano}`;
  const virou = p.norma_numero
    ? ` Virou ${p.norma_tipo?.replace(/_/g, " ").toLowerCase()} ${p.norma_numero}/${p.norma_ano}.`
    : "";
  return {
    title: `${nome} — ${ROTULO[p.marco_atual ?? ""] ?? "em tramitação"}`,
    description: `${(p.ementa ?? "").slice(0, 150)}${virou}`,
  };
}

const MORTOS = ["REJEITADO", "ARQUIVADO", "RETIRADO", "PREJUDICADO", "VETO_TOTAL"];

export default async function PaginaLei({ params }: Props) {
  const { id } = await params;
  const p = await carrega(id);
  const morto = MORTOS.includes(p.marco_atual ?? "");
  const nome = `${p.tipo} ${p.numero}/${p.ano}`;

  // O caminho canonico mostra as sete etapas sempre, inclusive as que faltam.
  // Uma trilha que exibe so o que ja houve esconde justamente o que ensina:
  // quanto ainda falta para um projeto virar lei.
  const alcancadas = new Set(p.trilha.map((b) => b.marco));
  const fase = p.fase_atual ?? 0;

  return (
    <div className="wrap" style={{ paddingBlock: "28px 56px" }}>
      <Link href="/leis" className="mono"
            style={{ fontSize: 11.5, letterSpacing: ".06em", textTransform: "uppercase",
                     textDecoration: "none" }}>
        ← Leis em movimento
      </Link>

      <div className="linha-topo" style={{ marginTop: 16 }}>
        <span className="selo">{nome}</span>
        <span className="mono" style={{ fontSize: 12,
              color: morto ? "var(--risk)" : "var(--accent-ink)" }}>
          {ROTULO[p.marco_atual ?? ""] ?? "em tramitação"}
        </span>
        {p.regime && <span className="local">{p.regime}</span>}
      </div>

      <h1 style={{ marginTop: 10 }}>{p.ementa ?? nome}</h1>

      {p.norma_numero && (
        <p className="cartao" style={{ padding: "13px 15px", marginTop: 16,
             borderLeftWidth: 3, borderLeftStyle: "solid", borderLeftColor: "var(--accent)" }}>
          <strong>Hoje isto é lei.</strong>{" "}
          Virou {p.norma_tipo?.replace(/_/g, " ").toLowerCase()}{" "}
          <strong>{p.norma_numero}/{p.norma_ano}</strong>
          {p.norma_data ? `, sancionada em ${dataBr(p.norma_data)}` : ""}.
        </p>
      )}

      <dl className="cartao" style={{ margin: "18px 0 0", padding: "4px 0",
           display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))" }}>
        {[
          ["Apresentado em", dataBr(p.data_apresentacao)],
          ["Casa de origem", p.casa_origem ?? "—"],
          ["Movimentações", String(p.movimentacoes_totais)],
          ["Etapa", `${fase} de 7`],
        ].map(([k, v]) => (
          <div key={k} style={{ padding: "11px 15px" }}>
            <dt className="mono muted" style={{ fontSize: 10.5, letterSpacing: ".07em",
                 textTransform: "uppercase" }}>{k}</dt>
            <dd style={{ margin: "3px 0 0", fontSize: 15 }}>{v}</dd>
          </div>
        ))}
      </dl>

      {/* ---------------------------------------------- quem é responsável */}
      <h2 style={{ marginTop: 34 }}>Quem é responsável</h2>
      <div className="duas" style={{ marginTop: 12 }}>
        <div className="cartao">
          <div className="cabeca-pode" data-tipo="pode">Assinaram o texto original</div>
          <ul className="lista-reg">
            {p.autores.map((a) => (
              <li key={a.nome}>
                <p>
                  {a.pessoa_id
                    ? <Link href={`/deputado/${a.pessoa_id}/${slug(a.nome)}`}>{a.nome}</Link>
                    : a.nome}
                  {a.proponente && <span className="local">proponente</span>}
                </p>
                <span className="lei-ref">{a.tipo ?? ""}</span>
              </li>
            ))}
            {p.autores.length === 0 && (
              <li><p className="muted">Autoria não publicada para esta proposição.</p></li>
            )}
          </ul>
        </div>
        <div className="cartao">
          <div className="cabeca-pode" data-tipo="pode">Relataram</div>
          <ul className="lista-reg">
            {p.relatores.map((r) => (
              <li key={r.nome}>
                <p>{r.nome}{r.partido && <span className="local">{r.partido}{r.uf ? `-${r.uf}` : ""}</span>}</p>
              </li>
            ))}
            {p.relatores.length === 0 && (
              <li><p className="muted">Nenhum relator designado até agora.</p></li>
            )}
          </ul>
        </div>
      </div>
      {p.relatores.length > 0 && p.autores.length > 0 && (
        <p className="muted" style={{ fontSize: 13.5, marginTop: 11, maxWidth: "64ch" }}>
          Vale olhar os dois lados. Quem assina não é necessariamente quem
          escreve o texto que vai a voto: o relator pode substituir a proposta
          inteira por outra redação, e com frequência é o que acontece.
        </p>
      )}

      {/* ------------------------------------------------------- a trilha */}
      <h2 style={{ marginTop: 36 }}>O caminho para virar lei</h2>
      <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 20px", maxWidth: "64ch" }}>
        São sete etapas. As marcadas em cor já aconteceram; as de contorno
        tracejado ainda não. Cada bloco pode abrir e mostrar os despachos
        oficiais que o compõem.
      </p>

      <ol className="trilha">
        {p.caminho.map((etapa) => {
          const blocos = p.trilha.filter((b) => b.marco === etapa.marco);
          const feito = alcancadas.has(etapa.marco);
          return (
            <li key={etapa.marco} className="etapa"
                data-feito={feito ? "" : undefined}
                data-futuro={!feito ? "" : undefined}>
              <span className="bola" aria-hidden />
              <div>
                <div className="rotulo">{etapa.rotulo}</div>
                {blocos.length > 0 && (
                  <div className="quando">
                    {blocos.map((b) => periodo(b)).join(" · ")}
                  </div>
                )}
                {!feito && <div className="quando">ainda não aconteceu</div>}
                <p className="porque">{etapa.explicacao}</p>
                {blocos.map((b, i) => (
                  <details key={i}>
                    <summary>
                      {b.total === 1 ? "ver o despacho oficial"
                        : `ver as ${b.total} movimentações`}
                    </summary>
                    <ol>
                      {b.itens.map((m, j) => (
                        <li key={j}>
                          <span className="mono">{dataHoraBr(m.data_hora)}</span>
                          {m.orgao ? ` · ${m.orgao}` : ""}
                          {m.fonte === "senado" && <span className="local">Senado</span>}
                          <br />
                          <strong>{m.descricao}</strong>
                          {m.despacho && <> — {m.despacho}</>}
                          {m.url && <> <a href={m.url} target="_blank"
                                          rel="noopener noreferrer">íntegra</a></>}
                        </li>
                      ))}
                    </ol>
                  </details>
                ))}
              </div>
            </li>
          );
        })}
      </ol>

      {/* desfecho fora do caminho: morreu antes de chegar ao fim */}
      {p.trilha.filter((b) => MORTOS.includes(b.marco) || b.marco === "DESARQUIVADO"
                              || b.marco === "URGENCIA").length > 0 && (
        <>
          <h2 style={{ marginTop: 30, fontSize: 19 }}>Fora do caminho principal</h2>
          <div className="cartao" style={{ marginTop: 10 }}>
            <ul className="lista-reg">
              {p.trilha
                .filter((b) => MORTOS.includes(b.marco) || b.marco === "DESARQUIVADO"
                               || b.marco === "URGENCIA")
                .map((b, i) => (
                  <li key={i}>
                    <p><strong>{b.rotulo}</strong>{" "}
                      <span className="mono muted" style={{ fontSize: 11.5 }}>
                        {periodo(b)}
                      </span></p>
                    <span className="lei-ref">{b.explicacao}</span>
                  </li>
                ))}
            </ul>
          </div>
        </>
      )}

      <p className="procedencia">
        Fonte: tramitação da proposição na Câmara dos Deputados
        {p.trilha.some((b) => b.itens.some((i) => i.fonte === "senado"))
          && ", cruzada com o serviço de processo do Senado Federal"}.
        {" "}Guardamos todas as {p.movimentacoes_totais} movimentações; a trilha
        acima mostra as que mudam a situação do projeto e esconde os atos
        internos de processo — requerimentos, destaques, prazos.
        {p.url_integra && <> <a href={p.url_integra} target="_blank"
          rel="noopener noreferrer">Texto integral do projeto</a>.</>}
      </p>
    </div>
  );
}

function periodo(b: Bloco): string {
  if (!b.inicio) return "";
  if (b.total === 1 || b.inicio.slice(0, 10) === b.fim?.slice(0, 10)) {
    return dataBr(b.inicio);
  }
  return `${dataBr(b.inicio)} a ${dataBr(b.fim)} (${b.total}×)`;
}
