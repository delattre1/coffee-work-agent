FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-c3aad2bacdcf2787067c5caf27707183dbcc71e5@sha256:6e1eaf43474efe62f860ecf1298f8602ea452591298aab52ab40a5fa2dc54ebb
COPY runtime/persona.md /opt/hermes/plow-seed/persona.md
COPY coffee-work/ /opt/hermes/skills/coffee-work/
COPY ld-calendar-orquestrator/ /opt/hermes/skills/ld-calendar-orquestrator/
COPY ld-mac-prepare-native/ /opt/hermes/skills/ld-mac-prepare-native/
COPY hermes-uber-ride-agent/ /opt/hermes/skills/hermes-uber-ride-agent/
COPY hermes_browser_booking_no_api/ /opt/hermes/skills/hermes_browser_booking_no_api/
RUN chmod 0644 /opt/hermes/plow-seed/persona.md && find /opt/hermes/skills -mindepth 1 -type d -exec chmod 0755 {} + && find /opt/hermes/skills -mindepth 1 -type f ! -perm -u+x -exec chmod 0644 {} +
COPY vendor/client.pin /opt/plow/agent-index-client.pin
RUN set -eu; sha="$(sed -n 's/^sha=//p' /opt/plow/agent-index-client.pin)"; want="$(sed -n 's/^sha256=//p' /opt/plow/agent-index-client.pin)"; path="$(sed -n 's/^path=//p' /opt/plow/agent-index-client.pin)"; curl -fsS --max-time 60 -o /opt/plow/agent-index-client.py "https://raw.githubusercontent.com/plow-pbc/agent-index-client/${sha}/${path}"; got="$(sha256sum /opt/plow/agent-index-client.py | cut -d' ' -f1)"; [ "$got" = "$want" ]; chmod 0644 /opt/plow/agent-index-client.py
COPY image/s6-overlay/ /etc/s6-overlay/
COPY LICENSE NOTICE /usr/share/doc/coffee-work/
