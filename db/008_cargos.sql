-- Fase 3b: o limite de cada cargo publico.
--
-- Este e o objetivo central da plataforma e a unica parte que nao tem API:
-- e texto, escrito por gente, com o artigo citado do lado. Por isso toda linha
-- nasce com revisado=false e uma base_legal obrigatoria.
--
-- Uma honestidade que o schema precisa carregar: o limite do vereador nao esta
-- so na Constituicao. O art. 29 manda cada municipio se reger pela sua propria
-- Lei Organica, e sao 5.571 textos diferentes. Entao a coluna `abrangencia`
-- separa o que vale para todo o Brasil do que depende da lei local - prometer
-- o limite exato do vereador de uma cidade sem ler a Lei Organica dela seria
-- inventar com cara de fonte oficial.

begin;

create table if not exists atribuicao_cargo (
  id          bigserial primary key,
  cargo       text not null
                   check (cargo in ('PRESIDENTE','GOVERNADOR','PREFEITO','SENADOR',
                                    'DEPUTADO_FEDERAL','DEPUTADO_ESTADUAL','VEREADOR')),
  -- 'pode' e o que o cargo faz. 'nao_pode' e o que as pessoas acham que ele
  -- faz e nao faz - e e a parte que mais ensina, porque e onde mora a
  -- cobranca endereçada a quem nao tem como atender.
  natureza    text not null check (natureza in ('pode','nao_pode','limite')),
  texto       text not null,
  base_legal  text not null,
  abrangencia text not null default 'NACIONAL'
                   check (abrangencia in ('NACIONAL','LEI_LOCAL')),
  ordem       integer not null default 0,
  revisado    boolean not null default false,
  revisado_por text,
  revisado_em  timestamptz,
  fonte_url   text,
  fonte_registro_id bigint references fonte_registro(id),
  unique (cargo, natureza, ordem)
);
create index if not exists ix_atribuicao_cargo on atribuicao_cargo (cargo, natureza, ordem);

-- Resumo de uma frase por cargo, para a tela nao abrir com uma lista.
create table if not exists cargo (
  codigo     text primary key
                  check (codigo in ('PRESIDENTE','GOVERNADOR','PREFEITO','SENADOR',
                                    'DEPUTADO_FEDERAL','DEPUTADO_ESTADUAL','VEREADOR')),
  nome       text not null,
  plural     text not null,
  esfera     text not null check (esfera in ('MUNICIPAL','ESTADUAL','FEDERAL')),
  poder      text not null check (poder in ('EXECUTIVO','LEGISLATIVO')),
  mandato_anos integer not null default 4,
  resumo     text,
  ordem      integer not null default 0
);

insert into cargo (codigo, nome, plural, esfera, poder, mandato_anos, ordem, resumo) values
 ('VEREADOR','Vereador','Vereadores','MUNICIPAL','LEGISLATIVO',4,1,
  'Faz as leis da cidade e fiscaliza o prefeito. Não executa obra nem presta serviço: quando um vereador "consegue" um asfalto, ele pediu ao Executivo — a decisão e o dinheiro são do prefeito.'),
 ('PREFEITO','Prefeito','Prefeitos','MUNICIPAL','EXECUTIVO',4,2,
  'Administra a cidade: executa o orçamento aprovado pela Câmara, cuida do que é de interesse local e responde pelos serviços do dia a dia.'),
 ('DEPUTADO_ESTADUAL','Deputado estadual','Deputados estaduais','ESTADUAL','LEGISLATIVO',4,3,
  'Faz as leis do estado e fiscaliza o governador. Legisla sobre o que não é exclusivo da União nem de interesse puramente local.'),
 ('GOVERNADOR','Governador','Governadores','ESTADUAL','EXECUTIVO',4,4,
  'Administra o estado. Responde pela segurança pública, pelas rodovias estaduais e pelo ensino médio — as três cobranças que mais chegam ao endereço errado.'),
 ('DEPUTADO_FEDERAL','Deputado federal','Deputados federais','FEDERAL','LEGISLATIVO',4,5,
  'Representa a população do seu estado na Câmara. Faz leis nacionais, aprova o orçamento da União e fiscaliza o governo federal.'),
 ('SENADOR','Senador','Senadores','FEDERAL','LEGISLATIVO',8,6,
  'Representa o estado como unidade da Federação, com mandato de oito anos. Além de legislar, aprova indicações para tribunais, bancos e embaixadas.'),
 ('PRESIDENTE','Presidente da República','Presidentes','FEDERAL','EXECUTIVO',4,7,
  'Chefe do Executivo federal e chefe de Estado. Sanciona ou veta as leis do Congresso, comanda as Forças Armadas e representa o país no exterior.')
