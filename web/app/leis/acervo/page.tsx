import type { Metadata } from "next";
import Link from "next/link";
import Abas from "../../components/Abas";
import Caminho from "../../components/Caminho";
import Fonte from "../../components/Fonte";
import { ROTULO } from "../../components/CartaoProjeto";
import {
  verAcervo, listarTiposProposicao, verGlossario, dataBr, slug,
  type NoAcervo,
} from "../../lib/api";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "Todas as leis de 2026",
  description:
    "O acervo completo das proposições de 2026: as que viraram lei, as que estão em andamento, as agendadas e as que foram arquivadas, rejeitadas ou retiradas — com o motivo e quem decidiu.",
};

const ANO = 2026;

const FILTROS = [
  ["", "Todas"],
  ["virou_lei", "Viraram lei"],
  ["em_andamento", "Em andamento"],
  ["agendada", "Agendadas"],
  ["encerrada", "Encerradas"],
  ["sem_tramitacao", "Sem histórico"],
] as const;

const MORTOS = ["REJEITADO", "ARQUIVADO", "RETIRADO", "PREJUDICADO", "VETO_TOTAL"];

type Props = {
  searchParams: Promise<{ situacao?: string; tipo?: string; busca?: string;
                          pagina?: string }>;
};

export default async function PaginaAcervo({ searchParams }: Props) {
  const sp = await searchParams;
  const pagina = Math.max(1, Number(sp.pagina ?? 1) || 1);
  const [acervo, tipos, glossario] = await Promise.all([
    verAcervo({ ano: ANO, situacao: sp.situacao, tipo: sp.tipo,
                busca: sp.busca, pagina }),
    listarTiposProposicao(),
    verGlossario(),
  ]);
  const r = acervo.resumo;
  const contagem: Record<string, number> = {
    "": r.total, virou_lei: r.virou_lei, em_andamento: r.em_andamento,
    encerrada: r.encerrada, sem_tramitacao: r.sem_tramitacao,
  };
  const qs = (extra: Record<string, string>) => {
    const q = new URLSearchParams();
    if (sp.busca) q.set("busca", sp.busca);
    if (sp.tipo) q.set("tipo", sp.tipo);
    for (const [k, v] of Object.entries(extra)) { if (v) q.set(k, v); else q.delete(k); }
    return `?${q}`;
  };
  const paginas = Math.ceil(acervo.total / acervo.limite);

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Acervo de {ANO}
      </p>
      <h1>Todas as leis de {ANO}</h1>
      <p className="muted" style={{ maxWidth: "62ch", margin: "12px 0 0" }}>
        As {r.total.toLocaleString("pt-BR")} proposições do ano, em qualquer
        estado — inclusive as que foram arquivadas, rejeitadas ou retiradas,
        que é o destino da maioria e normalmente some das telas. Para essas,
        mostramos o motivo e quem decidiu.
        <Fonte chave="camara_api" rotulo="proposições e tramitação" />
      </p>

      <Abas atual="/leis/acervo" />

      <div className="filtros">
        {FILTROS.map(([valor, rotulo]) => (
          <Link key={valor} href={qs({ situacao: valor })}
                aria-current={(sp.situacao ?? "") === valor ? "page" : undefined}>
            {rotulo}
            {contagem[valor] !== undefined && (
              <span className="n">{contagem[valor].toLocaleString("pt-BR")}</span>
            )}
          </Link>
        ))}
      </div>

      <form className="filtros" action="/leis/acervo" style={{ marginTop: 10 }}>
        {sp.situacao && <input type="hidden" name="situacao" value={sp.situacao} />}
        <input name="busca" defaultValue={sp.busca ?? ""} className="campo"
               placeholder="buscar na ementa ou pelo número" style={{ flex: 1, minWidth: 220 }} />
        <select name="tipo" defaultValue={sp.tipo ?? ""} className="campo"
                style={{ width: "auto" }}>
          <option value="">todos os tipos</option>
          {tipos.map((t) => (
            <option key={t.sigla} value={t.sigla}>{t.sigla} — {t.nome}</option>
          ))}
        </select>
        <button type="submit" className="botao" style={{ border: 0, cursor: "pointer" }}>
          Buscar
        </button>
      </form>

      <p className="muted mono" style={{ fontSize: 12, margin: "14px 0 0" }}>
        {acervo.total.toLocaleString("pt-BR")} resultado(s)
        {paginas > 1 && ` · página ${pagina} de ${paginas}`}
      </p>

      <div className="cartao" style={{ marginTop: 12 }}>
        {acervo.itens.map((i) => <Linha key={i.id} i={i} />)}
        {acervo.itens.length === 0 && (
          <p className="muted" style={{ padding: 18, margin: 0 }}>
            Nada encontrado com esses filtros.
          </p>
        )}
      </div>

      {paginas > 1 && (
        <div className="filtros" style={{ marginTop: 14 }}>
          {pagina > 1 && (
            <Link href={qs({ situacao: sp.situacao ?? "", pagina: String(pagina - 1) })}>
              ← anterior
            </Link>
          )}
          {pagina < paginas && (
            <Link href={qs({ situacao: sp.situacao ?? "", pagina: String(pagina + 1) })}>
              próxima →
            </Link>
          )}
        </div>
      )}

      {/* ---------------------------------------- explicando o instrumento */}
      <h2 style={{ marginTop: 40 }}>O que cada sigla significa</h2>
      <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 14px", maxWidth: "64ch" }}>
        A diferença entre um PL e uma PEC não é formalidade: muda quem pode
        propor, quantos votos são necessários e se o Presidente da República
        participa. É o que determina se um projeto tem chance.
      </p>
      <div className="cartao">
        <ul className="lista-reg">
          {tipos.map((t) => (
            <li key={t.sigla}>
              <p>
                <strong>{t.sigla}</strong> — {t.nome}
                {!t.vai_a_sancao && <span className="local">não vai à sanção</span>}
              </p>
              <p className="muted" style={{ fontSize: 13.5, margin: "5px 0 0" }}>
                {t.o_que_e}
              </p>
              {t.quorum && (
                <p className="muted" style={{ fontSize: 13, margin: "5px 0 0" }}>
                  <strong>Para aprovar:</strong> {t.quorum}
                </p>
              )}
              {t.quem_propoe && (
                <p className="muted" style={{ fontSize: 13, margin: "3px 0 0" }}>
                  <strong>Quem pode propor:</strong> {t.quem_propoe}
                </p>
              )}
              <span className="lei-ref">{t.base_legal}</span>
            </li>
          ))}
        </ul>
      </div>

      <h2 style={{ marginTop: 34 }}>O jargão dos despachos</h2>
      <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 14px", maxWidth: "64ch" }}>
        Os termos que aparecem nos textos oficiais e travam a leitura de quem
        não é do ramo. São os que de fato apareceram nas movimentações que
        carregamos, não uma lista decorativa.
      </p>
      <div className="cartao">
        <ul className="lista-reg">
          {glossario.map((g) => (
            <li key={g.termo}>
              <p><strong>{g.termo}</strong></p>
              <p className="muted" style={{ fontSize: 13.5, margin: "4px 0 0" }}>
                {g.explicacao}
              </p>
              {g.base_legal && <span className="lei-ref">{g.base_legal}</span>}
            </li>
          ))}
        </ul>
      </div>

      <p className="procedencia">
        <strong>Uma honestidade sobre as explicações.</strong> Explicamos o
        <em> rito</em>: o que é cada tipo de proposição, quantos votos exige, em
        que etapa o projeto está e o que significa cada termo. Não escrevemos
        resumo do <em>conteúdo</em> de cada projeto — para isso seria preciso
        alguém ler o texto, e resumo gerado sem leitura é invenção com cara de
        síntese. O que aparece de cada projeto é a ementa oficial, inteira,
        como o autor escreveu.
      </p>
    </div>
  );
}

