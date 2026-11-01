-- Fase 5: o canal de reclamacao cidada.
--
-- O cidadao descreve um problema, a plataforma identifica a esfera responsavel
-- pela tabela `competencia`, roteia para quem tem poder de resolver, e deixa a
-- reclamacao PUBLICA com prazo contado. Se nao vier resposta, a plataforma diz
-- isso com clareza e mostra o que fazer em seguida.
--
-- Tres decisoes que moldam o schema:
--
-- 1. O prazo nao e invencao nossa. A Lei 13.460/2017 (Codigo de Defesa do
--    Usuario de Servicos Publicos) da a reclamacao o status de "manifestacao"
--    (art. 2, V) e obriga a ouvidoria a enviar a decisao administrativa final
--    ao usuario em 30 dias, prorrogavel uma vez por igual periodo mediante
--    justificativa (art. 16). Por isso `prazo_resposta` e data calculada, e
--    `prorrogado` existe: sem ele a plataforma acusaria de omissa uma
--    prefeitura que usou um direito que a lei lhe da.
--
-- 2. Silencio e informacao. O estado 'sem_resposta' nao e falha de coleta: e o
--    achado. Uma plataforma que so mostrasse as respondidas esconderia
--    justamente o que o cidadao precisa saber.
--
-- 3. Identidade do cidadao fica fora. A Lei 13.460 exige identificacao do
--    manifestante perante o orgao (art. 10), mas isso e com o orgao, nao com a
--    gente - e reclamacao e dado sensivel: revela onde a pessoa mora e do que
--    ela reclama. Guardamos o minimo para notificar e um hash para evitar
--    duplicata, e o nome so aparece se a pessoa marcar.

begin;

create table if not exists reclamacao (
  id                 bigserial primary key,
  -- Codigo publico, legivel, que a pessoa anota e usa para acompanhar.
  protocolo          text        not null unique,
  ente_codigo        text        not null references ente(codigo_ibge),
  tema               text,
  -- Esfera e cargo saem do roteamento por `competencia`, nao de escolha do
  -- cidadao: a pessoa nao tem por que saber de quem e a culpa - descobrir
  -- isso e o servico que a plataforma presta.
  esfera_responsavel text        check (esfera_responsavel in ('MUNICIPAL','ESTADUAL','FEDERAL')),
  cargo_destino      text,
  destino_nome       text,
  destino_orgao      text,
  destino_email      text,
  destino_metodo     text        check (destino_metodo in ('email','ouvidoria','protocolo','indefinido')),

  titulo             text        not null,
  descricao          text        not null,
  local_referencia   text,
  latitude           numeric(9,6),
  longitude          numeric(9,6),

  -- Identificacao minima. autor_hash permite barrar duplicata sem guardar
  -- quem e; autor_nome so vai para a tela se exibir_autor for verdadeiro.
  autor_hash         text,
  autor_nome         text,
  autor_email        text,
  exibir_autor       boolean     not null default false,

  estado             text        not null default 'recebida'
                                 check (estado in ('recebida','encaminhada','respondida',
                                                   'sem_resposta','improcedente','arquivada')),
  publica            boolean     not null default true,

  criado_em          timestamptz not null default now(),
  encaminhado_em     timestamptz,
  -- 30 dias do encaminhamento (Lei 13.460/2017, art. 16).
  prazo_resposta     date,
  prorrogado         boolean     not null default false,
  prorrogado_ate     date,
  respondido_em      timestamptz,
  resposta           text,
  resposta_autor     text,
  -- Quem reclamou diz se a resposta resolveu. E a unica metrica que importa:
  -- orgao que responde sempre e nunca resolve nao e orgao transparente.
  resolvido          boolean,
  avaliado_em        timestamptz
);
create index if not exists ix_reclamacao_ente on reclamacao (ente_codigo, criado_em desc);
create index if not exists ix_reclamacao_estado on reclamacao (estado, prazo_resposta);
create index if not exists ix_reclamacao_publica on reclamacao (publica, criado_em desc)
  where publica;

