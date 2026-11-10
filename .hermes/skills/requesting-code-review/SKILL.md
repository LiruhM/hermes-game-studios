---
name: requesting-code-review
description: Use when a major feature is done, before release or merge.
---

# requesting-code-review (adaptado de obra/superpowers, MIT)

## Regra
Reviewer recebe CONTEXTO CONSTRUÍDO PRA ELE (o que devia fazer, onde olhar, o que é aceitável), nunca o histórico da sessão — ele acha o problema que VOCÊ deixou de ver por não carregar seus vieses.

## Checklist do despacho de review
- O que a mudança DEVIA fazer (especificação original, trecho citado)
- O que ela FAZ de fato (arquivos tocados, diff resumido)
- Onde é mais provável o erro (áreas de menor certeza do autor)
- Barra de aceite: o que é 'bom o suficiente' vs 'bloqueia'
- Reviewer NÃO recebe: racionalizações do autor, histórico de tentativas, 'confia em mim'

## No Hermes
A auditoria da Débora (QA-0110, QA-Bíblia-V1) é exatamente este padrão funcionando: contexto construído + severidades + mitigação. Em código: voo GRANDE = review da Débora antes do release.

## Redator ≠ juiz
Quem escreveu não se audita sozinho — review é ALWAYS despachado, nunca 'eu mesmo confio'.