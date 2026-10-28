-- Para reverter um lote inteiro, toda tabela que aceita importacao manual
-- precisa apontar para fonte_registro - que e quem carrega o lote_id.
begin;

alter table competencia      add column if not exists fonte_registro_id bigint references fonte_registro(id);
alter table orgao_municipal  add column if not exists fonte_registro_id bigint references fonte_registro(id);

-- competencia nao tinha chave natural: sem isso o reimport duplica.
create unique index if not exists ux_competencia_tema
  on competencia (lower(tema), esfera, cargo_responsavel);

-- Quem opera o painel. Sem cadastro publico: a linha entra por script.
-- A identidade e verificada por um provedor externo; aqui so guardamos quem
-- pode o que, nunca senha.
create table if not exists administrador (
  id          bigserial primary key,
  email       text unique not null,
  nome        text,
  papel       text not null default 'editor' check (papel in ('editor','admin')),
  ativo       boolean not null default true,
  criado_em   timestamptz not null default now(),
  ultimo_acesso timestamptz
);

commit;
