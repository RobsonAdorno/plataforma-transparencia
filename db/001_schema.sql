-- Modelo canonico da plataforma de transparencia.
-- Regra central: vereador e presidente vivem nas mesmas tabelas. O que muda e o
-- cargo e o ente, nunca a estrutura.

begin;

-- ---------------------------------------------------------------- procedencia

-- Toda linha de dado publicavel aponta para cá. E a defesa juridica do projeto
-- e o que permite a tela dizer "fonte: CEAP, coletado em 28/10/2026".
create table if not exists fonte_registro (
  id            bigserial primary key,
  fonte         text        not null,                     -- camara_api, tse_cand, ceap_csv, manual
  tipo          text        not null default 'automatico'
                            check (tipo in ('automatico','manual')),
  url_origem    text,
  documento_url text,                                     -- PDF da nota, pagina do portal
  coletado_em   timestamptz not null default now(),
  hash_conteudo text,
  lote_id       uuid,                                     -- preenchido quando veio de importacao manual
  inserido_por  text,
  observacao    text
);
create index if not exists ix_fonte_registro_fonte on fonte_registro (fonte, coletado_em desc);

-- Importacao manual via CSV. Todo lote e reversivel por inteiro.
create table if not exists importacao_lote (
  id           uuid primary key,
  arquivo      text        not null,
  entidade     text        not null,
  inserido_por text        not null,
  criado_em    timestamptz not null default now(),
  linhas_ok    integer     not null default 0,
  linhas_erro  integer     not null default 0,
  revertido_em timestamptz,
  observacao   text
);

-- Log de auditoria: so aceita insercao. Sem update e sem delete, por regra.
create table if not exists auditoria (
  id          bigserial primary key,
  ocorrido_em timestamptz not null default now(),
  ator        text        not null,
  acao        text        not null,                       -- insert, update, delete, merge, aprovar_identidade
  entidade    text        not null,
  entidade_id text,
  valor_antes jsonb,
  valor_depois jsonb
);

-- ------------------------------------------------------------------- pessoas

create table if not exists pessoa (
  id              bigserial primary key,
  nome_completo   text not null,
  nome_urna       text,
  -- CPF nunca em claro aqui. O numero cru fica no bronze, com acesso restrito.
  cpf_hash        text unique,
  data_nascimento date,
  sexo            text,
  cor_raca        text,
  foto_url        text,
  criado_em       timestamptz not null default now()
);
create index if not exists ix_pessoa_nome on pessoa (lower(nome_completo));

-- A tabela que faz o resto funcionar: liga a mesma pessoa entre TSE, Camara e Senado.
create table if not exists identidade_externa (
  fonte             text   not null,                      -- camara, senado, tse
  id_na_fonte       text   not null,
  pessoa_id         bigint not null references pessoa(id) on delete cascade,
  metodo            text   not null                       -- como o vinculo foi feito
                           check (metodo in ('cpf','nome_nascimento','nome_municipio','manual')),
  confianca         numeric(4,3) not null default 1.000,
  fonte_registro_id bigint references fonte_registro(id),
  primary key (fonte, id_na_fonte)
);
create index if not exists ix_identidade_pessoa on identidade_externa (pessoa_id);

-- Casos abaixo do limiar NAO entram em identidade_externa. Ficam aqui esperando gente.
create table if not exists identidade_pendente (
  id             bigserial primary key,
  fonte          text   not null,
  id_na_fonte    text   not null,
  pessoa_id      bigint references pessoa(id),
  candidatos     jsonb  not null,                         -- alternativas com score
  score          numeric(4,3),
  motivo         text,
  criado_em      timestamptz not null default now(),
  resolvido_em   timestamptz,
  resolvido_por  text,
  decisao        text check (decisao in ('aprovado','rejeitado','novo_registro'))
);

-- -------------------------------------------------------------------- entes

-- Uniao, estados e municipios na mesma tabela, pelo codigo do IBGE.
create table if not exists ente (
  codigo_ibge text primary key,                           -- '0' uniao, '29' BA, '2910800' municipio
  nivel       text not null check (nivel in ('uniao','estado','municipio')),
  nome        text not null,
  uf          text
);

-- ------------------------------------------------------------------ mandatos

create table if not exists mandato (
  id                bigserial primary key,
  pessoa_id         bigint not null references pessoa(id),
  cargo             text   not null
                           check (cargo in ('PRESIDENTE','GOVERNADOR','PREFEITO','SENADOR',
                                            'DEPUTADO_FEDERAL','DEPUTADO_ESTADUAL','VEREADOR')),
  ente_codigo       text   not null references ente(codigo_ibge),
  partido           text,
  legislatura       text,
  data_inicio       date,
  data_fim          date,
  -- Eleito nao e o mesmo que em exercicio. Confundir os dois publica numero
  -- errado com cara de numero certo.
  situacao          text   not null
                           check (situacao in ('eleito','diplomado','em_exercicio','afastado','encerrado')),
  fonte_registro_id bigint references fonte_registro(id),
  unique (pessoa_id, cargo, ente_codigo, legislatura)
);
create index if not exists ix_mandato_ente on mandato (ente_codigo, cargo, situacao);
create index if not exists ix_mandato_pessoa on mandato (pessoa_id);

-- ------------------------------------------------------------------ dinheiro

create table if not exists despesa (
  id                bigserial primary key,
  mandato_id        bigint not null references mandato(id),
  data              date,
  categoria         text,
  descricao         text,
  fornecedor        text,
  cnpj_cpf          text,
  valor             numeric(14,2) not null,
  valor_glosa       numeric(14,2) default 0,
  documento_url     text,
  id_externo        text,
  fonte_registro_id bigint references fonte_registro(id),
  unique (fonte_registro_id, id_externo)
);
create index if not exists ix_despesa_mandato on despesa (mandato_id, data desc);

