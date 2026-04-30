# Guacamole Gateway

This is the browser gateway for the final online runtime.

## First boot

```bash
cp .env.example .env
# edit .env with a real password
docker run --rm guacamole/guacamole:1.6.0 /opt/guacamole/bin/initdb.sh --postgresql > initdb/001-initdb.sql
docker compose up -d
```

Guacamole will be available locally on the server at:

```text
http://127.0.0.1:8080/guacamole/
```

Put a TLS reverse proxy in front of it for the public URL.

## Runtime connection

Create an RDP connection to the Windows runtime host:

- Protocol: RDP
- Hostname: Windows runtime internal IP or hostname
- Port: 3389
- Audio: enabled/default
- Initial program: original projector launcher when stable

The Windows VM/server must have Remote Desktop enabled and the original runtime installed or mounted.