on conflict (codigo) do update set resumo = excluded.resumo, nome = excluded.nome;

-- ------------------------------------------------ os numeros que dao auditar
--
-- O art. 29, IV fixa quantos vereadores cada camara PODE ter, por faixa de
-- populacao, em 24 degraus (redacao da EC 58/2009). Guardar isso como tabela,
-- e nao como texto, transforma conteudo educativo em fiscalizacao: com a
-- populacao do IBGE do lado, da para conferir as 5.571 camaras do pais contra
-- o limite constitucional.

create table if not exists faixa_vereador (
  letra      text primary key,
  pop_min    bigint not null,
  pop_max    bigint,                       -- nulo = sem teto (acima de 8 mi)
  max_vereadores integer not null
);

insert into faixa_vereador (letra, pop_min, pop_max, max_vereadores) values
 ('a',       0,   15000,  9), ('b',   15001,   30000, 11),
 ('c',   30001,   50000, 13), ('d',   50001,   80000, 15),
 ('e',   80001,  120000, 17), ('f',  120001,  160000, 19),
 ('g',  160001,  300000, 21), ('h',  300001,  450000, 23),
 ('i',  450001,  600000, 25), ('j',  600001,  750000, 27),
 ('k',  750001,  900000, 29), ('l',  900001, 1050000, 31),
 ('m', 1050001, 1200000, 33), ('n', 1200001, 1350000, 35),
 ('o', 1350001, 1500000, 37), ('p', 1500001, 1800000, 39),
 ('q', 1800001, 2400000, 41), ('r', 2400001, 3000000, 43),
 ('s', 3000001, 4000000, 45), ('t', 4000001, 5000000, 47),
 ('u', 5000001, 6000000, 49), ('v', 6000001, 7000000, 51),
 ('w', 7000001, 8000000, 53), ('x', 8000001,    null, 55)
on conflict (letra) do update set
  pop_min = excluded.pop_min, pop_max = excluded.pop_max,
  max_vereadores = excluded.max_vereadores;

-- Art. 29-A: teto de gasto da Camara Municipal, em % da receita tributaria e
-- das transferencias do ano anterior.
create table if not exists faixa_gasto_camara (
  inciso     text primary key,
  pop_min    bigint not null,
  pop_max    bigint,
  percentual numeric(4,2) not null
);

insert into faixa_gasto_camara (inciso, pop_min, pop_max, percentual) values
 ('I',        0,  100000, 7.00),
 ('II',  100001,  300000, 6.00),
 ('III', 300001,  500000, 5.00),
 ('IV',  500001, 3000000, 4.50),
 ('V',  3000001, 8000000, 4.00),
 ('VI', 8000001,    null, 3.50)
on conflict (inciso) do update set percentual = excluded.percentual;

-- Populacao por ente: sem ela os dois tetos acima sao letra morta.
alter table ente add column if not exists populacao      bigint;
alter table ente add column if not exists populacao_ano  integer;
alter table ente add column if not exists populacao_fonte text;

commit;

-- A populacao de referencia da eleicao, adicionada depois de um erro: comparar
-- as cadeiras contra o Censo 2022 acusava 34 camaras de estourar o teto, e 30
-- delas tinham teto maior pela populacao vigente quando as vagas foram
-- fixadas. Guardar as duas e o que impede a plataforma de acusar quem esta em
-- ordem.
begin;
alter table ente add column if not exists populacao_referencia     bigint;
alter table ente add column if not exists populacao_referencia_ano integer;
commit;
