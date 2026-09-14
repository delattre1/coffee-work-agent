# English test and demo scenarios

Use these phrases exactly during the demo. All user-facing demo dialogue is in English.

## 1. Preflight

User:

> Hermes, check if my Mac is ready for the demo.

Expected:

> Your Mac is ready. Automation and Accessibility are available.

Permission failure:

> I still need Accessibility permission. Open System Settings → Privacy & Security → Accessibility and enable the Hermes host.

## 2. Create a personal preference

User:

> Hermes, whenever I am coding, keep Slack hidden but do not hide Spotify.

Expected:

> Got it. Coding mode will hide Slack and keep Spotify available.

User:

> When I prepare a presentation, open Keynote, Chrome, and Notes, then use the presentable layout.

Expected:

> Saved. Presentation mode will open Keynote, Chrome, and Notes in the presentable layout.

## 3. Start in coding context

User:

> Hermes, prepare my Mac for coding. I am implementing the automatic Calendar trigger.

Expected:

> Coding is ready — VS Code and Terminal are open, distractions are hidden, and your previous workspace is saved.

Optional follow-up:

> What did you remember about my previous context?

Expected:

> I saved your active apps, Chrome tabs, window positions, displays, and your current intent: “Implementing the automatic Calendar trigger.”

## 4. Calendar preparation moment

Hermes:

> Product Review starts in 10 min. Want me to prepare your Mac?

User:

> Yes, prepare it for the meeting.

Expected:

> Meeting mode is ready. Your coding context is safely stored in a Context Capsule.

## 5. Desktop layouts

User:

> Hermes, make my desktop presentation-ready.

Expected:

> Done. Your main window is in focus and the supporting apps are arranged around it.

User:

> Put Keynote on the main display and arrange Chrome and Notes on the second display.

Expected:

> Done. Keynote is on the main display, with Chrome and Notes arranged on the second display.

User:

> Split Chrome and Notes side by side.

Expected:

> Done. Chrome and Notes are arranged side by side.

User:

> Move this setup to the top of the screen.

Expected:

> Done. The workspace is arranged across the top of the screen.

User:

> Put Notes in the top-right corner.

Expected:

> Done. Notes is in the top-right corner.

User:

> Arrange these four apps in a clean grid.

Expected:

> Done. The apps are arranged in a clean two-by-two grid.

## 6. Recording consent — required trust moment

Hermes:

> The meeting is starting. Would you like me to record and transcribe it locally?

User denial:

> No, do not record this meeting.

Expected:

> Understood. I will not record anything.

User approval:

> Yes, start recording and transcribing now.

Expected:

> Recording started. System audio and microphone audio are being saved locally on this Mac.

Status check:

> Hermes, are you recording right now?

Expected:

> Yes. This meeting is being recorded locally.

Stop:

> Hermes, stop recording and create the meeting memory.

Expected:

> Recording stopped. The audio, transcript, decisions, and action items were saved locally.

On-device transcription unavailable:

> Recording stopped. The audio is safe, but on-device transcription is unavailable for this language. Nothing was sent to the cloud.

## 7. Resume — final wow moment

Hermes:

> You were coding before this meeting. Resume where you left off?

User:

> Yes, resume my previous context.

Expected:

> Back to coding. You were implementing the automatic Calendar trigger.

Follow-up:

> What was I working on before the meeting?

Expected:

> You were implementing the automatic Calendar trigger.

## 8. Custom modes

User:

> Create a study mode with Safari, Notes, and the split layout. Hide Messages and Mail.

Expected:

> Study mode is saved with Safari and Notes in a split layout. Messages and Mail will be hidden.

User:

> Add Spotify to my study mode.

Expected:

> Spotify was added to study mode.

User:

> Show me all my Prepare My Mac modes.

Expected:

> Your modes are coding, focus, meeting, presentation, study, and any custom modes you created.

## 9. Safe failure cases

User:

> Start recording.

Expected when consent is ambiguous:

> Before I start, please confirm: do you want me to record system audio and microphone audio locally now?

User:

> Close every app I am not using.

Expected:

> I can hide distractions safely, but I will not quit apps or risk unsaved work. Should I hide them instead?

User:

> Upload the meeting to Drive.

Expected:

> This version is local-only and does not upload recordings or context data. I can show you where the local files were saved.

## 10. Three-minute stage script

Presenter opening:

> My work changes all day, but my Mac does not. Every transition makes me rebuild both my desktop and my train of thought.

Presenter command:

> Hermes, prepare my Mac for coding. I am implementing the automatic Calendar trigger.

Calendar interruption:

> Product Review starts in 10 min. Want me to prepare your Mac?

Presenter response:

> Yes, prepare it for the meeting.

Presenter trust explanation:

> Hermes can prepare proactively, but it is conservative about capture. Recording always requires explicit consent.

Presenter consent:

> Yes, start recording and transcribing now.

Presenter stop:

> Hermes, stop recording and create the meeting memory.

Resume prompt:

> You were coding before this meeting. Resume where you left off?

Presenter response:

> Yes, resume my previous context.

Final Hermes line:

> Back to coding. You were implementing the automatic Calendar trigger.

Presenter closing:

> Prepare My Mac understands where I am going, protects where I came from, and brings me back without losing my train of thought. Your Mac is ready before you are.
