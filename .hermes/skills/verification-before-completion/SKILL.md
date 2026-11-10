---
name: verification-before-completion
description: Use before claiming anything is done. Proof required.
---

# verification-before-completion (adaptado de obra/superpowers, MIT)

## Regra
Não existe 'done' sem EVIDÊNCIA. Toda declaração de conclusão cita a prova: output do teste, hash do digest, URL da release, saída do comando.

## Checklist
- O que EU rodei (não o que o subagente DISSE que rodou) confirma o resultado?
- Teste/verificação re-executado (--rerun-tasks quando houver cache)?
- External state verificado NA FONTE (release: digest local == GitHub; commit: git log; arquivo: read de volta)?
- Números declarados contados de verdade (contar XML de testes, não estimar)?
- Claim de subagente é self-report — o pai VERIFICA antes de repassar ao CEO.

## Antimotivação
Subagente dizendo 'upload ok' sem hash é rumor, não fato. A regra do O Sistema: digest local == digest GitHub, sempre.

## Frase-chave
'O relatório diz que funcionou? Então me mostra rodando.' — Débora