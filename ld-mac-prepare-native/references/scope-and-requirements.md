# Escopo e requisitos — Prepare My Mac

## Visão do produto

Prepare My Mac é um agente pessoal de transição de contexto para macOS. Ele entende o próximo objetivo, prepara um ambiente visualmente organizado, protege o contexto atual em uma Context Capsule e permite retomar o trabalho com a intenção anterior preservada.

Proposta central:

> **Your Mac is ready before you are.**

## Princípios obrigatórios

- [x] Sem APIs externas, OAuth, SDK Google ou upload em nuvem.
- [x] Dados pessoais, histórico, gravações e transcrições permanecem no Mac.
- [x] Python usa somente biblioteca padrão.
- [x] Automação usa frameworks e binários nativos: AppleScript/JXA, AppKit, Calendar, ScreenCaptureKit, AVFoundation e Speech.
- [x] Gravação exige consentimento explícito em cada sessão.
- [x] Ações normais são reversíveis: abrir, ocultar, organizar e restaurar.
- [x] Nenhum fluxo fecha apps, apaga arquivos ou envia conteúdo automaticamente.
- [x] Respostas e resultados de CLI são curtos e estruturados.

## P0 — Demo vencedora

### 1. Smart Prepare

- [x] Modos nativos: `coding`, `focus`, `meeting`, `presentation`, `study`.
- [x] Modos customizados por linguagem natural através do Hermes/iMessage.
- [x] Apps, URLs, distrações e layout persistidos localmente.
- [x] Abertura rápida sem sleeps por app.
- [x] Falhas parciais reportadas sem falso sucesso.
- [x] Notificação nativa confirma ativação e restauração sem bloquear o fluxo.

Critério de aceite: `activate <mode>` salva o contexto atual, oculta apenas distrações configuradas, abre os recursos válidos, aplica o layout e retorna JSON com todas as ações e falhas.

### 2. Context Capsule + Resume My Mac

- [x] Salvar apps ativos, app frontal, janelas, posições, tamanhos, monitores, abas do Chrome e intenção declarada.
- [x] Restaurar apps, abas e geometria de janelas.
- [x] Reapresentar a intenção como “Why I was here”.
- [x] Snapshot local com escrita atômica e permissão privada.

Critério de aceite: depois de alternar para uma reunião, `resume` recompõe o ambiente salvo e devolve a intenção sem gerar informação nova.

### 3. Desktop apresentável

- [x] `presentable`: janela principal em destaque e apps auxiliares organizados.
- [x] `split`: duas metades.
- [x] `top`: janela na porção superior.
- [x] `corner`: janela no canto superior direito.
- [x] `grid`: grade 2×2.
- [x] Adaptação automática a um ou dois monitores.

Critério de aceite: com dois monitores, `presentable` coloca o app principal em tela cheia útil no monitor principal e distribui apoios no segundo; com um monitor, usa composição 68/32.

### 4. Trust moment da reunião

- [x] Calendar nativo detecta evento próximo sem API externa.
- [x] Evento gera somente sugestão; não muda o Mac sozinho.
- [x] Gravação nunca inicia sem `--confirmed-by-user`.
- [x] Captura separada de microfone e áudio do sistema.
- [x] Transcrição on-device; sem fallback de rede.
- [x] Resumo local com overview, decisões, ações e transcript.

Critério de aceite: negar ou omitir confirmação impede a gravação; indisponibilidade do Speech mantém o áudio salvo e retorna um erro claro de transcrição.

## P1 — Confiabilidade e performance

- [x] Configuração com escrita atômica, `fsync` e permissão `0600`.
- [x] Auditoria NDJSON com lock para concorrência.
- [x] Estado de gravação persistido por PID, permitindo `start` e `stop` em processos distintos.
- [x] Parâmetros enviados ao AppleScript por `argv`, não por interpolação.
- [x] Timeout em comandos nativos.
- [x] `--dry-run` para validar fluxos sem alterar o Mac.
- [x] Helper Swift compilado uma vez com `-O` e reutilizado.

Meta de demo em Mac já autorizado:

- Resolver configuração: menos de 100 ms.
- Iniciar transição: percepção imediata; apps são disparados sem espera serial.
- Aplicar layout: até 2 s após apps abrirem.
- Resposta do comando: JSON em uma linha.

## P2 — Evoluções após o hackathon

- [ ] Aprender sugestões a partir de correções sem alterar modos automaticamente.
- [ ] Suporte opcional ao Safari para captura/restauração de abas.
- [ ] Matching de eventos com projetos locais por título, participantes e histórico.
- [ ] Menu bar app assinado para distribuir o helper sem depender de Command Line Tools.
- [ ] Assinatura/notarização e testes em Macs Intel e Apple Silicon.

## Requisitos de ambiente

- macOS 15 ou superior para captura simultânea de microfone + áudio do sistema.
- Apple Command Line Tools na versão de desenvolvimento/hackathon para compilar o helper uma vez.
- Permissões concedidas ao host Hermes: Automation, Accessibility, Calendar, Screen & System Audio Recording, Microphone e Speech Recognition.
- Google Chrome é opcional; modos sem URLs funcionam sem ele.

## Fora de escopo

- Google Calendar/Gmail/Drive APIs.
- Qualquer API de IA ou transcrição externa.
- Fechar apps ou descartar alterações.
- Enviar mensagens, e-mails ou convites diretamente.
- Captura silenciosa, contínua ou automática.
- Promessa de “zero bugs”. O objetivo verificável é falhar com segurança, preservar dados e reportar erros sem falso sucesso.

## Roteiro de validação

- [ ] Rodar testes Python em Linux/CI.
- [ ] Rodar `mac_executor.py check` no Mac de demo.
- [ ] Rodar os três modos principais com `--dry-run`.
- [ ] Compilar `meeting_recorder.py build`.
- [ ] Testar cada permissão separadamente.
- [ ] Testar um e dois monitores.
- [ ] Testar Chrome ausente/fechado.
- [ ] Testar gravação negada, iniciada, interrompida e recuperação após processo órfão.
- [ ] Ensaiar o roteiro completo abaixo sem internet.
