-- Fase 2: agenda, pauta e o servico de alerta.

begin;

-- O que esta marcado para ser apreciado num evento. E daqui que sai o aviso
-- "vai ter votacao sobre a PEC tal na quinta".
create table if not exists pauta_item (
  evento_id     bigint  not null references evento(id) on delete cascade,
  proposicao_id bigint  not null references proposicao(id),
  ordem         integer,
  regime        text,
  topico        text,
  primary key (evento_id, proposicao_id)
);

-- Materias que uma pessoa marcou como importantes. Fura o filtro automatico:
-- e o canal pelo qual o julgamento humano entra no sistema.
create table if not exists watchlist (
  proposicao_id  bigint primary key references proposicao(id) on delete cascade,
  motivo         text not null,
  adicionado_por text not null,
  criado_em      timestamptz not null default now()
);

-- Alerta e sempre rascunho ate alguem mandar enviar. Nada sai sozinho.
create table if not exists alerta (
  id            bigserial primary key,
  chave_dedup   text        not null unique,
  tipo          text        not null
                            check (tipo in ('votacao_ocorrida','pauta_futura')),
  titulo        text        not null,
  corpo         text        not null,
  prioridade    integer     not null default 0,
  topicos       text[]      not null default '{}',
  proposicao_id bigint references proposicao(id),
  evento_id     bigint references evento(id),
  votacao_id    bigint references votacao(id),
  estado        text        not null default 'rascunho'
                            check (estado in ('rascunho','aprovado','enviado','descartado')),
  criado_em     timestamptz not null default now(),
  decidido_em   timestamptz,
  decidido_por  text,
  enviado_em    timestamptz
);
create index if not exists ix_alerta_estado on alerta (estado, prioridade desc, criado_em desc);

commit;
