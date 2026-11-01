-- Fase 6: o Congresso como instituicao - quem o preside e como ele e composto.
--
-- Até aqui a plataforma sabia quem sao os 513 deputados, mas nao sabia quem
-- comanda a casa. Presidente de casa legislativa decide o que entra em pauta,
-- e pauta e poder: um projeto pode ter maioria e nunca ser votado. Sem esse
-- dado a plataforma explica como uma lei nasce e omite quem segura a porta.

begin;

create table if not exists mesa_diretora (
  id            bigserial primary key,
  casa          text not null check (casa in ('camara','senado','congresso')),
  cargo         text not null,
  -- 'ordem' e a hierarquia do cargo, nao a ordem alfabetica: presidente e 1,
  -- vice sao 2 e 3, secretarios vem depois. A tela mostra nessa ordem.
  ordem         integer not null default 99,
  pessoa_id     bigint references pessoa(id),
  nome          text not null,
  partido       text,
  uf            text,
  foto_url      text,
  id_na_fonte   text,
  data_inicio   date,
  data_fim      date,
  fonte_registro_id bigint references fonte_registro(id),
  unique (casa, cargo, nome, data_inicio)
);
create index if not exists ix_mesa_atual on mesa_diretora (casa, ordem)
  where data_fim is null;

-- ------------------------------------------- o que cada tipo de proposicao e
--
-- A pedido: "explicacao para qualquer um entender". O que da para explicar com
-- honestidade e o INSTRUMENTO - o que e um PL, o que e uma PEC, quantos votos
-- cada um exige, o que pode e o que nao pode. Isso e regra fixa, verificavel
-- na Constituicao e no Regimento.
--
-- O que NAO da e resumir o conteudo de cada projeto em linguagem simples sem
-- alguem ler o projeto. Resumo gerado sem leitura e invencao com cara de
-- sintese, e numa plataforma de transparencia isso e pior que nao ter resumo.
-- Entao a tela explica o rito e mostra a ementa oficial inteira, e o campo de
-- resumo editorial fica vazio ate uma pessoa escrever.

create table if not exists tipo_proposicao (
  sigla        text primary key,
  nome         text not null,
  o_que_e      text not null,
  quem_propoe  text,
  quorum       text,
  vai_a_sancao boolean not null default true,
  base_legal   text not null,
  ordem        integer not null default 99
);

insert into tipo_proposicao (sigla, nome, o_que_e, quem_propoe, quorum, vai_a_sancao, base_legal, ordem) values
('PL','Projeto de Lei Ordinária',
 'O tipo mais comum. Cria ou altera uma lei comum — a maioria das regras do dia a dia nasce assim.',
 'Qualquer deputado ou senador, o Presidente da República, o STF, os tribunais superiores, o Procurador-Geral e também os cidadãos por iniciativa popular.',
 'Maioria simples: basta mais da metade dos presentes, desde que a maioria absoluta da casa esteja na sessão.',
 true, 'CF/88, art. 47, 61 e 65', 1),
('PLP','Projeto de Lei Complementar',
 'Para os assuntos que a Constituição manda tratar por lei complementar, como regras de orçamento público, sistema tributário e organização do Judiciário.',
 'Os mesmos que podem propor lei ordinária.',
 'Maioria absoluta: 257 votos na Câmara e 41 no Senado, independentemente de quantos estejam presentes.',
 true, 'CF/88, art. 69', 2),
('PEC','Proposta de Emenda à Constituição',
 'Muda o texto da própria Constituição. É o instrumento mais pesado, e tem as regras mais duras.',
 'Um terço dos deputados ou dos senadores, o Presidente da República, ou mais da metade das assembleias legislativas.',
 'Três quintos em dois turnos nas duas casas: 308 votos na Câmara e 49 no Senado, duas vezes em cada uma.',
 false, 'CF/88, art. 60', 3),
('MPV','Medida Provisória',
 'Vale como lei desde o dia em que é publicada, antes de o Congresso votar. Só o Presidente da República pode editar, e só em caso de relevância e urgência.',
 'Exclusivamente o Presidente da República.',
 'Maioria simples nas duas casas. Caduca em 60 dias, prorrogáveis uma vez — se o Congresso não votar, perde a validade.',
 false, 'CF/88, art. 62', 4),
('PDL','Projeto de Decreto Legislativo',
 'Trata de matéria que é só do Congresso e não passa pelo Presidente: aprovar tratado internacional, sustar ato do Executivo, julgar as contas do governo.',
 'Deputados, senadores e comissões.',
 'Maioria simples.',
 false, 'CF/88, art. 49 e 62, §3º', 5),