-- Linha do tempo publica, no mesmo espirito de `etapa` nas leis: o valor esta
-- em mostrar o caminho, nao so o estado atual.
create table if not exists reclamacao_evento (
  id            bigserial primary key,
  reclamacao_id bigint      not null references reclamacao(id) on delete cascade,
  tipo          text        not null,
  descricao     text,
  ator          text,
  criado_em     timestamptz not null default now()
);
create index if not exists ix_reclamacao_evento on reclamacao_evento (reclamacao_id, criado_em);

-- Onde reclamar em cada ente: a ouvidoria, o e-mail, o portal. Enquanto nao
-- estiver preenchido, a reclamacao fica com destino_metodo='indefinido' e a
-- tela diz que nao sabemos para onde mandar - que e verdade, e e melhor que
-- fingir que mandamos.
create table if not exists canal_atendimento (
  ente_codigo   text    not null references ente(codigo_ibge),
  tipo          text    not null check (tipo in ('ouvidoria','email','portal','telefone','lai')),
  valor         text    not null,
  orgao         text,
  observacao    text,
  verificado_em date,
  primary key (ente_codigo, tipo, valor)
);

-- ------------------------------------------------- o que fazer sem resposta
--
-- A parte mais util da feature, e a que o usuario disse nao saber. Nao e
-- opiniao: cada passo tem base legal e um prazo proprio. Ordenado do mais
-- simples ao mais pesado, porque mandar o cidadao direto ao Ministerio
-- Publico por um poste queimado desperdica o instrumento.

create table if not exists escalonamento (
  id            bigserial primary key,
  esfera        text    not null check (esfera in ('MUNICIPAL','ESTADUAL','FEDERAL')),
  ordem         integer not null,
  orgao         text    not null,
  o_que_fazer   text    not null,
  prazo         text,
  base_legal    text    not null,
  quando_usar   text,
  revisado      boolean not null default false,
  unique (esfera, ordem)
);

insert into escalonamento (esfera, ordem, orgao, o_que_fazer, prazo, base_legal, quando_usar) values
('MUNICIPAL', 1, 'Ouvidoria da prefeitura',
 'Registre a mesma reclamação na ouvidoria do município e guarde o número de protocolo. A ouvidoria é obrigada a analisar, encaminhar ao setor competente e acompanhar até a conclusão.',
 '30 dias para a decisão final, prorrogáveis uma vez por igual período com justificativa',
 'Lei 13.460/2017, art. 10, 13 e 16',
 'Primeiro passo sempre. Sem protocolo registrado, os passos seguintes ficam sem prova de que você tentou.'),

('MUNICIPAL', 2, 'Pedido de informação pela Lei de Acesso',
 'Em vez de pedir a solução, pergunte por escrito o que foi feito: qual o setor responsável, qual o número do processo interno, se há obra prevista e com qual dotação orçamentária. Pergunta objetiva é mais difícil de ignorar que pedido genérico.',
 '20 dias, prorrogáveis por 10 com justificativa; se negarem ou não responderem, cabe recurso à autoridade superior em 10 dias',
 'Lei 12.527/2011 (LAI), art. 11 e 15',
 'Quando a ouvidoria não responde, ou responde sem dizer nada. O prazo da LAI é mais curto e o recurso é definido em lei.'),

('MUNICIPAL', 3, 'Vereador da sua cidade',
 'Leve o protocolo a um vereador e peça que ele apresente requerimento de informação à prefeitura. Fiscalizar o Executivo é função constitucional da Câmara, não favor.',
 'Depende do Regimento Interno da Câmara',
 'CF/88, art. 31; Lei Orgânica do município',
 'Quando há silêncio administrativo. O requerimento de um vereador entra por outra porta e fica registrado em sessão pública.'),

('MUNICIPAL', 4, 'Ministério Público do seu estado',
 'Represente ao MP estadual descrevendo o problema, anexando os protocolos e o silêncio. O promotor pode abrir inquérito civil e, se for o caso, propor ação civil pública.',
 'Não há prazo fixo para a resposta do MP',
 'CF/88, art. 129, II e III; Lei 7.347/1985',
 'Omissão em serviço essencial — água, esgoto, saúde, escola, lixo — ou risco à segurança das pessoas. Não use para questão estética.'),

