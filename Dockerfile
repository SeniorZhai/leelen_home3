FROM ghcr.io/home-assistant/home-assistant:2026.9.1

COPY custom_components/leelen_home3 /opt/custom_components/leelen3
RUN python3 -c 'import json; print("\n".join(json.load(open("/opt/custom_components/leelen3/manifest.json"))["requirements"]))' > /tmp/leelen-requirements.txt \
    && uv pip install -r /tmp/leelen-requirements.txt -c /usr/src/homeassistant/homeassistant/package_constraints.txt \
    && rm /tmp/leelen-requirements.txt
COPY --chmod=755 docker/entrypoint.sh /leelen-entrypoint.sh
ENTRYPOINT ["/leelen-entrypoint.sh"]
