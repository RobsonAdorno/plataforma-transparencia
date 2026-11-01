import type { Metadata } from "next";
import Link from "next/link";
import Fonte from "../components/Fonte";
import { verFontes, dataBr } from "../lib/api";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "O que está coberto, e o que não está",
  description:
    "Quais leis esta plataforma consegue acompanhar em cada esfera — federal, estadual e municipal — e onde a fonte oficial não existe.",
};

const SELO = {
  testado: ["Testado", "var(--accent-ink)", "Chamei o endereço e veio dado."],
  documentado: ["Documentado", "var(--muted)",
    "A casa publica a documentação, mas eu não obtive resposta nos testes."],
  ausente: ["Não levantado", "var(--risk)", "Ainda não verificado, ou não existe."],
} as const;

export default async function PaginaCobertura() {
  const f = await verFontes();
  const mun = f.municipal;
  const total = mun.com_gazeta + mun.sem_gazeta;

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Procedência
      </p>
      <h1>O que está coberto, e o que não está</h1>
      <p className="muted" style={{ maxWidth: "62ch", margin: "12px 0 0" }}>
        Esta página existe porque a ausência de um dado pode ser lida como
        afirmação. Se a plataforma não mostra nenhuma lei do seu estado, isso
        quer dizer que ainda não coletamos — não que a assembleia não legislou.
      </p>

      <h2 style={{ marginTop: 34 }}>Federal: completo</h2>
      <p className="muted" style={{ fontSize: 14, margin: "7px 0 0", maxWidth: "62ch" }}>
        A Câmara dos Deputados e o Senado publicam API documentada, com
        tramitação por proposição. É a única esfera onde a trilha inteira, do
        protocolo ao Diário Oficial, sai de fonte oficial sem raspagem.
      </p>

      <h2 style={{ marginTop: 30 }}>Estadual: uma assembleia por vez</h2>
      <p className="muted" style={{ fontSize: 14, margin: "7px 0 14px", maxWidth: "64ch" }}>
        Não existe API única nem agregador oficial. São 27 casas, cada uma com
        o seu formato — quando tem. Abaixo, o que levantei até agora.
      </p>
      <div className="cartao rolar">
        <table>
          <thead>
            <tr><th>Casa</th><th>Fonte</th><th>Formato</th>
                <th>Tramitação</th><th>Verificação</th></tr>
          </thead>
          <tbody>
            {f.estaduais_e_federal.map((l, i) => {
              const [rot, cor] = SELO[l.verificacao];
              return (
                <tr key={`${l.nome}-${l.escopo}-${i}`}>
                  <td>
                    {l.nome}{l.uf && ` (${l.uf})`}
                    <div className="muted" style={{ fontSize: 12.5 }}>{l.observacao}</div>
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>{l.tipo}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{l.formato ?? "—"}</td>
                  <td className="mono" style={{ fontSize: 12 }}>
                    {l.tem_tramitacao ? "sim" : "não"}
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: cor }}>{rot}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ fontSize: 13, marginTop: 11, maxWidth: "64ch" }}>
        “Documentado” não é o mesmo que “funciona”. O Paraná tem a API estadual
        mais completa que encontrei — proposição com tramitação embutida e
        norma com o vínculo de volta ao projeto — e o host dela não respondeu
        nos meus testes. Tratar os dois casos como iguais faria esta tabela
        mentir sobre o que está pronto para usar.
      </p>

      <h2 style={{ marginTop: 34 }}>Municipal: o buraco de verdade<Fonte chave="querido_diario" rotulo="diários municipais" /></h2>
      <dl className="cartao" style={{ margin: "12px 0 0", padding: "4px 0",
           display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))" }}>
        {[
          ["Com diário indexado", mun.com_gazeta.toLocaleString("pt-BR")],
          ["Sem fonte alguma", mun.sem_gazeta.toLocaleString("pt-BR")],
          ["Cobertura", `${((mun.com_gazeta / total) * 100).toFixed(1)}%`],
        ].map(([k, v]) => (
          <div key={k} style={{ padding: "11px 15px" }}>
            <dt className="mono muted" style={{ fontSize: 10.5, letterSpacing: ".07em",
                 textTransform: "uppercase" }}>{k}</dt>
            <dd style={{ margin: "3px 0 0", fontSize: 21,
                         fontFamily: "var(--fonte-mono)" }}>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="muted" style={{ fontSize: 14, margin: "13px 0 0", maxWidth: "64ch" }}>
        São 5.571 câmaras municipais, sem padrão, sem API e sem CSV. O único
        caminho em escala é o diário oficial, e o Querido Diário indexa o
        diário de {mun.com_gazeta} cidades — com busca em texto completo e sem
        autenticação.
      </p>
      <p className="aviso" style={{ marginTop: 14 }}>
        <strong>E aqui cabe uma ressalva que muda o tamanho da promessa.</strong>{" "}
        Diário oficial é <em>texto</em>, não registro de leis. Uma busca por
        “lei” em Salvador devolve 4.823 edições, e a lei aparece citada dentro
        de um despacho tributário qualquer. Transformar isso em “quais leis esta
        cidade aprovou” exige extração, e extração erra. Por isso o municipal
        entra pela{" "}
        <Link href="/cargos">importação manual revisada</Link>, cidade por
        cidade, e não como cobertura nacional automática.
      </p>

      <p className="procedencia">
        Levantamento de {dataBr(f.estaduais_e_federal[0]?.verificado_em)}. A
        Transparência Internacional avaliou as 27 casas legislativas estaduais:
        só quatro ficaram em nível “bom” (DF, ES, MG e CE), nenhuma chegou a
        “ótimo”, e dados abertos está entre os pontos mais fracos. Cada linha
        desta página é refeita quando o levantamento é repetido.
      </p>
    </div>
  );
}
