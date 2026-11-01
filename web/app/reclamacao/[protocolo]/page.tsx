import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Escalonamento } from "../../reclamar/Formulario";
import { verReclamacao, dataBr, dataHoraBr, ESTADO_RECLAMACAO, type Reclamacao }
  from "../../lib/api";

export const revalidate = 60;

type Props = { params: Promise<{ protocolo: string }> };

async function carrega(protocolo: string): Promise<Reclamacao> {
  try {
    return await verReclamacao(protocolo);
  } catch {
    notFound();
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { protocolo } = await params;
  const r = await carrega(protocolo);
  const [rotulo] = ESTADO_RECLAMACAO[r.estado];
  return {
    title: `${r.titulo} — ${rotulo}`,
    description: `Reclamação ${r.protocolo} em ${r.municipio}, ${r.uf}: ${r.descricao.slice(0, 140)}`,
  };
}

export default async function PaginaReclamacao({ params }: Props) {
  const { protocolo } = await params;
  const r = await carrega(protocolo);
  const [rotulo, cor] = ESTADO_RECLAMACAO[r.estado];
  const limite = r.prorrogado_ate ?? r.prazo_resposta;

  return (
    <div className="wrap" style={{ paddingBlock: "28px 56px" }}>
      <Link href="/reclamacoes" className="mono"
            style={{ fontSize: 11.5, letterSpacing: ".06em", textTransform: "uppercase",
                     textDecoration: "none" }}>
        ← Reclamações
      </Link>

      <div className="linha-topo" style={{ marginTop: 16 }}>
        <span className="selo">{r.protocolo}</span>
        <span className="mono" style={{ fontSize: 12, color: cor }}>{rotulo}</span>
        <Link href={`/municipio/${r.ente_codigo}`} className="mono"
              style={{ fontSize: 11.5 }}>
          {r.municipio}/{r.uf}
        </Link>
      </div>

      <h1 style={{ marginTop: 10 }}>{r.titulo}</h1>

      {/* O bloco que da sentido a tudo: o prazo. */}
      {r.estado === "sem_resposta" && (
        <p className="aviso" style={{ marginTop: 18, borderLeftColor: "var(--risk)" }}>
          <strong>
            O prazo legal venceu {r.dias_de_atraso > 0 && `há ${r.dias_de_atraso} dias `}
            e não houve resposta.
          </strong>{" "}
          A Lei 13.460/2017 obriga a ouvidoria a enviar a decisão administrativa
          final em 30 dias, prorrogáveis uma única vez
          {r.prorrogado && " — e esta prorrogação já foi usada"}. O prazo
          terminou em {dataBr(limite)}. O silêncio está registrado, e abaixo
          está o que você pode fazer agora.
        </p>
      )}
      {r.estado === "encaminhada" && limite && (
        <p className="cartao" style={{ padding: "13px 15px", marginTop: 18,
             borderLeftWidth: 3, borderLeftStyle: "solid",
             borderLeftColor: "var(--accent)" }}>
          <strong>Aguardando resposta até {dataBr(limite)}.</strong>{" "}
          São 30 dias contados do encaminhamento, pelo art. 16 da Lei
          13.460/2017.
          {r.prorrogado && " O órgão já usou a prorrogação que a lei permite."}
        </p>
      )}
      {r.estado === "recebida" && (
        <p className="aviso" style={{ marginTop: 18 }}>
          <strong>Registrada, mas ainda não encaminhada.</strong> Não temos o
          canal oficial deste órgão cadastrado, então o prazo legal ainda não
          começou a correr. Protocole você mesmo na ouvidoria usando o passo 1
          abaixo — é o ato que faz o prazo começar.
        </p>
      )}

      <dl className="cartao" style={{ margin: "18px 0 0", padding: "4px 0",
           display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))" }}>
        {[
          ["Tema", r.tema],
          ["Responsável",
           r.esfera_responsavel === "MUNICIPAL" ? "Prefeitura"
           : r.esfera_responsavel === "ESTADUAL" ? "Governo do estado"
           : r.esfera_responsavel === "FEDERAL" ? "Governo federal" : "—"],
          ["Para", r.destino_nome ?? "—"],
          ["Aberta em", dataBr(r.criado_em)],
        ].map(([k, v]) => (
          <div key={k} style={{ padding: "11px 15px" }}>
            <dt className="mono muted" style={{ fontSize: 10.5, letterSpacing: ".07em",
                 textTransform: "uppercase" }}>{k}</dt>
            <dd style={{ margin: "3px 0 0", fontSize: 14.5 }}>{v}</dd>
          </div>
        ))}
      </dl>

      <h2 style={{ marginTop: 32 }}>A reclamação</h2>
      <div className="cartao" style={{ padding: 16, marginTop: 10 }}>
        <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{r.descricao}</p>
        {r.local_referencia && (
          <p className="mono muted" style={{ fontSize: 12.5, margin: "12px 0 0" }}>
            {r.local_referencia}
          </p>
        )}
        <p className="mono muted" style={{ fontSize: 11.5, margin: "12px 0 0" }}>
          {r.autor ? `Por ${r.autor}` : "Enviada sem identificação pública"}
          {" · "}{dataHoraBr(r.criado_em)}
        </p>
      </div>

      {r.resposta && (
        <>
          <h2 style={{ marginTop: 30 }}>A resposta do órgão</h2>
          <div className="cartao" style={{ padding: 16, marginTop: 10,
               borderLeftWidth: 3, borderLeftStyle: "solid",
               borderLeftColor: "var(--accent)" }}>
            <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{r.resposta}</p>
            <p className="mono muted" style={{ fontSize: 11.5, margin: "12px 0 0" }}>
              {r.resposta_autor ?? "órgão"} · {dataHoraBr(r.respondido_em)}
            </p>
            {r.resolvido !== null && (
              <p className="mono" style={{ fontSize: 12, marginTop: 10,
                   color: r.resolvido ? "var(--accent-ink)" : "var(--risk)" }}>
                {r.resolvido
                  ? "Quem reclamou confirmou que resolveu."
                  : "Quem reclamou diz que a resposta não resolveu."}
              </p>
            )}
          </div>
          <p className="muted" style={{ fontSize: 13, marginTop: 10, maxWidth: "62ch" }}>
            A resposta está publicada no texto em que foi enviada, sem edição.
            Responder não é o mesmo que resolver — e é por isso que quem
            reclamou avalia depois.
          </p>
        </>
      )}

      <h2 style={{ marginTop: 32 }}>O que aconteceu até agora</h2>
      <ol className="trilha" style={{ marginTop: 14 }}>
        {r.linha_do_tempo.map((e, i) => (
          <li key={i} className="etapa" data-feito=""
              data-fim={e.tipo === "sem_resposta" ? "" : undefined}>
            <span className="bola" aria-hidden />
            <div>
              <div className="rotulo">{tituloEvento(e.tipo)}</div>
              <div className="quando">{dataHoraBr(e.criado_em)}
                {e.ator && e.ator !== "plataforma" && ` · ${e.ator}`}</div>
              {e.descricao && <p className="porque">{e.descricao}</p>}
            </div>
          </li>
        ))}
      </ol>

      {r.escalonamento && r.escalonamento.length > 0 && (
        <>
          <h2 style={{ marginTop: 34 }}>
            {r.estado === "respondida"
              ? "Se a resposta não resolveu"
              : "O que fazer se não responderem"}
          </h2>
          <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 0", maxWidth: "64ch" }}>
            Na ordem, do mais simples ao mais pesado. Cada passo tem base legal
            e prazo próprio, e nenhum depende de advogado. Mandar o caso direto
            ao Ministério Público por um poste queimado desperdiça o
            instrumento — por isso a ordem importa.
          </p>
          <Escalonamento passos={r.escalonamento} />
        </>
      )}

      <p className="procedencia">
        Reclamação registrada por um cidadão nesta plataforma, não por um órgão
        público. O texto é de quem enviou. O prazo de 30 dias e os passos de
        escalonamento vêm da Lei 13.460/2017, da Lei 12.527/2011 (Acesso à
        Informação) e da Constituição, com o artigo citado em cada linha.
      </p>
    </div>
  );
}

function tituloEvento(tipo: string): string {
  const mapa: Record<string, string> = {
    recebida: "Reclamação registrada",
    sem_canal: "Sem canal oficial cadastrado",
    encaminhada: "Encaminhada ao órgão",
    prorrogada: "Prazo prorrogado pelo órgão",
    respondida: "Órgão respondeu",
    sem_resposta: "Prazo vencido sem resposta",
    avaliada: "Avaliada por quem reclamou",
  };
  return mapa[tipo] ?? tipo;
}
