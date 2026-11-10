---
name: writing-plans
description: Use when a spec is approved, before coding. Full paths.
---

# writing-plans (adaptado de obra/superpowers, MIT)

## Regra
Plano é documento de tarefas que um junior SEM contexto consegue seguir — sem TBD, sem 'e aí a gente vê'.

## Estrutura
1. Contexto: o que já existe, onde (paths reais), decisão tomada e POR QUÊ (linkar blueprint/ata).
2. Tarefas de 2-5 min de trabalho cada, na ordem, cada uma com:
   - Arquivo exato a tocar (path completo)
   - Comportamento esperado (critério de aceite objetivo)
   - Como VERIFICAR (comando/observação)
3. Riscos conhecidos e o plano B de cada (pitfalls do playbook da skill do projeto).
4. Zero placeholder: 'TBD' e 'etc' são bugs de plano.

## Como o Hermes usa
O briefing de subagente (delegate_task context) é o plano desta skill em prática — cada voo da Morgana segue este formato. Revisar contra este checklist antes de despachar.

## Auto-revisão
Reler o plano inteiro procurando: tarefa com dois verbos no infinitivo (quebrar), verificação vaga ('testar' — O QUÊ, com qual comando), dependência implícita entre tarefas paralelas.