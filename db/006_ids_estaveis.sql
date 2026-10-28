-- O carregador truncava pessoa e reiniciava os ids a cada execucao. Como a URL
-- publica e /deputado/<id>/<slug>, isso faria o mesmo endereco apontar para
-- outra pessoa depois de cada recarga - quebra link compartilhado e busca.
--
-- A despesa era unica por (fonte_registro_id, id_externo), e como o
-- fonte_registro nasce novo a cada execucao, so o truncate evitava duplicata.
-- A chave ja e um hash dos campos de negocio, entao basta ser unica sozinha.
begin;
alter table despesa drop constraint if exists despesa_fonte_registro_id_id_externo_key;
create unique index if not exists ux_despesa_id_externo on despesa (id_externo);
commit;
