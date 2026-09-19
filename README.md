# Coffee Work

**Coffee Work turns a Mac into a calmer workday.** It is a practical work companion that watches the calendar, prepares the computer for the next meeting, helps capture decisions, and coordinates the small logistics around a busy schedule.

Built for **Hermes + Plow Chat + Plow Latch** on macOS. The agent talks to the user in **English**, as required by the hackathon.

- [English](#english) · [Português](#português) · [Install on macOS](#install-on-macos) · [Demo prompts](#demo-prompts)

---

## English

### Why Coffee Work?

The friction around work is rarely one big task. It is the five minutes before a call, the browser tab that is not open, the notes that disappear after a meeting, and the reservation or ride that is easy to forget. Coffee Work connects those moments into one workflow.

It uses the user's Google Calendar through Plow Latch, coordinates skills through Hermes, and performs Mac actions only with the owner's permissions. A calendar watcher checks the next events every ten minutes and offers help at the right moment.

### What it does

| Work moment | Coffee Work can help with |
| --- | --- |
| **Calendar** | Read upcoming events, create/update/delete meetings, and recognize meeting links and locations. |
| **Meeting preparation** | Open the meeting link and the relevant browser tabs, apps, CRM, documents, Slack or Notion context on the Mac. |
| **Meeting capture** | Ask for recording consent, record locally, transcribe, create an AI summary and save notes to Google Drive. |
| **Restaurant and coworking** | Find or reserve a restaurant/coworking option only when the user asks; confirmed details can be added to Calendar. |
| **Ride logistics** | Suggest an Uber for a Calendar destination and show options. It never requests a paid ride without explicit approval. |
| **Proactive help** | In automatic mode, prepare eligible meetings. In manual mode, ask before invoking a suggested skill. |

### Designed to stay in control

- Calendar access comes from the Google account connected in Plow Latch; Coffee Work does **not** require a separate Google Calendar OAuth client.
- Restaurant/coworking reservations are manual-only. Uber, paid bookings, recording and Drive publishing require the appropriate confirmation or consent.
- The agent asks for Plow's action approval when needed. The owner can use **Allow Once** to test safely or **Always Allow** for a trusted recurring action.
- Transcription is local to macOS. Google Drive publishing is optional and has a separate one-time authorization.

---

## Português

### A proposta

O **Coffee Work** transforma o Mac em um assistente de rotina de trabalho. Ele reduz o atrito entre agenda, reunião, anotações e deslocamento: prepara o computador antes da chamada, ajuda a registrar decisões e organiza a logística em volta do compromisso.

Ele usa o Google Calendar conectado ao Plow Latch, conversa pelo Hermes/iMessage e aciona as skills certas conforme o contexto. Um job verifica a agenda a cada dez minutos e oferece ajuda no momento certo.

| Momento de trabalho | O que o Coffee Work faz |
| --- | --- |
| **Agenda** | Consulta próximos eventos, cria/edita/exclui compromissos e identifica links e locais. |
| **Preparação** | Abre o link da reunião, abas, aplicativos, CRM, documentos, Slack ou Notion relevantes no Mac. |
| **Registro da reunião** | Pede consentimento, grava localmente, transcreve, resume com IA e salva no Google Drive. |
| **Restaurante e coworking** | Busca ou reserva apenas quando o usuário pedir; os dados confirmados podem entrar no Calendar. |
| **Uber** | Sugere corrida para um destino da agenda e mostra opções. Nunca solicita corrida paga sem aprovação explícita. |
| **Ajuda proativa** | No modo automático, prepara reuniões elegíveis; no manual, pergunta antes de chamar a skill sugerida. |

---

## Install on macOS

These are the complete commands for a normal Mac user. Copy one block at a time into **Terminal**. The same installation serves both English and Portuguese users; Coffee Work's chat replies are in English.

### 1. Install the required apps

Install these apps first:

1. [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) — open it once and wait until Docker is running.
2. [Google Chrome](https://www.google.com/chrome/) — used for meeting links and browser booking.
3. **Plow Latch** — download/sign in through the [Plow dashboard](https://api.plow.co/app/dashboard), then leave Latch running on the Mac.
4. Apple Command Line Tools — in Terminal, run:

```bash
xcode-select --install
```

After the installer finishes, open a **new Terminal window** and check the basics:

```bash
git --version
docker --version
docker compose version
```

If any command says `command not found`, finish that app's installation before continuing.

### 2. Connect Google Calendar in Plow Latch

1. Open Plow Latch and sign in with the same Plow account that will own the agent.
2. In the Plow dashboard, connect the Google account that owns the Calendar.
3. Keep Plow Latch open. Calendar reads/writes are relayed through Latch's authenticated Google connection.

No `google-client-secret.json` and no Google Calendar OAuth file are needed for this project.

### 3. Clone Plow and Coffee Work

Choose one stable folder. This guide uses `~/CoffeeWork`:

```bash
mkdir -p "$HOME/CoffeeWork"
cd "$HOME/CoffeeWork"
git clone https://github.com/plow-pbc/plow-agents.git
git clone https://github.com/leandroralexandre2/coffee-work-agent.git
```


```bash
export PATH="$HOME/CoffeeWork/plow-agents/bin:$PATH"
cd "$HOME/CoffeeWork/coffee-work-agent"
```

To make `plow-agents` available after every new Terminal session, run this once:

```bash
echo 'export PATH="$HOME/CoffeeWork/plow-agents/bin:$PATH"' >> "$HOME/.zshrc"
source "$HOME/.zshrc"
```

### 4. Activate a Plow line and create the agent credential

From the `coffee-work-agent` folder, run:

```bash
plow-agents login
```

Terminal will show a short activation text and a phone number. Send **exactly that text** from iMessage, then wait until Terminal says the account token was written. Next, list available lines:

```bash
plow-agents lines
```

Choose a line whose status is `free` — for example `ln_p1` — and mint it:

```bash
plow-agents mint ln_p1
chmod 600 plow-credentials
```

This writes `plow-credentials` inside the Coffee Work folder. **Do not copy an older credential over this file.** If you need to replace a credential later, use `plow-agents rotate` or `plow-agents revoke <line>`; do not mint the same file twice.

### 5. Create the local environment file

```bash
cp agent.env.example .env
nano .env
```

Set a unique Agent Index identifier in `.env`, for example:

```dotenv
AGENT_ID=coffee-work-leandro
```

Save nano with `Control + O`, press `Return`, then exit with `Control + X`. The Plow base image includes the required Agent Index reporter. Use a unique `coffee-work-*` value so the usage is attributed to your agent.

### 6. Install the Mac helper and choose its mode

```bash
./scripts/install-mac.sh
nano "$HOME/.coffee-work/config.json"
```

The important starting values are:

```json
{
  "mode": "manual",
  "timezone": "America/Sao_Paulo",
  "calendar_id": "primary"
}
```

- `manual`: Coffee Work asks before preparing a meeting or offering a related action. Recommended for the first run.
- `automatic`: Coffee Work can proactively prepare eligible meetings. It still does not buy rides, book venues or record without the required confirmation/consent.

Save and close nano. The watcher runs inside Docker; do not run the old `coffee-work auth` or a separate macOS calendar timer.

### 7. Allow the required macOS permissions

Open **System Settings → Privacy & Security**:

1. **Automation**: allow Plow Latch (and Terminal, if prompted) to control **Google Chrome**.
2. **Accessibility**: allow Plow Latch if macOS asks.
3. For recording: allow the recording helper the requested **Microphone**, **Screen Recording** and **Speech Recognition** permissions.

In Chrome, enable **View → Developer → Allow JavaScript from Apple Events** if a browser action reports an Apple Events permission error. Quit and reopen Chrome after changing permissions.

### 8. Start Coffee Work

Make sure Docker Desktop and Plow Latch are running. In the project folder:

```bash
cd "$HOME/CoffeeWork/coffee-work-agent"
docker compose up --build -d
docker compose ps
docker compose logs -f agent
```

The expected status is `Up`. Press `Control + C` to stop only the log view; the agent keeps running in the background. The Calendar watcher checks every **10 minutes**.

If logs show `401 -- Plow refused this credential`, stop the container and mint a fresh credential for a free line. Do not reuse or overwrite a credential from another project.

### 9. Send the first message

Find the iMessage number for the line:

```bash
plow-agents lines
```

From iMessage, send `Hello Coffee Work` to the number shown for the minted line. Then try:

> What is my next calendar event?

Plow may display an approval card for the first Calendar query. Select **Allow Once** for a test or **Always Allow** if you trust that recurring calendar action.

### 10. Optional: authorize Google Drive for meeting notes

Calendar uses Plow Latch and needs no Google OAuth file. Google Drive is different: it is only needed when you choose to publish meeting notes. When prompted, run:

```bash
"$HOME/.coffee-work/bin/coffee-work" drive-auth
```

Complete the Google permission page in the browser, then ask Coffee Work to save the finished notes.

### Everyday commands

```bash
cd "$HOME/CoffeeWork/coffee-work-agent"
docker compose ps                 # Is it running?
docker compose logs -f agent      # Live logs
docker compose restart agent      # Restart after a configuration change
docker compose down               # Stop Coffee Work
docker compose up -d              # Start it again
```

---

## Instalação no macOS

Resumo em português: instale Docker Desktop, Chrome e Plow Latch; conecte sua conta Google no painel do Plow; clone `plow-agents` e este repositório; ative uma linha livre com `plow-agents login` e `plow-agents mint`; execute `./scripts/install-mac.sh`; dê as permissões do macOS; e inicie com `docker compose up --build -d`.

Os comandos completos estão na seção em inglês acima porque funcionam igual em qualquer Mac. Os cuidados importantes são:

- Use uma linha com status `free` e mantenha o `plow-credentials` recém-criado dentro da pasta do Coffee Work.
- Não copie uma credencial antiga por cima dela; isso causa erro `401` no Plow.
- Use o modo `manual` no primeiro teste.
- Ao aparecer uma aprovação do Plow para consultar a agenda, escolha **Allow Once** para testar com segurança.
- O Google Calendar já vem do Plow Latch; só o envio de notas para o Google Drive pede autorização separada.

---

## Demo prompts

Use these messages in iMessage. They are deliberately specific: each one has a clear outcome and keeps paid or sensitive actions behind a confirmation.

| Goal | English message to Coffee Work |
| --- | --- |
| Prepare for a meeting | `I have a client review in 15 minutes. Prepare my Mac for the meeting and open the meeting link.` |
| Start recording | `Record this meeting and create notes. I confirm that everyone has been informed and I consent to recording.` |
| Finish and save notes | `Stop recording, summarize the meeting, and save the notes to Google Drive.` |
| Restaurant | `Book a table for two at [RESTAURANT] this Friday at 7:30 PM. Show me the details before you confirm anything.` |
| Coworking | `Find a coworking desk near [NEIGHBORHOOD] tomorrow from 9 AM to 1 PM. Do not reserve it until I approve the exact option.` |
| Uber | `I have a dinner reservation tonight. Check the Calendar destination and show me the Uber options and fare. Do not request a ride yet.` |
| Proactive mode | `Set my meeting preparation mode to automatic for today.` |

### Frases de demonstração em português

| Objetivo | Mensagem em português |
| --- | --- |
| Preparar reunião | `Tenho uma reunião com cliente em 15 minutos. Prepare meu Mac e abra o link da reunião.` |
| Gravar reunião | `Grave esta reunião e crie as anotações. Confirmo que todos foram avisados e autorizo a gravação.` |
| Finalizar e salvar | `Pare a gravação, resuma a reunião e salve as anotações no Google Drive.` |
| Reservar restaurante | `Reserve uma mesa para duas pessoas no [RESTAURANTE] nesta sexta às 19h30. Mostre os detalhes antes de confirmar qualquer coisa.` |
| Reservar coworking | `Encontre uma mesa de coworking perto de [BAIRRO] amanhã, das 9h às 13h. Não reserve até eu aprovar a opção exata.` |
| Chamar Uber | `Tenho uma reserva para jantar hoje. Veja o destino no Calendar e me mostre as opções e o valor do Uber. Não solicite a corrida ainda.` |

---

## Verify the project before submitting

From the repository folder, run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s ld-mac-prepare-native/tests -p 'test_*.py'
python3 -m unittest discover -s hermes-uber-ride-agent/tests -p 'test_*.py'
docker compose ps
```

For a complete smoke test, send the Calendar question first, then use the meeting-preparation prompt above. Test recording only with informed participants and test Uber/booking with a preview before any confirmation.

## License and acknowledgements

Coffee Work is open source under the MIT License. See [NOTICE](NOTICE) for upstream components and attributions.
