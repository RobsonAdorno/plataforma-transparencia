-- Fase 3: a vida de um projeto de lei, do protocolo ao Diario Oficial.
--
-- Tres decisoes que moldam este schema:
--
-- 1. Guardamos TODAS as movimentacoes, nao so as importantes. Um PL grande tem
--    150 delas e a cidada quer ver 9. Mas quem guarda so as 9 nao consegue
--    mostrar "ver trilha completa" depois, e nao consegue reprocessar quando o
--    mapeamento de marcos melhorar. O filtro e a coluna `marco`, nao o delete.
--
-- 2. `fase` existe para desenhar a barra de progresso sem o front ter que
--    conhecer o regimento. Fase nula = movimentacao que nao anda com o projeto
--    (urgencia, desarquivamento, despacho interno).
--
-- 3. Arquivamento e etapa, nao delete. Em fevereiro de 2027 milhares de PLs
--    morrem de uma vez pelo art. 105 do RICD e alguns voltam. "Esse projeto ja
--    morreu duas vezes" e exatamente o que a plataforma quer poder contar.

begin;

alter table proposicao add column if not exists casa_origem   text;
alter table proposicao add column if not exists regime        text;
alter table proposicao add column if not exists apreciacao    text;
alter table proposicao add column if not exists url_integra   text;
alter table proposicao add column if not exists cod_situacao  integer;
alter table proposicao add column if not exists tramitando    boolean;
alter table proposicao add column if not exists id_senado     text;
alter table proposicao add column if not exists marco_atual   text;
alter table proposicao add column if not exists fase_atual    integer;
alter table proposicao add column if not exists atualizado_em timestamptz;

-- A norma que o projeto virou. Fica na propria proposicao porque e o desfecho
-- dela, nao uma entidade a parte: "PL 1087/2025 virou a Lei 15.270/2025".
alter table proposicao add column if not exists norma_tipo    text;
alter table proposicao add column if not exists norma_numero  text;
alter table proposicao add column if not exists norma_ano     integer;
alter table proposicao add column if not exists norma_data    date;

create index if not exists ix_proposicao_marco  on proposicao (marco_atual, data_apresentacao desc);
create index if not exists ix_proposicao_norma  on proposicao (norma_ano desc, norma_numero)
  where norma_numero is not null;
create index if not exists ix_proposicao_tipo_ano on proposicao (tipo, ano desc, numero);

-- ------------------------------------------------------------------- etapas

create table if not exists etapa (
  id             bigserial primary key,
  proposicao_id  bigint not null references proposicao(id) on delete cascade,
  -- Qual casa registrou. A Camara registra que o Senado aprovou, mas nao
  -- registra o que aconteceu DENTRO do Senado: para isso existe a trilha do
  -- Senado, na mesma tabela, com fonte diferente.
  fonte          text   not null check (fonte in ('camara','senado')),
  sequencia      integer,
  data_hora      timestamptz,
  orgao          text,
  cod_tipo       text,
  descricao      text,
  despacho       text,
  situacao       text,
  cod_situacao   integer,
  url            text,
  relator        text,
  -- Nulo = ruido processual (requerimento, destaque, prazo). A trilha da
  -- cidada mostra so o que tem marco; o resto fica atras de um "ver tudo".
  marco          text,
  fase           integer,
  -- Como o marco foi reconhecido. 'codigo' e deterministico; 'texto' saiu de
  -- regra sobre o despacho e e o que quebra em silencio se a Camara mudar a
  -- redacao. Guardar isso e o que permite medir a fragilidade depois.
  metodo         text check (metodo in ('codigo','texto')),
  fonte_registro_id bigint references fonte_registro(id),
  unique (proposicao_id, fonte, sequencia, cod_tipo, data_hora)
);
create index if not exists ix_etapa_proposicao on etapa (proposicao_id, data_hora);
create index if not exists ix_etapa_marco on etapa (marco, data_hora desc) where marco is not null;

-- ------------------------------------------------------------------- autoria
--
-- Separada de `autoria` (que exige mandato_id) porque autor de proposicao
-- frequentemente NAO e parlamentar: e o Poder Executivo, o STF, o Senado como
-- orgao, ou uma comissao. Forcar tudo em mandato_id perderia justamente o caso
-- mais relevante - a lei que o governo manda pronta.
create table if not exists autoria_proposicao (
  id            bigserial primary key,
  proposicao_id bigint not null references proposicao(id) on delete cascade,
  pessoa_id     bigint references pessoa(id),
  nome          text   not null,
  tipo          text,
  partido       text,
  uf            text,
  ordem         integer,
  proponente    boolean not null default false,
  -- 'autor' assinou o texto original. 'relator' escreveu o texto que foi
  -- votado - que muitas vezes substitui o original por inteiro. Mostrar os
  -- dois lado a lado e a parte mais educativa da pagina.
  papel         text not null default 'autor' check (papel in ('autor','relator')),
  unique (proposicao_id, nome, papel)
);
create index if not exists ix_autoria_prop on autoria_proposicao (proposicao_id, papel, ordem);
create index if not exists ix_autoria_pessoa on autoria_proposicao (pessoa_id) where pessoa_id is not null;

-- ------------------------------------------------- fila de revisao do modelo
--
-- O teste de sanidade escreve aqui. Se a Camara diz que o PL virou norma
-- juridica e a minha trilha nao achou a etapa de lei, o mapeamento regrediu em
-- silencio - e silencio e o pior modo de falhar numa plataforma de dados.
create table if not exists divergencia_tramitacao (
  id            bigserial primary key,
  proposicao_id bigint not null references proposicao(id) on delete cascade,
  tipo          text   not null,
  esperado      text,
  encontrado    text,
  detectado_em  timestamptz not null default now(),
  resolvido_em  timestamptz,
  unique (proposicao_id, tipo)
);

commit;
