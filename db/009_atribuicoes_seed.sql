-- Conteudo editorial: o que cada cargo pode, o que nao pode, e os tetos.
--
-- Separado do schema de proposito: isto se reescreve, o schema nao. Toda linha
-- entra com revisado=false e so vira "conferido" na tela depois que uma pessoa
-- aprovar no painel. A base_legal e obrigatoria - afirmacao sobre poder de
-- autoridade publica sem artigo do lado nao e transparencia, e opiniao.
--
-- O criterio do 'nao_pode': nao e lista de proibicao juridica, e lista do que
-- as pessoas cobram de quem nao tem como atender. E a parte que mais ensina.

begin;

delete from atribuicao_cargo where revisado = false;

-- =========================================================== VEREADOR
insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('VEREADOR','pode',1,
 'Votar as leis do município sobre assuntos de interesse local — do zoneamento ao calendário de eventos, do transporte ao código de obras.',
 'CF/88, art. 30, I','NACIONAL'),
('VEREADOR','pode',2,
 'Complementar a legislação federal e estadual no que couber à cidade, quando a lei maior deixa espaço para a regra local.',
 'CF/88, art. 30, II','NACIONAL'),
('VEREADOR','pode',3,
 'Aprovar, emendar e rejeitar o orçamento do município. Nenhuma despesa da prefeitura existe sem passar pela Câmara.',
 'CF/88, art. 165; Lei 4.320/1964','NACIONAL'),
('VEREADOR','pode',4,
 'Fiscalizar as contas e os atos do prefeito, com o auxílio técnico do Tribunal de Contas do Estado.',
 'CF/88, art. 31','NACIONAL'),
('VEREADOR','pode',5,
 'Julgar as contas do prefeito. O parecer do Tribunal de Contas vale a não ser que dois terços dos vereadores decidam o contrário — é o único caso em que a Câmara se sobrepõe ao órgão técnico.',
 'CF/88, art. 31, §2º','NACIONAL'),
('VEREADOR','pode',6,
 'Cassar o mandato do prefeito por infração político-administrativa, em processo na própria Câmara.',
 'Decreto-Lei 201/1967, art. 4º','NACIONAL'),
('VEREADOR','pode',7,
 'Abrir comissão parlamentar de inquérito e convocar secretários municipais para prestar contas — nos termos que a Lei Orgânica do município definir.',
 'CF/88, art. 58, §3º (por simetria); Lei Orgânica municipal','LEI_LOCAL');

insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('VEREADOR','nao_pode',1,
 'Asfaltar rua, trocar lâmpada, tapar buraco, limpar terreno ou construir creche. Executar é do prefeito. Quando um vereador "consegue" uma obra, ele pediu — quem decidiu e pagou foi o Executivo.',
 'CF/88, art. 2º e art. 30','NACIONAL'),
('VEREADOR','nao_pode',2,
 'Nomear servidor da prefeitura. O vereador só nomeia dentro do próprio gabinete, na Câmara.',
 'CF/88, art. 37, II; iniciativa privativa do Executivo','NACIONAL'),
('VEREADOR','nao_pode',3,
 'Legislar sobre o que é exclusivo da União: trânsito, direito penal, telecomunicações, energia, direito do trabalho. Lei municipal que entra nesses temas é derrubada na Justiça, e isso acontece com frequência.',
 'CF/88, art. 22','NACIONAL'),
('VEREADOR','nao_pode',4,
 'Aumentar a despesa prevista em projeto de iniciativa exclusiva do prefeito, nem criar gasto sem apontar de onde vem o dinheiro.',
 'CF/88, art. 63, I (por simetria); LC 101/2000 (LRF), art. 15 a 17','NACIONAL'),
('VEREADOR','nao_pode',5,
 'Criar secretaria, cargo ou estrutura dentro da prefeitura. A organização administrativa do Executivo só o prefeito pode propor.',
 'CF/88, art. 61, §1º, II (por simetria)','NACIONAL');

insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('VEREADOR','limite',1,
 'O número de vereadores é fixado pela população, em 24 faixas: de 9 cadeiras em cidades de até 15 mil habitantes a 55 nas acima de 8 milhões. É teto, não piso — a cidade pode ter menos.',
 'CF/88, art. 29, IV (redação da EC 58/2009)','NACIONAL'),
('VEREADOR','limite',2,
 'A Câmara inteira não pode gastar mais que 7% (cidades até 100 mil habitantes) a 3,5% (acima de 8 milhões) da receita de impostos e transferências do ano anterior.',
 'CF/88, art. 29-A','NACIONAL'),
('VEREADOR','limite',3,
 'Da receita que a Câmara recebe, no máximo 70% pode ir para folha de pagamento.',
 'CF/88, art. 29-A, §1º','NACIONAL'),
('VEREADOR','limite',4,
 'O subsídio de um vereador vai de 20% a 75% do subsídio de deputado estadual, conforme o tamanho da cidade.',
 'CF/88, art. 29, VI (redação da EC 25/2000)','NACIONAL'),
('VEREADOR','limite',5,
 'A soma de tudo que se paga aos vereadores não pode passar de 5% da receita do município.',
 'CF/88, art. 29, VII','NACIONAL');

-- =========================================================== PREFEITO
insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('PREFEITO','pode',1,
 'Executar o orçamento aprovado pela Câmara: é ele que contrata, paga e entrega.',
 'CF/88, art. 165 e 167','NACIONAL'),
('PREFEITO','pode',2,
 'Organizar e prestar os serviços públicos de interesse local, incluindo o transporte coletivo, que a Constituição dá expressamente ao município.',
 'CF/88, art. 30, V','NACIONAL'),
('PREFEITO','pode',3,
 'Manter os programas de educação infantil e de ensino fundamental, com apoio técnico e financeiro da União e do estado.',
 'CF/88, art. 30, VI e art. 211, §2º','NACIONAL'),
('PREFEITO','pode',4,
 'Prestar atendimento à saúde da população — a atenção básica, as UBS e as equipes de família são responsabilidade do município.',
 'CF/88, art. 30, VII e art. 198','NACIONAL'),
('PREFEITO','pode',5,
 'Decidir o uso e a ocupação do solo urbano: zoneamento, plano diretor, licença de construção.',
 'CF/88, art. 30, VIII e art. 182','NACIONAL'),
('PREFEITO','pode',6,
 'Instituir e cobrar os tributos do município: IPTU, ISS e ITBI.',
 'CF/88, art. 156','NACIONAL'),
('PREFEITO','pode',7,
 'Vetar, total ou parcialmente, projeto aprovado pela Câmara — e a Câmara pode derrubar o veto.',
 'CF/88, art. 66, §1º (por simetria); Lei Orgânica municipal','LEI_LOCAL');

insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('PREFEITO','nao_pode',1,
 'Fazer policiamento ostensivo. Polícia Militar e Polícia Civil são do estado. A guarda municipal protege os bens e serviços do município — não é polícia de rua.',
 'CF/88, art. 144, §§ 4º, 5º e 8º','NACIONAL'),
('PREFEITO','nao_pode',2,
 'Gastar sem dotação orçamentária, nem começar obra ou programa que não esteja no orçamento.',
 'CF/88, art. 167, I e II','NACIONAL'),
('PREFEITO','nao_pode',3,
 'Legislar por conta própria. Não existe medida provisória municipal: para mudar a lei da cidade, ele depende da Câmara.',
 'CF/88, art. 62 (restrito à União)','NACIONAL'),
('PREFEITO','nao_pode',4,
 'Assumir despesa nos últimos oito meses de mandato sem deixar dinheiro em caixa para pagá-la, nem aumentar gasto com pessoal nos 180 dias finais.',
 'LC 101/2000 (LRF), art. 21 e art. 42','NACIONAL'),
('PREFEITO','nao_pode',5,
 'Criar imposto que a Constituição não deu ao município, nem cobrar taxa sem serviço específico em troca.',
 'CF/88, art. 145 e art. 156','NACIONAL'),
