# Seguranca - AgentVision

## Rotacao de chaves Fernet

### Objetivo
Permitir a troca segura da chave de criptografia sem perder acesso
aos dados ja armazenados (credenciais, API keys, channel_config, etc.).

### Passo a passo

1. Gere uma nova chave Fernet:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

2. Atualize o `.env` com a nova chave como **primeira** em `ENCRYPTION_KEYS`:
```
ENCRYPTION_KEYS=nova_chave,antiga_chave
```

3. Execute o script de rotacao:
```bash
python -m scripts.rotate_encryption_keys
```

4. Remova a chave antiga do `.env`:
```
ENCRYPTION_KEYS=nova_chave
```

5. Reinicie os containers:
```bash
docker compose down
docker compose up -d --build
```

### Observacoes
- A primeira chave em `ENCRYPTION_KEYS` sempre sera usada para criptografar.
- As demais chaves servem apenas para descriptografar dados legados.
- Nunca versionar `.env` com chaves reais.
