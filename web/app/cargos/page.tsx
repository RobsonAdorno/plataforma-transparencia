import type { Metadata } from "next";
import Link from "next/link";
import { listarCargos } from "../lib/api";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "O que cada cargo público pode fazer",
  description:
    "Vereador, prefeito, deputado, governador, senador e presidente: o que a Constituição dá a cada cargo, o que ele não pode fazer e quais são os limites de gasto e de tamanho.",
};

const ESFERAS = [
  ["MUNICIPAL", "Na sua cidade",
   "É a esfera mais próxima e a mais confundida. Buraco, poste, creche, coleta de lixo e posto de saúde começam aqui."],
  ["ESTADUAL", "No seu estado",
   "Segurança pública, ensino médio e rodovias estaduais. A cobrança que mais chega no endereço errado é a de polícia."],
  ["FEDERAL", "No país",
   "Leis que valem para os 5.571 municípios, o orçamento da União e os tratados internacionais."],
] as const;

export default async function PaginaCargos() {
  const cargos = await listarCargos();
  return (
    <div className="wrap" style={{ paddingBlock: "32px 56px" }}>
      <p className="mono" style={{ fontSize: 12, letterSpacing: ".14em",
           textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px" }}>
        O limite de cada cargo
      </p>
      <h1>Cobrar da pessoa certa</h1>
      <p className="muted" style={{ maxWidth: "62ch", margin: "12px 0 0" }}>
        Boa parte da frustração com política vem de cobrar de quem não tem como
        atender. O vereador não asfalta rua, o prefeito não comanda a polícia, o
        deputado federal não tapa buraco de bairro. Cada página abaixo diz o que
        aquele cargo pode fazer, o que ele <em>não</em> pode, e com qual artigo
        da Constituição.
      </p>

      {ESFERAS.map(([esfera, titulo, chamada]) => (
        <section key={esfera} style={{ marginTop: 34 }}>
          <h2>{titulo}</h2>
          <p className="muted" style={{ fontSize: 14, margin: "6px 0 14px", maxWidth: "60ch" }}>
            {chamada}
          </p>
          <div className="grade" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))" }}>
            {cargos.filter((c) => c.esfera === esfera).map((c) => (
              <Link key={c.codigo} href={`/cargo/${c.codigo.toLowerCase()}`}
                    className="cartao" style={{ padding: 16, textDecoration: "none",
                                                color: "inherit", display: "block" }}>
                <div className="linha-topo">
                  <span className="selo">{c.poder === "EXECUTIVO" ? "Executivo" : "Legislativo"}</span>
                  <span className="mono muted" style={{ fontSize: 11 }}>
                    {c.mandato_anos} anos
                  </span>
                </div>
                <h3 style={{ fontFamily: "var(--fonte-titulo)", fontSize: 17, margin: "4px 0 0" }}>
                  {c.nome}
                </h3>
                <p className="muted" style={{ fontSize: 13.5, margin: "7px 0 0" }}>
                  {c.resumo}
                </p>
              </Link>
            ))}
          </div>
        </section>
      ))}

      <p className="procedencia">
        Base: Constituição Federal de 1988, Lei de Responsabilidade Fiscal
        (LC 101/2000) e Decreto-Lei 201/1967. Cada afirmação traz o artigo na
        página do cargo. Os limites do nível municipal dependem também da Lei
        Orgânica de cada município — são 5.571 textos diferentes, e isso vem
        sinalizado onde se aplica.
      </p>
    </div>
  );
}
