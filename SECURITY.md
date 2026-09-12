# Security Policy

## Supported versions

`v2.0.0-dev.10` is a development preview. Security fixes are applied to the newest development release only.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting or contact the repository owner through GitHub. Do not publish credentials, private URLs, customer data, model download tokens, project archives, or proof-of-concept details that expose another system in a public issue.

Include the affected version, the smallest reproducible example, expected impact, and any safe mitigation you have already tested.

## Deployment boundary

The default development server is for local use. Put authentication, HTTPS, request limits, and network isolation in front of any Internet-facing deployment. ComfyUI and local LLM endpoints should remain on loopback or a trusted private network.
