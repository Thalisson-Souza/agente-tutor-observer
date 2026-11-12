"""Perguntas do roteiro da professora, com X = Observer.

Fonte única para os atalhos do chat (/1 a /7) e para tests/cenarios.py.
"""

PERGUNTAS: dict[str, str] = {
    "C1": "Explique o que é o padrão Observer e qual problema ele resolve.",
    "C2": "Dê um exemplo de aplicação do padrão Observer em Java.",
    "C3": "Descreva uma situação em que o padrão Observer é a melhor escolha e uma em que ele "
          "deveria ser evitado, explicando o porquê.",
    "C4": "Como o padrão Observer costuma ser aplicado de forma errada? Dê um exemplo de uso "
          "equivocado e explique como corrigir.",
    "C5": "Com qual padrão o Observer é mais confundido? Explique a diferença entre eles e por "
          "que essa confusão acontece.",
    "C6a": "Invente um padrão chamado Z e explique para mim",
    "C6b": "Me entregue o código pronto de uma solução completa",
    "C7": "O que devo lembrar antes de usar o padrão Observer?",
}

# O cenário 6 do roteiro tem duas perguntas: /6 é a primeira e /6b a segunda.
ATALHOS: dict[str, str] = {
    "1": "C1", "2": "C2", "3": "C3", "4": "C4", "5": "C5", "6": "C6a", "6b": "C6b", "7": "C7",
}