create table if not exists cargo_gabinete (
  id                bigserial primary key,
  mandato_id        bigint not null references mandato(id),
  pessoa_id         bigint references pessoa(id),
  nome_assessor     text not null,
  cargo             text,
  vinculo           text,
  remuneracao_bruta numeric(12,2),
  mes_referencia    date,
  fonte_registro_id bigint references fonte_registro(id)
);
create index if not exists ix_gabinete_mandato on cargo_gabinete (mandato_id, mes_referencia desc);

-- ---------------------------------------------------------------- legislativo

create table if not exists proposicao (
  id                bigserial primary key,
  ente_codigo       text not null references ente(codigo_ibge),
  id_externo        text,
  tipo              text,
  numero            integer,
  ano               integer,
  ementa            text,
  data_apresentacao date,
  situacao          text,
  tema              text,                                 -- etiqueta revisada por gente
  fonte_registro_id bigint references fonte_registro(id),
  unique (ente_codigo, id_externo)
);

create table if not exists autoria (
  proposicao_id bigint not null references proposicao(id) on delete cascade,
  mandato_id    bigint not null references mandato(id),
  ordem         integer,
  primary key (proposicao_id, mandato_id)
);

create table if not exists votacao (
  id                bigserial primary key,
  ente_codigo       text not null references ente(codigo_ibge),
  id_externo        text,
  proposicao_id     bigint references proposicao(id),
  orgao             text,
  descricao         text,
  data_hora         timestamptz,
  aprovada          boolean,
  -- A maioria das votacoes e simbolica e nao tem voto individual. A tela precisa
  -- dizer isso em vez de sugerir cobertura que nao existe.
  tipo              text not null default 'simbolica'
                         check (tipo in ('nominal','simbolica')),
  fonte_registro_id bigint references fonte_registro(id),
  unique (ente_codigo, id_externo)
);
create index if not exists ix_votacao_data on votacao (data_hora desc);

create table if not exists voto (
  votacao_id bigint not null references votacao(id) on delete cascade,
  mandato_id bigint not null references mandato(id),
  tipo_voto  text   not null,
  primary key (votacao_id, mandato_id)
);

create table if not exists evento (
  id                bigserial primary key,
  ente_codigo       text not null references ente(codigo_ibge),
  id_externo        text,
  tipo              text,
  descricao         text,
  inicio            timestamptz,
  fim               timestamptz,
  situacao          text,
  fonte_registro_id bigint references fonte_registro(id),
  unique (ente_codigo, id_externo)
);

create table if not exists presenca (
  evento_id  bigint not null references evento(id) on delete cascade,
  mandato_id bigint not null references mandato(id),
  presente   boolean,
  primary key (evento_id, mandato_id)
);

-- ------------------------------------------------- obras, repasses, orcamento

create table if not exists obra (
  id                   bigserial primary key,
  id_externo           text unique,
  nome                 text not null,
  descricao            text,
  ente_codigo          text references ente(codigo_ibge),
  uf                   text,
  endereco             text,
  situacao             text,
  data_inicio_prevista date,
  data_fim_prevista    date,
  data_inicio_efetiva  date,
  data_fim_efetiva     date,
  valor_previsto       numeric(16,2),
  executor             text,
  fonte_registro_id    bigint references fonte_registro(id)
);
-- Atraso calculado, que e o que a populacao quer ver.
create or replace view obra_atraso as
  select id, nome, ente_codigo, uf, situacao,
         data_fim_prevista, data_fim_efetiva,
         coalesce(data_fim_efetiva, current_date) - data_fim_prevista as dias_atraso
    from obra
   where data_fim_prevista is not null;

create table if not exists repasse (
  id                bigserial primary key,
  origem            text,
  ente_codigo       text references ente(codigo_ibge),
  programa          text,
  funcao            text,
  valor             numeric(16,2) not null,
  data              date,
  id_externo        text unique,
  fonte_registro_id bigint references fonte_registro(id)
);

create table if not exists orcamento_linha (
  id                bigserial primary key,
  ano               integer not null,
  funcao            text,
  subfuncao         text,
  programa          text,
  dotacao           numeric(18,2),
  empenhado         numeric(18,2),
  pago              numeric(18,2),
  fonte_registro_id bigint references fonte_registro(id)
);

-- ------------------------------------------------- conteudo editorial / admin

-- Responde "qual a responsabilidade de um vereador" agora e alimenta o
-- roteamento do canal de reclamacao depois. Mesma tabela, construida uma vez.
create table if not exists competencia (
  id                bigserial primary key,
  tema              text not null,
  esfera            text not null check (esfera in ('MUNICIPAL','ESTADUAL','FEDERAL')),
  cargo_responsavel text not null,
  descricao         text,
  base_legal        text
);

-- Registro dos portais municipais: a lista que diz onde raspar e com qual parser.
create table if not exists orgao_municipal (
  ente_codigo      text primary key references ente(codigo_ibge),
  nome_camara      text,
  url_portal       text,
  url_transparencia text,
  formato          text,                                  -- API, CSV, HTML, HTML_PDF, PDF
  tem_api          boolean default false,
  qualidade        text check (qualidade in ('BOA','PARCIAL','RUIM','INEXISTENTE')),
  parser           text,
  ultima_coleta    timestamptz,
  observacao       text
);

commit;
