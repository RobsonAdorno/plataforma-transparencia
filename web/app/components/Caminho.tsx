// A barra do caminho ate virar lei. O numero de degraus NAO e fixo: sao sete
// no Congresso, onde o texto passa por duas casas, e cinco numa assembleia
// estadual ou camara municipal, que sao unicamerais. Fixar em sete faria uma
// lei estadual parecer ter duas etapas pendentes que nao existem.
//
// Desenhar o caminho inteiro, e nao so o ponto onde o projeto esta, e o que
// ensina: a pessoa ve quanto ainda falta, e por que a maioria nunca chega.
export default function Caminho(
  { fase, total = 7, morto }: { fase: number | null; total?: number; morto?: boolean },
) {
  const degraus = Array.from({ length: total }, (_, i) => i + 1);
  return (
    <div className="caminho" data-morto={morto ? "" : undefined}
         role="img" aria-label={`Etapa ${fase ?? 0} de ${total} até virar lei`}>
      {degraus.map((n) => (
        <span key={n} data-feito={fase !== null && n <= fase ? "" : undefined} />
      ))}
    </div>
  );
}