('MUNICIPAL', 5, 'Tribunal de Contas do Estado',
 'Represente ao TCE quando houver dinheiro envolvido: obra paga e não entregue, contrato sem execução, serviço faturado e não prestado.',
 'Não há prazo fixo',
 'CF/88, art. 31, §1º e art. 74, §2º',
 'Só quando há gasto público identificável. Para buraco em rua que nunca teve obra contratada, este não é o caminho.'),

('MUNICIPAL', 6, 'Defensoria Pública',
 'Se o problema afeta você diretamente e você não pode pagar advogado, a Defensoria pode ajuizar ação. Atendimento gratuito.',
 'Varia por comarca',
 'CF/88, art. 134; LC 80/1994',
 'Quando o problema é individual e já virou lesão a direito seu — falta de vaga em creche, de medicamento, de laudo.'),

('ESTADUAL', 1, 'Ouvidoria do órgão estadual',
 'Registre na ouvidoria da secretaria responsável e guarde o protocolo. Vale o mesmo prazo de 30 dias da esfera municipal.',
 '30 dias, prorrogáveis uma vez',
 'Lei 13.460/2017, art. 16',
 'Primeiro passo. Segurança pública, rodovia estadual e ensino médio são do estado, não da prefeitura.'),
('ESTADUAL', 2, 'Pedido de informação pela Lei de Acesso',
 'Pergunte por escrito o que foi feito e com qual processo. O estado tem portal próprio de acesso à informação.',
 '20 dias + 10 de prorrogação; recurso em 10 dias',
 'Lei 12.527/2011, art. 11 e 15', 'Quando a ouvidoria silencia.'),
('ESTADUAL', 3, 'Deputado estadual',
 'Peça a um deputado estadual que apresente requerimento de informação ao governo do estado. Fiscalizar o Executivo é função da Assembleia.',
 'Depende do Regimento da Assembleia',
 'CF/88, art. 25 e art. 58, §3º (por simetria)', 'Diante de silêncio administrativo.'),
('ESTADUAL', 4, 'Ministério Público do seu estado',
 'Represente ao MP com os protocolos e o silêncio anexados.',
 'Sem prazo fixo', 'CF/88, art. 129, II; Lei 7.347/1985',
 'Omissão em serviço essencial estadual.'),

('FEDERAL', 1, 'Ouvidoria do órgão federal',
 'Use o Fala.BR, canal único do governo federal para manifestações e pedidos de informação.',
 '30 dias, prorrogáveis uma vez',
 'Lei 13.460/2017, art. 16; Decreto 9.492/2018', 'Primeiro passo na esfera federal.'),
('FEDERAL', 2, 'Pedido de informação pela Lei de Acesso',
 'Pelo mesmo Fala.BR, agora como pedido de acesso à informação — o prazo é menor e o recurso é escalonado.',
 '20 dias + 10; recursos sucessivos até a CGU',
 'Lei 12.527/2011, art. 11, 15 e 16', 'Quando a resposta não vem ou vem vazia.'),
('FEDERAL', 3, 'Controladoria-Geral da União',
 'Recorra à CGU, que é a instância de recurso dos pedidos de informação federais negados.',
 '5 dias para a CGU decidir após o recurso', 'Lei 12.527/2011, art. 16',
 'Depois de esgotado o recurso dentro do próprio órgão.'),
('FEDERAL', 4, 'Ministério Público Federal',
 'Represente ao MPF quando houver omissão federal em serviço essencial.',
 'Sem prazo fixo', 'CF/88, art. 129, II', 'Última instância administrativa esgotada.')
on conflict (esfera, ordem) do update set
  orgao=excluded.orgao, o_que_fazer=excluded.o_que_fazer, prazo=excluded.prazo,
  base_legal=excluded.base_legal, quando_usar=excluded.quando_usar;

commit;
