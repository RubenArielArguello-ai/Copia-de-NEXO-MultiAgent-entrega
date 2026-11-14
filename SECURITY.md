# Security Guidelines for NEXO MultiAgent

## Container Security

### Best Practices:
1. Use official Python images from Docker Hub
2. Always use the latest stable versions
3. Follow security recommendations from Docker:
   - https://github.com/docker/hygiene
4. Implement proper user management in containers

## Dependency Management

### Recommendations:
1. Keep `requirements.txt` up to date
2. Use secure package sources
3. Regularly audit dependencies for vulnerabilities
4. Monitor for new versions and updates

## Network Security

### Best Practices:
1. Use the `docker-compose` network model
2. Avoid mapping unnecessary ports
3. Implement proper firewall rules
4. Use HTTPS for internal communication if possible

NEXO binds to `127.0.0.1` by default. Compose publishes the dashboard/API only on
host loopback and does not publish Ollama's port. Set a high-entropy
`NEXO_API_TOKEN` for bearer authentication; production mode refuses API access
without it. CORS origins are controlled by `NEXO_CORS_ORIGINS`.

## Tool boundaries

Read-only diagnostics are the default. File tools resolve paths and reject
paths outside the project workspace. The legacy Python helper evaluates only
bounded arithmetic expressions; it does not spawn a shell or execute Python
programs. Skills must be registered and authorized for the requesting agent.

## Credentials Management

### Recommendations:
1. Never commit credential files
2. Use environment variables for secrets
3. Rotate credentials regularly
4. Implement MFA where possible

## Reporting Vulnerabilities

If you find a security issue, please report it responsibly by contacting the project maintainers.