('PDC','Projeto de Decreto Legislativo (Câmara)',
 'Mesma natureza do PDL, na numeração antiga da Câmara.',
 'Deputados e comissões.', 'Maioria simples.', false, 'CF/88, art. 49', 6),
('PLN','Projeto de Lei do Congresso Nacional',
 'Mexe no orçamento da União: créditos adicionais e alterações nas leis orçamentárias. É votado pelas duas casas em sessão conjunta.',
 'O Presidente da República, na maioria dos casos.',
 'Maioria simples em sessão conjunta do Congresso.',
 true, 'CF/88, art. 166', 7),
('PLV','Projeto de Lei de Conversão',
 'É o texto final de uma medida provisória depois que o Congresso a modificou. Quando a MP é alterada, ela vira PLV e só então segue para sanção.',
 'A comissão mista que analisa a medida provisória.',
 'Maioria simples nas duas casas.', true, 'CF/88, art. 62, §12', 8)
on conflict (sigla) do update set
  o_que_e = excluded.o_que_e, quem_propoe = excluded.quem_propoe,
  quorum = excluded.quorum, base_legal = excluded.base_legal;

-- --------------------------------------------- glossario do juridiques
--
-- Os termos que aparecem nos despachos oficiais e que travam a leitura de
-- quem nao e do ramo. Sao os que de fato apareceram nas 19.694 etapas
-- carregadas, nao uma lista decorativa.

create table if not exists glossario (
  termo      text primary key,
  explicacao text not null,
  base_legal text
);

insert into glossario (termo, explicacao, base_legal) values
('Regime de urgência',
 'Atalho no rito: dispensa prazos e etapas em comissão para o projeto ir direto ao plenário. Acelera a votação e encurta o debate público.',
 'Regimento Interno da Câmara, art. 152 a 157'),
('Substitutivo',
 'Um texto inteiro novo que o relator apresenta no lugar do projeto original. Quando aprovado, o texto do autor é descartado — por isso o relator costuma pesar mais que o autor.',
 'Regimento Interno da Câmara, art. 118, §4º'),
('Emenda de plenário',
 'Mudança pontual proposta durante a votação, já fora das comissões.',
 'Regimento Interno da Câmara, art. 120'),
('Destaque (DTQ)',
 'Pedido para votar um trecho separado do resto. Serve para derrubar um pedaço específico sem rejeitar o projeto inteiro.',
 'Regimento Interno da Câmara, art. 161'),
('Prejudicado',
 'Perdeu o objeto: outro texto sobre o mesmo assunto foi aprovado antes, ou a questão já foi resolvida. Encerra sem votação de mérito.',
 'Regimento Interno da Câmara, art. 163 e 164'),
('Parecer do relator',
 'A análise e a recomendação de quem foi designado para estudar o projeto. Não decide nada sozinho, mas orienta o voto da maioria.',
 'Regimento Interno da Câmara, art. 56'),
('Redação final',
 'A última revisão do texto aprovado, só para ajustar forma e coerência. Não pode mudar o conteúdo que foi votado.',
 'Regimento Interno da Câmara, art. 195'),
('Autógrafo',
 'A versão oficial e assinada do texto aprovado, que uma casa envia à outra ou à sanção presidencial.',
 'Regimento Interno da Câmara, art. 200'),
('Sanção tácita',
 'Se o Presidente não sancionar nem vetar em 15 dias úteis, o projeto vira lei do mesmo jeito.',
 'CF/88, art. 66, §3º'),
('Veto parcial',
 'O Presidente corta trechos do texto aprovado e sanciona o resto. O Congresso pode derrubar o veto por maioria absoluta das duas casas.',
 'CF/88, art. 66, §§1º e 4º'),
('Apensação',
 'Juntar projetos sobre o mesmo assunto para tramitarem juntos. O principal puxa os demais, que seguem o destino dele.',
 'Regimento Interno da Câmara, art. 143'),
('Arquivamento de fim de legislatura',
 'Projeto não votado em quatro anos é arquivado em bloco no fim da legislatura. Pode ser desarquivado no início da seguinte, a pedido do autor.',
 'Regimento Interno da Câmara, art. 105'),
('Votação simbólica',
 'O presidente da sessão pergunta quem é contra e registra o resultado sem apurar voto por voto. Não fica registro de como cada parlamentar votou — é o caso de 98% das votações.',
 'Regimento Interno da Câmara, art. 185'),
('Votação nominal',
 'Cada parlamentar registra o próprio voto no painel. É a única em que dá para saber quem votou o quê.',
 'Regimento Interno da Câmara, art. 185, §1º')
on conflict (termo) do update set explicacao = excluded.explicacao;

commit;