('PREFEITO','nao_pode',6,
 'Cuidar de rodovia federal ou estadual que corta a cidade, nem de escola estadual ou hospital federal que fica nela. Estar dentro do município não transfere a responsabilidade.',
 'CF/88, art. 21, art. 25, §1º e art. 30','NACIONAL');

-- =================================================== DEPUTADO ESTADUAL
insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('DEPUTADO_ESTADUAL','pode',1,
 'Fazer as leis do estado sobre tudo que não é exclusivo da União nem de interesse puramente local — a chamada competência residual.',
 'CF/88, art. 25, §1º','NACIONAL'),
('DEPUTADO_ESTADUAL','pode',2,
 'Legislar junto com a União em temas compartilhados: educação, saúde, meio ambiente, proteção ao consumidor, defesa civil. O estado preenche o que a lei federal deixa em aberto.',
 'CF/88, art. 24','NACIONAL'),
('DEPUTADO_ESTADUAL','pode',3,
 'Aprovar e emendar o orçamento do estado, e fiscalizar o governador com o auxílio do Tribunal de Contas do Estado.',
 'CF/88, art. 165 e art. 75','NACIONAL'),
('DEPUTADO_ESTADUAL','pode',4,
 'Abrir CPI estadual, convocar secretários e sustar atos do governador que extrapolem o poder regulamentar.',
 'CF/88, art. 27, §1º e art. 58, §3º','NACIONAL'),
('DEPUTADO_ESTADUAL','pode',5,
 'Autorizar o governador a se ausentar do estado e julgá-lo por crime de responsabilidade, conforme a Constituição estadual.',
 'CF/88, art. 25; Constituição do estado','LEI_LOCAL');

insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('DEPUTADO_ESTADUAL','nao_pode',1,
 'Legislar sobre o que é exclusivo da União: direito penal, trânsito, trabalho, telecomunicações, energia elétrica, moeda.',
 'CF/88, art. 22','NACIONAL'),
('DEPUTADO_ESTADUAL','nao_pode',2,
 'Legislar sobre assunto de interesse local — isso é da Câmara Municipal, mesmo quando a cidade é a capital.',
 'CF/88, art. 30, I','NACIONAL'),
('DEPUTADO_ESTADUAL','nao_pode',3,
 'Comandar a Polícia Militar, nomear delegado ou dirigir obra estadual. Executar é do governador.',
 'CF/88, art. 2º e art. 144, §6º','NACIONAL'),
('DEPUTADO_ESTADUAL','nao_pode',4,
 'Contrariar a lei federal nos temas de competência compartilhada: onde a União fixou a regra geral, a lei estadual não pode ir contra.',
 'CF/88, art. 24, §§ 1º a 4º','NACIONAL');

-- =========================================================== GOVERNADOR
insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('GOVERNADOR','pode',1,
 'Comandar a segurança pública do estado: Polícia Militar, Polícia Civil, Corpo de Bombeiros e o sistema prisional. É a maior responsabilidade do cargo e a mais cobrada no endereço errado.',
 'CF/88, art. 144, §§ 4º, 5º e 6º','NACIONAL'),
('GOVERNADOR','pode',2,
 'Responder pelo ensino médio e pelas rodovias estaduais.',
 'CF/88, art. 211, §3º e art. 25, §1º','NACIONAL'),
('GOVERNADOR','pode',3,
 'Executar o orçamento do estado, instituir e cobrar ICMS, IPVA e ITCMD.',
 'CF/88, art. 155 e art. 165','NACIONAL'),
('GOVERNADOR','pode',4,
 'Sancionar ou vetar os projetos da Assembleia e propor leis de iniciativa exclusiva do Executivo estadual.',
 'CF/88, art. 25 e art. 66 (por simetria)','NACIONAL'),
('GOVERNADOR','pode',5,
 'Organizar regiões metropolitanas e aglomerações urbanas, agrupando municípios para serviços comuns.',
 'CF/88, art. 25, §3º','NACIONAL');

insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('GOVERNADOR','nao_pode',1,
 'Usar a Polícia Federal ou as Forças Armadas. Essas respondem ao governo federal; o governador pode pedir, não mandar.',
 'CF/88, art. 21, XIV, art. 84, XIII e art. 144, §1º','NACIONAL'),
