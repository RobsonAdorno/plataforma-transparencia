import type { Metadata } from "next";
import Link from "next/link";
import Abas from "../components/Abas";
import Banner from "../components/Banner";
import Congresso from "../components/Congresso";
import Fonte from "../components/Fonte";
import { verPanorama, verCongresso, verAcervo } from "../lib/api";

export const revalidate = 60;

export const metadata: Metadata = {
  title: "Leis e Congresso",
  description:
    "O que o Congresso está votando, como ele está composto e o acervo completo das leis de 2026 — em andamento, votadas, arquivadas e agendadas.",
};

const ANO = 2026;

export default async function PaginaLeis() {
  const [panorama, congresso, acervo] = await Promise.all([
    verPanorama(), verCongresso(), verAcervo({ ano: ANO, pagina: 1 }),
  ]);
  const r = acervo.resumo;

  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        Leis e Congresso
      </p>
      <h1>O que estão decidindo por você</h1>

      <div style={{ marginTop: 20 }}>
        <Banner p={panorama} />
      </div>

      <h2 style={{ marginTop: 34 }}>
        Como o Congresso está composto
        <Fonte chave="camara_api" rotulo="composição das casas" />
      </h2>
      <p className="muted" style={{ fontSize: 14, margin: "8px 0 16px", maxWidth: "62ch" }}>
        Toda lei federal precisa passar pelas duas casas. Quem preside cada uma
        decide o que entra em pauta — e projeto sem pauta não vira lei, por
        mais maioria que tenha.
      </p>
      <Congresso dados={congresso} />

      <h2 style={{ marginTop: 36 }}>As leis de {ANO}</h2>
      <div className="grade" style={{ marginTop: 12,
           gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))" }}>
        {[
          ["Viraram lei", r.virou_lei, "virou_lei", "var(--accent-ink)"],
          ["Em andamento", r.em_andamento, "em_andamento", "var(--fg)"],
          ["Encerradas sem virar lei", r.encerrada, "encerrada", "var(--risk)"],
          ["Sem tramitação carregada", r.sem_tramitacao, "sem_tramitacao", "var(--muted)"],
        ].map(([rot, n, filtro, cor]) => (
          <Link key={String(filtro)} href={`/leis/acervo?situacao=${filtro}`}
                className="cartao" style={{ padding: 15, textDecoration: "none",
                                            color: "inherit" }}>
            <p className="mono" style={{ fontSize: 26, margin: 0,
                 color: String(cor) }}>
              {Number(n).toLocaleString("pt-BR")}
            </p>
            <p className="muted" style={{ fontSize: 13, margin: "4px 0 0" }}>{rot}</p>
          </Link>
        ))}
      </div>
      <p className="muted" style={{ fontSize: 13.5, marginTop: 12, maxWidth: "64ch" }}>
        “Sem tramitação carregada” não é um estado do projeto, é um estado do
        nosso dado: conhecemos o cadastro dessas proposições mas ainda não
        baixamos o histórico delas. Contá-las como “em andamento” seria afirmar
        que andam, e não sabemos.
      </p>

      <Abas atual="/leis" />
      <p className="procedencia">
        Fonte: API de dados abertos da Câmara dos Deputados e serviço de
        processo do Senado Federal. A composição do Senado vem do próprio
        Senado — o TSE só publica os eleitos de cada pleito, e a casa mistura
        três eleições.
      </p>
    </div>
  );
}
