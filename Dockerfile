FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-ef0019372ff8bca593611b31ebd2e08f9f1458ff@sha256:a8a2f97ad78b8192d80a984dce81d3bf5a9a883d18cb7b677704913a09b56aee
COPY runtime/persona.md /opt/hermes/plow-seed/persona.md
COPY coffee-work/ /opt/hermes/skills/coffee-work/
COPY ld-calendar-orquestrator/ /opt/hermes/skills/ld-calendar-orquestrator/
COPY ld-mac-prepare-native/ /opt/hermes/skills/ld-mac-prepare-native/
COPY hermes-uber-ride-agent/ /opt/hermes/skills/hermes-uber-ride-agent/
COPY hermes_browser_booking_no_api/ /opt/hermes/skills/hermes_browser_booking_no_api/
RUN chmod 0644 /opt/hermes/plow-seed/persona.md && find /opt/hermes/skills -mindepth 1 -type d -exec chmod 0755 {} + && find /opt/hermes/skills -mindepth 1 -type f ! -perm -u+x -exec chmod 0644 {} +
COPY image/s6-overlay/ /etc/s6-overlay/
COPY LICENSE NOTICE /usr/share/doc/coffee-work/