('GOVERNADOR','nao_pode',2,
 'Cuidar de rodovia federal, aeroporto ou porto — mesmo os que ficam dentro do estado.',
 'CF/88, art. 21, XII','NACIONAL'),
('GOVERNADOR','nao_pode',3,
 'Mandar na prefeitura, nem assumir serviço que é do município, como coleta de lixo, iluminação ou atenção básica de saúde.',
 'CF/88, art. 18 e art. 30','NACIONAL'),
('GOVERNADOR','nao_pode',4,
 'Gastar acima dos limites de pessoal e de dívida fixados em lei nacional, nem contratar empréstimo sem autorização.',
 'LC 101/2000 (LRF), art. 19 e art. 32','NACIONAL');

-- ==================================================== DEPUTADO FEDERAL
insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('DEPUTADO_FEDERAL','pode',1,
 'Propor e votar as leis nacionais, que valem para os 5.571 municípios e os 27 estados.',
 'CF/88, art. 48 e art. 61','NACIONAL'),
('DEPUTADO_FEDERAL','pode',2,
 'Aprovar o orçamento da União e apresentar emendas que direcionam dinheiro federal para obras e serviços.',
 'CF/88, art. 48, II e art. 166','NACIONAL'),
('DEPUTADO_FEDERAL','pode',3,
 'Fiscalizar o governo federal: convocar ministro, pedir informação por escrito, abrir CPI e sustar ato do Executivo que exceda o poder regulamentar.',
 'CF/88, art. 49, V e X; art. 50; art. 58, §3º','NACIONAL'),
('DEPUTADO_FEDERAL','pode',4,
 'Autorizar a abertura de processo de impeachment do Presidente, por dois terços da Câmara. A Câmara acusa; o Senado julga.',
 'CF/88, art. 51, I e art. 86','NACIONAL'),
('DEPUTADO_FEDERAL','pode',5,
 'Derrubar veto presidencial, em sessão conjunta com o Senado e por maioria absoluta das duas casas.',
 'CF/88, art. 66, §4º','NACIONAL'),
('DEPUTADO_FEDERAL','pode',6,
 'Propor emenda à Constituição, com assinatura de um terço dos deputados.',
 'CF/88, art. 60, I','NACIONAL');

insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('DEPUTADO_FEDERAL','nao_pode',1,
 'Resolver problema de rua, bairro ou cidade. Buraco, poste e creche não são matéria de lei federal: isso é prefeitura.',
 'CF/88, art. 30','NACIONAL'),
('DEPUTADO_FEDERAL','nao_pode',2,
 'Criar ou aumentar despesa em projeto de iniciativa exclusiva do Presidente, nem mexer na organização dos ministérios.',
 'CF/88, art. 61, §1º e art. 63, I','NACIONAL'),
('DEPUTADO_FEDERAL','nao_pode',3,
 'Executar a emenda que ele mesmo propôs. A emenda destina o dinheiro; quem contrata e paga é o Executivo.',
 'CF/88, art. 165 e art. 166','NACIONAL'),
('DEPUTADO_FEDERAL','nao_pode',4,
 'Aprovar emenda constitucional que ataque a forma federativa, o voto direto e secreto, a separação dos poderes ou os direitos e garantias individuais — são as cláusulas pétreas.',
 'CF/88, art. 60, §4º','NACIONAL'),
('DEPUTADO_FEDERAL','nao_pode',5,
 'Legislar sozinho: todo projeto que ele aprova ainda precisa passar pelo Senado e pela sanção do Presidente.',
 'CF/88, art. 65 e art. 66','NACIONAL');

-- =========================================================== SENADOR
insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('SENADOR','pode',1,
 'Legislar como revisor ou iniciador de qualquer lei federal, com mandato de oito anos — o dobro dos deputados.',
 'CF/88, art. 46 e art. 48','NACIONAL'),
('SENADOR','pode',2,
 'Aprovar ou rejeitar as indicações do Presidente para o STF, os tribunais superiores, o Banco Central, o Procurador-Geral da República, as agências reguladoras e as embaixadas.',
 'CF/88, art. 52, III e IV','NACIONAL'),
