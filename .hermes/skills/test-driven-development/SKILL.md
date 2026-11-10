---
name: test-driven-development
description: Use before implementing testable logic. RED-GREEN-REFACTOR.
---

# test-driven-development (adaptado de obra/superpowers, MIT)

## O ciclo
1. **RED**: escreva o teste que FALHA primeiro (define o comportamento desejado). Rode e VEJA falhar — teste que nunca ficou vermelho não prova nada.
2. **GREEN**: o mínimo de código que faz passar. Nada mais.
3. **REFACTOR**: limpeza sem mudar comportamento (testes continuam verdes).

## Regras duras
- Código escrito antes de teste que o cubra = escrever de novo (no O Sistema: cada fix de gamificação exigiu 'teste unitário novo' no briefing — é esta skill em prática).
- Simulação antes de balanceamento (as 50k lutas do Incursão Engine) é o RED em escala: comportamento definido ANTES do código existir.
- Exceções legítimas (documentar): UI pura sem lógica, spikes descartáveis, config estática.

## Anti-padrões
- Teste escrito DEPOIS pra 'cobrir' (prova menos)
- Teste que lê a implementação atual (acoplado ao bug)
- Mockar demais: teste de unidade puro > teste que só testa o mock