function Linha({ i }: { i: NoAcervo }) {
  const morto = MORTOS.includes(i.marco_atual ?? "");
  const virouLei = Boolean(i.norma_numero);
  const d = i.desfecho;

  return (
    <Link href={`/lei/${i.id}/${slug(`${i.tipo}-${i.numero}-${i.ano}`)}`}
          className="projeto">
      <div className="linha-topo">
        <span className="selo">{i.tipo} {i.numero}/{i.ano}</span>
        {virouLei ? (
          <span className="mono" style={{ fontSize: 11.5, color: "var(--accent-ink)" }}>
            virou {i.norma_tipo?.replace(/_/g, " ").toLowerCase()} {i.norma_numero}/{i.norma_ano}
          </span>
        ) : i.marco_atual ? (
          <span className="mono" style={{ fontSize: 11.5,
                color: morto ? "var(--risk)" : "var(--muted)" }}>
            {ROTULO[i.marco_atual] ?? i.marco_atual}
          </span>
        ) : (
          <span className="mono muted" style={{ fontSize: 11.5 }}>
            histórico não carregado
          </span>
        )}
        {i.agendada && (
          <span className="mono" style={{ fontSize: 11, color: "var(--accent-ink)" }}>
            ● na pauta
          </span>
        )}
      </div>

      {i.movimentacoes > 0 && <Caminho fase={i.fase_atual} morto={morto} />}

      <h3>{i.ementa?.split(/(?<=\.)\s/)[0]?.slice(0, 120) ?? "Sem ementa publicada"}</h3>
      {i.ementa && i.ementa.length > 120 && <p>{i.ementa}</p>}

      <p className="mono" style={{ fontSize: 11.5, marginTop: 7,
           WebkitLineClamp: "unset" as never, color: "var(--muted)" }}>
        {i.autor && `autor: ${i.autor}`}
        {i.relator && ` · relator: ${i.relator}`}
        {i.data_apresentacao && ` · apresentado em ${dataBr(i.data_apresentacao)}`}
        {i.movimentacoes > 0 && ` · ${i.movimentacoes} movimentações`}
      </p>

      {/* O pedido era saber o motivo e quem decidiu. Está aqui, no texto
          oficial — sem parafrasear, porque despacho parafraseado vira outra
          coisa. */}
      {d && !virouLei && (
        <div className="desfecho">
          <strong>{ROTULO[d.marco ?? ""] ?? d.marco}</strong>
          {d.orgao && ` · ${d.orgao}`}
          {d.quando && ` · ${dataBr(d.quando)}`}
          {d.despacho && <div style={{ marginTop: 4 }}>{d.despacho}</div>}
        </div>
      )}
    </Link>
  );
}