('SENADOR','pode',3,
 'Julgar o Presidente da República no impeachment, depois que a Câmara autoriza. A condenação exige dois terços do Senado.',
 'CF/88, art. 52, I e art. 86','NACIONAL'),
('SENADOR','pode',4,
 'Autorizar operações de crédito e fixar limites de endividamento da União, dos estados e dos municípios.',
 'CF/88, art. 52, V a IX','NACIONAL'),
('SENADOR','pode',5,
 'Suspender a execução de lei declarada inconstitucional pelo STF.',
 'CF/88, art. 52, X','NACIONAL');

insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('SENADOR','nao_pode',1,
 'Iniciar o impeachment. Essa porta é só da Câmara dos Deputados; o Senado entra depois, como tribunal.',
 'CF/88, art. 51, I','NACIONAL'),
('SENADOR','nao_pode',2,
 'Iniciar projeto de lei que crie despesa de competência exclusiva do Presidente, nem lei orçamentária.',
 'CF/88, art. 61, §1º e art. 165','NACIONAL'),
('SENADOR','nao_pode',3,
 'Resolver demanda de bairro ou de cidade. O Senado representa o estado como unidade da Federação, não o município.',
 'CF/88, art. 46','NACIONAL');

-- =========================================================== PRESIDENTE
insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('PRESIDENTE','pode',1,
 'Sancionar, vetar e regulamentar as leis aprovadas pelo Congresso. O veto pode ser total ou parcial — e o Congresso pode derrubá-lo.',
 'CF/88, art. 84, III a V e art. 66','NACIONAL'),
('PRESIDENTE','pode',2,
 'Editar medida provisória, com força de lei imediata, em caso de relevância e urgência. Ela caduca em 60 dias, prorrogáveis uma vez, se o Congresso não aprovar.',
 'CF/88, art. 62','NACIONAL'),
('PRESIDENTE','pode',3,
 'Comandar as Forças Armadas, nomear ministros e dirigir a administração federal.',
 'CF/88, art. 84, I, II e XIII','NACIONAL'),
('PRESIDENTE','pode',4,
 'Representar o país, celebrar tratados e manter relações com outros Estados — sujeito a referendo do Congresso.',
 'CF/88, art. 84, VII e VIII','NACIONAL'),
('PRESIDENTE','pode',5,
 'Nomear ministros do STF e dos tribunais superiores, o Procurador-Geral da República e o presidente do Banco Central, todos com aprovação do Senado.',
 'CF/88, art. 84, XIV a XVI','NACIONAL'),
('PRESIDENTE','pode',6,
 'Decretar estado de defesa, estado de sítio e intervenção federal, sob controle do Congresso.',
 'CF/88, art. 84, IX e X; art. 136 a 141','NACIONAL');

insert into atribuicao_cargo (cargo, natureza, ordem, texto, base_legal, abrangencia) values
('PRESIDENTE','nao_pode',1,
 'Usar medida provisória para tratar de direito penal, eleitoral, processual, orçamento ou matéria reservada a lei complementar.',
 'CF/88, art. 62, §1º','NACIONAL'),
('PRESIDENTE','nao_pode',2,
 'Gastar acima do que o Congresso autorizou no orçamento, nem abrir crédito sem lei.',
 'CF/88, art. 167','NACIONAL'),
('PRESIDENTE','nao_pode',3,
 'Mandar em governador ou prefeito. A Federação é formada por entes autônomos; intervir exige as hipóteses fechadas da Constituição.',
 'CF/88, art. 18 e art. 34','NACIONAL'),
('PRESIDENTE','nao_pode',4,
 'Legislar sobre assunto de interesse local ou estadual, nem interferir na Polícia Militar de um estado.',
 'CF/88, art. 25, art. 30 e art. 144, §6º','NACIONAL'),
('PRESIDENTE','nao_pode',5,
 'Permanecer no cargo depois de condenado pelo Senado por crime de responsabilidade.',
 'CF/88, art. 86','NACIONAL');

commit;
